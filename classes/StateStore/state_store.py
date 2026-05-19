import aiosqlite
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import uuid
import json
from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class StateStoreEngineConfig(BaseModel):
    """Constructor input for StateStoreEngine."""
    db_path: str
    default_table_name: str


class GetStateInfoInput(BaseModel):
    """Input for get_state_info."""
    key: str


class UpdateKeyInput(BaseModel):
    """Input for update_key / upsert a row."""
    key: str
    value: Any


class DeleteKeyInput(BaseModel):
    """Input for delete_key / remove a row and all children."""
    key: str


class RemoveAtInput(BaseModel):
    """Input for remove_at / remove element from a JSON blob."""
    key: str
    locator: Union[int, str]


class InsertAtInput(BaseModel):
    """Input for insert_at / insert element into a JSON blob. locator=None appends."""
    key: str
    locator: Union[int, str, None]
    value: Any


class SetAtInput(BaseModel):
    """Input for set_at / update element inside a JSON blob."""
    key: str
    locator: Union[int, str]
    value: Any


class GetKeyExactInput(BaseModel):
    """Input for get_key_exact / single row fetch with no prefix expansion."""
    key: str


# --- Patch operation models ---

class AddOperation(BaseModel):
    op: Literal["add"]
    path: str
    value: Any

    @field_validator("path")
    @classmethod
    def path_must_be_dot_notation(cls, v: str) -> str:
        if not v or "/" in v:
            raise ValueError(f"path must use dot-notation, got {v!r}")
        return v


class RemoveOperation(BaseModel):
    op: Literal["remove"]
    path: str

    @field_validator("path")
    @classmethod
    def path_must_be_dot_notation(cls, v: str) -> str:
        if not v or "/" in v:
            raise ValueError(f"path must use dot-notation, got {v!r}")
        return v


class ReplaceOperation(BaseModel):
    op: Literal["replace"]
    path: str
    value: Any

    @field_validator("path")
    @classmethod
    def path_must_be_dot_notation(cls, v: str) -> str:
        if not v or "/" in v:
            raise ValueError(f"path must use dot-notation, got {v!r}")
        return v


class MoveOperation(BaseModel):
    op: Literal["move"]
    path: str
    from_path: str  # 'from' is a Python keyword — mapped via alias

    model_config = {"populate_by_name": True}

    @field_validator("path", "from_path")
    @classmethod
    def path_must_be_dot_notation(cls, v: str) -> str:
        if not v or "/" in v:
            raise ValueError(f"path must use dot-notation, got {v!r}")
        return v


class CopyOperation(BaseModel):
    op: Literal["copy"]
    path: str
    from_path: str

    model_config = {"populate_by_name": True}

    @field_validator("path", "from_path")
    @classmethod
    def path_must_be_dot_notation(cls, v: str) -> str:
        if not v or "/" in v:
            raise ValueError(f"path must use dot-notation, got {v!r}")
        return v


class TestOperation(BaseModel):
    op: Literal["test"]
    path: str
    value: Any

    @field_validator("path")
    @classmethod
    def path_must_be_dot_notation(cls, v: str) -> str:
        if not v or "/" in v:
            raise ValueError(f"path must use dot-notation, got {v!r}")
        return v


PatchOperation = Union[
    AddOperation,
    RemoveOperation,
    ReplaceOperation,
    MoveOperation,
    CopyOperation,
    TestOperation,
]


class ApplyPatchInput(BaseModel):
    """Input for apply_patch / bulk patch application."""
    patch: List[PatchOperation]


# --- StateStoreSidecar constructor ---

class StateStoreSidecarConfig(BaseModel):
    """Constructor input for StateStoreSidecar."""
    prefix: str
    sidecar_id: str


# --- StateStoreAgent constructor ---

class StateStoreAgentConfig(BaseModel):
    """Constructor input for StateStoreAgent."""
    prefix: str
    agent_id: str


# --- StateStore constructor ---

class StateStoreConfig(BaseModel):
    """Constructor input for StateStore."""
    db_path: str
    default_table_name: str

