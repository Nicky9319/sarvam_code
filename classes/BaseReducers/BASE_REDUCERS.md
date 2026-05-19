# BaseReducers

`BaseReducers` is the reusable infrastructure layer that all Reducer classes inherit from. It handles wrapping, validation, DB sync, and lifecycle — you only write the domain methods.

---

## What It Provides

| Feature | How it works |
|---|---|
| Input validation | `_pre_hook` inspects type hints and validates before every method call |
| Automatic DB sync | `_post_hook` diffs `domain_state` and writes changes to `StateStoreSidecar` via `PatchManager` |
| Nested call protection | `ContextVar` call depth counter — `_post_hook` only fires once when the outermost call returns |
| Error logging | Any exception in a wrapped method is logged before re-raising |
| Initialization guard | All public async methods raise `RuntimeError` if called before `initialize()` |

---

## PatchManager

`PatchManager` is a private helper created by `BaseReducers` during `initialize()`. It exists **only when a `StateStoreSidecar` is provided**. If no sidecar is given, `patch_manager` is `None` and all DB sync is skipped silently.

### What it does

On every `_post_hook` call:

1. Calls `current_state.model_dump()` to get the current state as a dict
2. Diffs against the previous snapshot using `jsonpatch.make_patch()`
3. Converts JSON Patch `/slash/paths` → `dot.notation` paths (matching StateStore's key format)
4. Calls `sidecar.apply_patch()` with the converted ops
5. Saves the current dump as the new snapshot

The first call after `initialize()` always produces a full `add` patch because `previous_state` starts as `{}` — this writes the entire initial state to the DB.

### Path conversion

```
JSON Patch path   →   StateStore key
"/frame_list"     →   "frame_list"
"/frame_list/frames/0/frame_id"  →  "frame_list.frames.0.frame_id"
```

---

## When PatchManager Is and Isn't Created

```
state_store_sidecar provided     →  PatchManager created, full initial state written to DB on initialize()
state_store_sidecar = None       →  patch_manager = None, no DB sync ever, runs in-memory only
```

There is no point creating `PatchManager` without a sidecar — it has nothing to write to. `BaseReducers` does not create it in that case.

---

## Nested Call Protection

If one reducer method calls another internally, `_post_hook` must only fire once — when the outermost call returns — not after every nested call.

This is handled with a `ContextVar[int]` call depth counter:

```
outer_method() called       → depth: 0 → 1
  inner_method_a() called   → depth: 1 → 2
  inner_method_a() returns  → depth: 2 → 1  (_post_hook NOT fired)
  inner_method_b() called   → depth: 1 → 2
  inner_method_b() returns  → depth: 2 → 1  (_post_hook NOT fired)
outer_method() returns      → depth: 1 → 0  (_post_hook fires once)
```

`ContextVar` is used (not a plain int) so the depth is tracked per-asyncio-task, making this async-safe when multiple tasks call reducers concurrently.

---

## Input Validation (`_pre_hook`)

Type hints on method parameters are validated automatically before every call:

| Type hint | Validation |
|---|---|
| `str` | must be a non-empty string |
| `Literal["a", "b"]` | must be one of the allowed values |
| `list` | must be a `list` instance |
| `Optional[X]` / `None` value | skipped entirely |

```python
async def set_url(self, url: str) -> None:
    # url="" → raises ReducerValidationError before method body runs
    self.domain_state.url = url

async def set_mode(self, mode: Literal["fast", "slow"]) -> None:
    # mode="other" → raises ReducerValidationError
    self.domain_state.mode = mode
```

Raises `ReducerValidationError` (subclass of `Exception`) on failure.

---

## Bypassed Methods

`__getattribute__` wrapping is skipped for:

- `initialize` — lifecycle method, must not be guarded by `_initialized` check
- `_pre_hook`, `_post_hook` — infrastructure, not domain methods
- Any method starting with `_` — private/internal, not part of the public reducer API
- Standard dunder attributes (`__class__`, `__dict__`, `__getattribute__`)

**Important:** Do not prefix domain methods with `_`. Underscore methods are not wrapped — no validation, no DB sync.

---

## Lifecycle

### `__init__`

```python
def __init__(self, logger: LogSidecar, state_store_sidecar: StateStoreSidecar = None):
```

Sets `logger`, `state_store_sidecar`, `domain_state = None`, `_initialized = False`, `patch_manager = None`.

### `initialize(domain_state)`

```python
async def initialize(self, domain_state: Any):
```

Called by the subclass's own `initialize()` via `super().initialize(MyDomainState())`.

- Sets `domain_state` and `_initialized = True`
- If `state_store_sidecar` is not `None`: creates `PatchManager` and writes the full initial state to DB
- If `state_store_sidecar` is `None`: sets `patch_manager = None`, no DB write

### `get_domain_state()`

Returns `self.domain_state.model_dump()`. Useful for debugging or exposing state to the Application Layer.

### `_cleanup()`

Base cleanup — logs a completion message. Subclasses override and call `super()._cleanup()` last.

---

## What You Can Override

### `_pre_hook` — add custom validation

```python
async def _pre_hook(self, method_name, func, args, kwargs):
    await super()._pre_hook(method_name, func, args, kwargs)  # keep base validation
    # add extra checks
```

### `_post_hook` — add side effects after every mutation

```python
async def _post_hook(self, method_name, result):
    await super()._post_hook(method_name, result)       # keep DB sync
    await self.event_bus.emit("state_changed")          # extra behaviour
```

### `_cleanup` — service-specific teardown

```python
async def _cleanup(self) -> None:
    await self.clear_something()   # domain cleanup first
    await super()._cleanup()       # base cleanup last
```

---

## What You Must NOT Do

- **Do not prefix domain methods with `_`** — they won't be wrapped (no validation, no DB sync)
- **Do not call `_post_hook` manually** — it fires automatically
- **Do not use `__getattribute__` yourself** — already set up in `BaseReducers`
- **Do not store state directly on `self`** — use `self.domain_state.*` so PatchManager can track it
- **Do not store non-serialisable objects in `domain_state`** — `jsonpatch` will fail on `model_dump()`
