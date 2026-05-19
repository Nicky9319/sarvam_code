"""BaseReducers — Reusable infrastructure layer for all reducer classes.

Provides:
  - __getattribute__ wrapping for all public async methods
  - _pre_hook: type-hint-driven input validation
  - _post_hook: automatic DB sync via PatchManager + StateStoreSidecar
  - call_depth_var: prevents nested reducer calls from triggering multiple DB writes
  - initialize() / get_domain_state() / _cleanup() base implementations

Usage:
    class MyReducers(BaseReducers):
        async def initialize(self):
            await super().initialize(MyDomainState())

        async def my_method(self, value: str) -> None:
            self.domain_state.some_field = value
"""

import inspect
import jsonpatch
from contextvars import ContextVar
from typing import Any, List, get_type_hints, Literal, get_origin, get_args

from classes.StateStore.state_store import StateStoreSidecar
from classes.Logger.logger import LogAgent


class ReducerValidationError(Exception):
    """Raised when a reducer input parameter fails type validation."""

    pass


class PatchManager:
    """Tracks domain state snapshots and syncs diffs to the StateStoreSidecar.

    On each call to generate_and_apply_patch:
      1. Diffs current state against previous snapshot via jsonpatch
      2. Converts /slash/paths → dot.notation paths
      3. Calls sidecar.apply_patch() with the converted ops
    """

    def __init__(self, sidecar: StateStoreSidecar):
        self.sidecar = sidecar
        self.previous_state: dict = {}  # empty so first diff generates full add patch

    def _convert_path(self, path: str) -> str:
        """Converts a JSON Patch /slash/path to a dot.notation path."""
        return path.lstrip("/").replace("/", ".")

    def _convert_patch(self, patch: List[dict]) -> List[dict]:
        """Converts all path and from fields in a patch list from slash to dot notation."""
        converted = []
        for op in patch:
            new_op = {**op, "path": self._convert_path(op["path"])}
            if "from" in op:
                new_op["from"] = self._convert_path(op["from"])
            converted.append(new_op)
        return converted

    async def generate_and_apply_patch(self, current_state: Any) -> List[dict]:
        """Diffs current_state against previous snapshot and applies changes to the sidecar.

        Returns the converted patch list that was applied. Empty list if no changes.
        """
        current_dump = current_state.model_dump()
        raw_patch = jsonpatch.make_patch(self.previous_state, current_dump).patch

        if not raw_patch:
            return []

        converted_patch = self._convert_patch(raw_patch)
        await self.sidecar.apply_patch(converted_patch)
        self.previous_state = current_dump
        return converted_patch


_call_depth_var: ContextVar[int] = ContextVar("call_depth", default=0)


class BaseReducers:
    """Reusable infrastructure for all reducer classes.

    Subclasses only need to:
      1. Call super().initialize(domain_state_instance) in their own initialize()
      2. Add domain-specific reducer methods

    Everything else (wrapping, validation, DB sync) is handled automatically.
    """

    def __init__(
        self,
        logger: LogAgent,
        state_store_sidecar: StateStoreSidecar = None,
    ) -> None:
        self.logger = logger
        self.state_store_sidecar = state_store_sidecar
        self.domain_state: Any = None
        self._initialized: bool = False

    # -----------------------------------------------------------------------
    # Hooks
    # -----------------------------------------------------------------------

    async def _pre_hook(self, _method_name: str, func, args, kwargs):
        """Validates all input params against their type hints before the method runs."""
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()

        type_hints = get_type_hints(func)

        for param_name, value in bound.arguments.items():
            param_type = type_hints.get(param_name)

            if value is None or param_type is None:
                continue

            if param_type == str:
                if not isinstance(value, str):
                    raise ReducerValidationError(f"{param_name} must be a string")

            elif get_origin(param_type) is Literal:
                if value not in get_args(param_type):
                    raise ReducerValidationError(
                        f"{param_name} must be one of {get_args(param_type)}, got {value!r}"
                    )

            elif get_origin(param_type) is list:
                if not isinstance(value, list):
                    raise ReducerValidationError(f"{param_name} must be a list")

    async def _post_hook(self, _method_name: str, _result: Any):
        """Diffs domain_state and syncs changes to the DB via PatchManager.

        No-op if no StateStoreSidecar was provided (patch_manager will be None).
        """
        if self.patch_manager is not None:
            await self.patch_manager.generate_and_apply_patch(self.domain_state)

    # -----------------------------------------------------------------------
    # __getattribute__ wrapping
    # -----------------------------------------------------------------------

    def __getattribute__(self, name: str):
        attr = object.__getattribute__(self, name)

        bypassed = {
            "initialize",
            "_initialized",
            "__class__",
            "__dict__",
            "__getattribute__",
            "_pre_hook",
            "_post_hook",
        }

        if name in bypassed:
            return attr

        if (
            callable(attr)
            and inspect.iscoroutinefunction(attr)
            and not name.startswith("_")
        ):

            async def wrapper(*args, **kwargs):
                if not object.__getattribute__(self, "_initialized"):
                    raise RuntimeError(
                        f"{type(self).__name__} is not initialized. Call initialize() first."
                    )

                token = _call_depth_var.set(_call_depth_var.get() + 1)

                try:
                    await object.__getattribute__(self, "_pre_hook")(
                        name, attr, args, kwargs
                    )
                    result = await attr(*args, **kwargs)

                except Exception as e:
                    try:
                        logger = object.__getattribute__(self, "logger")
                        await logger.error(f"{name} failed: {e}")
                    except Exception:
                        pass  # If logger also fails, just re-raise original exception
                    raise

                finally:
                    _call_depth_var.reset(token)

                sidecar = object.__getattribute__(self, "state_store_sidecar")
                if _call_depth_var.get() == 0 and sidecar is not None:
                    await object.__getattribute__(self, "_post_hook")(name, result)

                return result

            return wrapper

        return attr

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    async def initialize(self, domain_state: Any):
        """Base initialization. Subclasses must call this with their DomainState instance.

        Args:
            domain_state: An instantiated DomainState (or equivalent Pydantic model).
        """
        self.domain_state = domain_state
        self._initialized = True

        if self.state_store_sidecar is not None:
            self.patch_manager = PatchManager(sidecar=self.state_store_sidecar)
            await self._post_hook("initialize", None)  # writes full initial state to DB
        else:
            self.patch_manager = None  # no persistence — PatchManager not needed

    async def get_domain_state(self) -> dict:
        """Returns the full domain state as a dict."""
        return self.domain_state.model_dump()

    async def _cleanup(self) -> None:
        """Base cleanup. Subclasses can override and call super()._cleanup()."""
        await self.logger.info(f"{type(self).__name__} cleanup completed")