class StateStoreEngine:
    """Raw SQLite layer. Manages the key-value table and all JSON mutations."""

    def __init__(self, db_path: str, default_table_name: str):
        self.db_path = db_path
        self.default_table_name = default_table_name

    async def initialize(self):
        """Opens the SQLite connection and creates the key-value table if it doesn't exist."""
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.default_table_name} (
            key TEXT PRIMARY KEY,
            value TEXT CHECK(json_valid(value))
        )
        """)
        await self.conn.commit()

    async def get_state_info(self, key: str):
        """Fetches a value by exact key or reconstructs a nested dict from all keys matching key.*."""
        cursor = await self.conn.execute(
            f"""
            SELECT key,value
            FROM {self.default_table_name}
            WHERE key = ?
            OR key LIKE ?
            """,
            (key, f"{key}.%")
        )

        rows = await cursor.fetchall()

        result = {}

        for full_key, value in rows:

            value = json.loads(value)

            # remove prefix from key
            if full_key == key:
                return value

            relative_key = full_key[len(key) + 1:]

            parts = relative_key.split(".")

            current = result

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = value

        if result == {}:
            return None

        return result

    async def update_key(self, key: str, value: Any):
        """Upserts a row. Creates it if missing, overwrites if it exists. Value can be any JSON-serialisable type."""
        await self.conn.execute(
            f"INSERT OR REPLACE INTO {self.default_table_name} (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )

        await self.conn.commit()

    async def delete_key(self, key: str):
        """Deletes a row and all child rows matching key.*."""
        await self.conn.execute(
            f"DELETE FROM {self.default_table_name} WHERE key = ? OR key LIKE ?",
            (key, f"{key}.%")
        )

        await self.conn.commit()

    def _json_path(self, locator: Union[int, str, None]) -> str:
        """Converts a resolved locator into a SQLite JSON path string.

        The locator is produced by _resolve_path after inspecting the parent
        value's actual type in the DB. Three cases:

        int  -> '$[N]'   Parent was confirmed to be a list. N is the index.
                         Used by json_remove/json_insert/json_set to target
                         a specific element e.g. '$[1]' on [10, 20, 30] -> 20.

        str  -> '$.key'  Parent was confirmed to be a dict. key is the field
                         name, which may itself be a digit string like "1".
                         e.g. '$.name' on {"name": "x"} -> "x"
                         e.g. '$.1'    on {"1": "x"}    -> "x"

        None -> '$[#]'   Append sentinel. '#' is a SQLite extension meaning
                         one past the last index, so json_insert with '$[#]'
                         always appends to the end of the array.
        """
        if locator is None:
            return "$[#]"
        if isinstance(locator, int):
            return f"$[{locator}]"
        return f"$.{locator}"

    async def remove_at(self, key: str, locator: Union[int, str]):
        """Removes an element from a JSON blob in-place. Single SQL statement, no round-trip."""
        path = self._json_path(locator)
        await self.conn.execute(
            f"UPDATE {self.default_table_name} SET value = json_remove(value, '{path}') WHERE key = ?",
            (key,)
        )
        await self.conn.commit()

    async def insert_at(self, key: str, locator: Union[int, str, None], value: Any):
        """Inserts a value into a JSON blob in-place.

        locator=None  → appends to end of list via json_insert '$[#]' (single SQL)
        locator=str   → inserts dict key via json_insert '$.key'      (single SQL, no-op if key exists)
        locator=int   → inserts at index in list with shifting:
                          - if index is within bounds: fetch → list.insert() → write back (2 SQL)
                          - if index is out of bounds: json_insert '$[N]' (single SQL, no-op)
        """
        if isinstance(locator, int):
            current = await self.get_key_exact(key)
            if isinstance(current, list) and 0 <= locator < len(current):
                # index exists — must shift elements, SQLite can't do this natively
                current.insert(locator, value)
                await self.update_key(key, current)
                return

        path = self._json_path(locator)
        await self.conn.execute(
            f"UPDATE {self.default_table_name} SET value = json_insert(value, '{path}', json(?)) WHERE key = ?",
            (json.dumps(value), key)
        )
        await self.conn.commit()

    async def set_at(self, key: str, locator: Union[int, str], value: Any):
        """Updates an element inside a JSON blob in-place. Single SQL statement, no round-trip."""
        path = self._json_path(locator)
        await self.conn.execute(
            f"UPDATE {self.default_table_name} SET value = json_set(value, '{path}', json(?)) WHERE key = ?",
            (json.dumps(value), key)
        )
        await self.conn.commit()

    async def get_key_exact(self, key: str) -> Any:
        """Fetches the value at an exact key with no prefix expansion. Used internally by move/copy/test."""
        cursor = await self.conn.execute(
            f"SELECT value FROM {self.default_table_name} WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    async def cleanup(self):
        """Closes the SQLite connection."""
        await self.conn.close()


class StateStoreSidecar:
    """Scoped access layer over StateStoreEngine. All keys are namespaced under self.prefix.

    Exposes JSON Patch operations (add, remove, replace, move, copy, test) that automatically
    detect whether a path targets a whole DB row or an element inside a stored JSON blob.
    """

    def __init__(self, prefix: str, state_store_engine: StateStoreEngine, sidecar_id: str, parent=None):
        self.prefix = prefix
        self.state_store_engine = state_store_engine
        self.sidecar_id = sidecar_id
        self.parent = parent

    async def get_state_info(self, key: str = None):
        """Returns state at prefix.key. Pass empty string to get the full sidecar namespace."""
        if key == "" or key == None:
            sub_key = self.prefix
        else:
            sub_key = f"{self.prefix}.{key}"
        result = await self.state_store_engine.get_state_info(f"{sub_key}")
        return result

    async def _resolve_path(self, path: str) -> Tuple[str, Union[int, str, None]]:
        """
        Resolves a dot-notation path to a (store_key, locator) tuple.

        locator meaning:
          None -> whole DB row (no in-blob operation needed)
          int  -> list index within the JSON blob at store_key   e.g. "li.1"
          str  -> dict key within the JSON blob at store_key     e.g. "di.name"

        Special cases:
          single segment  "a"     -> ("a", None)       always a DB row
          digit last      "li.1"  -> ("li", 1)         always a list index
          append          "li.-"  -> ("li", None*)      None used as append sentinel

        For string last segments (e.g. "a.name"):
          - Fetch parent value from DB
          - If parent is a dict  -> locator = "name"  (key inside the blob)
          - If parent is a list  -> locator = "name"  (key inside the blob, unusual but valid)
          - If parent is missing or not a container -> locator = None (treat as separate DB row)
        """
        if not isinstance(path, str) or not path:
            return (path, None)

        parts = path.split(".")
        last = parts[-1]
        parent = ".".join(parts[:-1])

        # single segment — always a top-level DB row
        if not parent:
            return (path, None)

        # append sentinel
        if last == "-":
            return (parent, None)

        # for both digit and string segments — check what the parent actually stores
        full_parent = f"{self.prefix}.{parent}"
        parent_value = await self.state_store_engine.get_key_exact(full_parent)

        if isinstance(parent_value, list):
            # parent is a list — last segment must be an index
            return (parent, int(last)) if last.lstrip("-").isdigit() else (path, None)

        if isinstance(parent_value, dict):
            # parent is a dict — last segment is always a string key
            return (parent, last)

        # parent doesn't exist or is a scalar — treat as a separate DB row
        return (path, None)

    async def add(self, path: str, value: Any):
        """Inserts a value at path. Creates a new DB row for scalar paths, or inserts into a list/dict blob."""
        key, locator = await self._resolve_path(path)
        full_key = f"{self.prefix}.{key}"
        if locator is not None or path.endswith(".-"):
            await self.state_store_engine.insert_at(full_key, locator, value)
        else:
            await self.state_store_engine.update_key(full_key, value)

    async def remove(self, path: str):
        """Removes a value at path. Deletes the whole DB row for scalar paths, or removes from a list/dict blob."""
        key, locator = await self._resolve_path(path)
        full_key = f"{self.prefix}.{key}"
        if locator is not None:
            await self.state_store_engine.remove_at(full_key, locator)
        else:
            await self.state_store_engine.delete_key(full_key)

    async def replace(self, path: str, value: Any):
        """Updates a value at path. Overwrites the whole DB row for scalar paths, or sets element inside a blob."""
        key, locator = await self._resolve_path(path)
        full_key = f"{self.prefix}.{key}"
        if locator is not None:
            await self.state_store_engine.set_at(full_key, locator, value)
        else:
            await self.state_store_engine.update_key(full_key, value)

    async def move(self, from_path: str, to_path: str):
        """Reads value from from_path, writes it to to_path, then removes from_path."""
        from_key, from_locator = await self._resolve_path(from_path)
        full_from_key = f"{self.prefix}.{from_key}"
        if from_locator is not None:
            current = await self.state_store_engine.get_key_exact(full_from_key)
            value = current[from_locator]
        else:
            value = await self.state_store_engine.get_key_exact(full_from_key)
        await self.add(to_path, value)
        await self.remove(from_path)

    async def copy(self, from_path: str, to_path: str):
        """Reads value from from_path and writes it to to_path. Original is kept intact."""
        from_key, from_locator = await self._resolve_path(from_path)
        full_from_key = f"{self.prefix}.{from_key}"
        if from_locator is not None:
            current = await self.state_store_engine.get_key_exact(full_from_key)
            value = current[from_locator]
        else:
            value = await self.state_store_engine.get_key_exact(full_from_key)
        await self.add(to_path, value)

    async def test(self, path: str, expected_value: Any) -> bool:
        """Asserts the value at path equals expected_value. Raises ValueError if it doesn't."""
        key, locator = await self._resolve_path(path)
        full_key = f"{self.prefix}.{key}"
        if locator is not None:
            current = await self.state_store_engine.get_key_exact(full_key)
            actual = current[locator] if current is not None else None
        else:
            actual = await self.state_store_engine.get_key_exact(full_key)
        if actual != expected_value:
            raise ValueError(f"Test failed at '{path}': expected {expected_value!r}, got {actual!r}")
        return True

    async def apply_patch_operation(self, op: Union[PatchOperation, dict]):
        """Applies a single patch operation to the store.

        Accepts either a typed PatchOperation model or a raw dict (validated on entry).
        Paths must use dot-notation (e.g. 'a.b.c'). Raises ValueError for invalid input.
        """
        from pydantic import TypeAdapter
        if isinstance(op, dict):
            op = TypeAdapter(PatchOperation).validate_python(op)

        if isinstance(op, AddOperation):
            await self.add(op.path, op.value)
        elif isinstance(op, RemoveOperation):
            await self.remove(op.path)
        elif isinstance(op, ReplaceOperation):
            await self.replace(op.path, op.value)
        elif isinstance(op, MoveOperation):
            await self.move(op.from_path, op.path)
        elif isinstance(op, CopyOperation):
            await self.copy(op.from_path, op.path)
        elif isinstance(op, TestOperation):
            await self.test(op.path, op.value)

    async def apply_patch(self, patch: Union[ApplyPatchInput, List[Union[PatchOperation, dict]]]):
        """Bulk applies a list of patch operations in order. Stops on first failure.

        Accepts either an ApplyPatchInput model or a raw list of dicts/PatchOperation models.
        All paths must use dot-notation. Raises ValueError on invalid input or test failure.
        """
        if isinstance(patch, list):
            patch = ApplyPatchInput(patch=patch)

        for i, op in enumerate(patch.patch):
            try:
                await self.apply_patch_operation(op)
            except Exception as e:
                raise ValueError(f"Patch failed at operation {i} {op!r}: {e}") from e


