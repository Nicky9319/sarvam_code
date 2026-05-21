from typing import Any


class StateStoreSidecar:
    """Minimal stub for StateStore persistence.

    Currently a no-op. apply_patch() does nothing, so the pipeline runs
    entirely in-memory. Pass None to Reducers to use this mode.

    Wire a real StateStoreAgent here when persistence is needed.
    """

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    def apply_patch(self, patch: dict[str, Any]) -> None:
        """No-op patch application."""
        pass

    async def _cleanup(self) -> None:
        self._initialized = False