class StateStoreAgent(StateStoreSidecar):
    """Hierarchical extension of StateStoreSidecar. Can own child sidecars and sub-agents."""

    def __init__(self, prefix: str, state_store_engine: StateStoreEngine, agent_id: str, parent=None):
        self.prefix = prefix
        self.state_store_engine = state_store_engine
        self.agent_id = agent_id
        self.parent = parent

        self.sidecars : Dict[str,StateStoreSidecar] = {}
        self.sub_agents : Dict[str,"StateStoreAgent"]  = {}

    async def get_sidecar(self, sidecar_prefix: str):
        """Returns an existing sidecar or creates a new one scoped to prefix.sidecar_prefix."""
        if sidecar_prefix in self.sidecars:
            return self.sidecars[sidecar_prefix]

        sidecar_id = str(uuid.uuid4())
        sidecar = StateStoreSidecar(prefix=f"{self.prefix}.{sidecar_prefix}", state_store_engine=self.state_store_engine, sidecar_id=sidecar_id, parent=self)

        self.sidecars[sidecar_prefix] = sidecar
        return sidecar

    async def get_subAgent(self, sub_agent_prefix: str):
        """Returns an existing sub-agent or creates a new one scoped to prefix.sub_agent_prefix."""
        if sub_agent_prefix in self.sub_agents:
            return self.sub_agents[sub_agent_prefix]

        sub_agent_id = str(uuid.uuid4())
        sub_agent = StateStoreAgent(prefix=f"{self.prefix}.{sub_agent_prefix}", state_store_engine=self.state_store_engine, agent_id=sub_agent_id, parent=self)

        self.sub_agents[sub_agent_prefix] = sub_agent
        return sub_agent


class StateStore:
    """Root of the state store hierarchy. Owns the engine and top-level agents."""

    def __init__(self, db_path: str, default_table_name: str):
        self.db_path = db_path
        self.default_table_name = default_table_name

        self.agents = {}
        self._initialized = False

    def __getattribute__(self, name):
        attr = object.__getattribute__(self, name)

        if name in ("initialize", "_initialized", "__class__", "__dict__", "__getattribute__"):
            return attr

        if callable(attr):
            async def wrapper(*args, **kwargs):
                if not object.__getattribute__(self, "_initialized"):
                    raise RuntimeError("StateStore not initialized")
                return await attr(*args, **kwargs)
            return wrapper

        return attr

    async def initialize(self):
        """Creates the engine and initialises the database. Must be called before any other method."""
        self.engine = StateStoreEngine(db_path=self.db_path, default_table_name=self.default_table_name)
        self._initialized = True
        await self.engine.initialize()

    async def get_agent(self, prefix: str) -> StateStoreAgent:
        """Returns an existing agent or creates a new one scoped to prefix."""
        if prefix in self.agents:
            return self.agents[prefix]

        agent_id = str(uuid.uuid4())
        agent = StateStoreAgent(prefix=prefix, state_store_engine=self.engine, agent_id=agent_id, parent=self)

        self.agents[prefix] = agent
        return agent

    async def cleanup(self):
        """Closes the database connection."""
        await self.engine.cleanup()
