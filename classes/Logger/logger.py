"""Logger — hierarchical logging system.

Pattern (similar to StateStore):
- Logger (root) → creates LogAgent instances via get_agent()
- LogAgent → can create sub-agents (LogAgent) and sidecars (LogSidecar)
- LogSidecar → LEAF node, has emit methods, NO children

Component names build up as: parent.component_name

Owns:
    agent_registry – { component_name: log_level }
    output routing – stdout / file / structured JSON
"""

import json
import inspect
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, TextIO, Union
from enum import Enum


class LogFormat(Enum):
    """Output format for log messages."""

    JSON = "json"
    NORMAL = "normal"


_LEVEL_ORDER: Dict[str, int] = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
}


class LogSidecar:
    """Leaf node in logging hierarchy - FINAL entity, NO children.

    Has emit methods and configuration, but cannot create children.

    State:
        component_name – the full hierarchical name (e.g., "engine.application")
        identifier     – custom string identifier for this sidecar
        _logger       – reference back to the owning Logger instance
        _level        – log level (DEBUG, INFO, WARNING, ERROR)
        _format       – LogFormat enum (JSON or NORMAL)
        _include_function_name – whether to include caller function name (default: True)

    Methods:
        debug(message, **kwargs)    – log at DEBUG level
        info(message, **kwargs)     – log at INFO level
        warning(message, **kwargs)  – log at WARNING level
        error(message, **kwargs)    – log at ERROR level
        set_format(format)           – Set log format (JSON/NORMAL)
        set_level(level)             – Set log level (DEBUG/INFO/WARNING/ERROR)
        set_identifier(identifier)   – Set custom string identifier
        set_include_function_name(include) – Enable/disable function name logging (default: True)
    """

    def __init__(
        self,
        component_name: str,
        logger: "Logger",
        identifier: Optional[str] = None,
        parent: Optional["LogSidecar"] = None,
    ) -> None:
        self.component_name = component_name
        self.identifier = identifier
        self._logger = logger
        self._parent = parent
        self._level = "INFO"
        self._format = LogFormat.NORMAL
        self._include_function_name = True  # Default: ON
        self._enabled = True  # Default: logging enabled

    def _is_enabled_by_parent(self) -> bool:
        """Check if any parent in the hierarchy is disabled."""
        current = self._parent
        while current is not None:
            if not isinstance(current, Logger) and not current._enabled:
                return False
            current = getattr(current, "_parent", None)
        return True

    async def debug(self, message: str, **kwargs) -> None:
        """Log at DEBUG level."""
        await self._emit("DEBUG", message, **kwargs)

    async def info(self, message: str, **kwargs) -> None:
        """Log at INFO level."""
        await self._emit("INFO", message, **kwargs)

    async def warning(self, message: str, **kwargs) -> None:
        """Log at WARNING level."""
        await self._emit("WARNING", message, **kwargs)

    async def error(self, message: str, **kwargs) -> None:
        """Log at ERROR level."""
        await self._emit("ERROR", message, **kwargs)

    def _get_caller_function_name(self) -> Optional[str]:
        """Extract the function name from the caller's stack frame.

        Walks up the call stack to find the actual caller:
        Frame 0: _get_caller_function_name
        Frame 1: _emit
        Frame 2: debug/info/warning/error
        Frame 3: User code (actual caller)
        """
        frame = inspect.currentframe()
        try:
            if frame is not None:
                # Walk up: _get_caller_function_name -> _emit -> public method -> user code
                caller_frame = frame.f_back.f_back.f_back
                if caller_frame is not None:
                    return caller_frame.f_code.co_name
        finally:
            del frame
        return None

    async def _emit(self, level: str, message: str, **kwargs) -> None:
        """Internal emit - checks level and outputs."""
        if not self._enabled or not self._is_enabled_by_parent():
            return

        if _LEVEL_ORDER.get(level, 999) < _LEVEL_ORDER.get(self._level, 1):
            return

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "component": self.component_name,
            "message": message,
        }

        if self.identifier:
            log_entry["identifier"] = self.identifier

        if self._include_function_name:
            caller_func = self._get_caller_function_name()
            if caller_func:
                log_entry["function"] = caller_func

        log_entry.update(kwargs)

        if self._format == LogFormat.JSON:
            line = json.dumps(log_entry)
        else:
            timestamp = log_entry["timestamp"]
            level_str = log_entry["level"]
            component_str = log_entry["component"]
            message_str = log_entry["message"]
            function_str = log_entry.get("function", "")

            extra_fields = []
            for key, value in kwargs.items():
                extra_fields.append(f"{key}={value}")
            extra_str = " | ".join(extra_fields) if extra_fields else ""

            id_str = f" | {self.identifier}" if self.identifier else ""
            func_str = f" | {function_str}" if function_str else ""
            if extra_str:
                line = f"{timestamp} | {level_str} | {component_str}{id_str}{func_str} | {extra_str} | {message_str}"
            else:
                line = f"{timestamp} | {level_str} | {component_str}{id_str}{func_str} | {message_str}"

        await self._logger.enqueue_output_line(line)

    def set_format(self, log_format: LogFormat) -> None:
        """Set the log format for this sidecar (JSON or NORMAL)."""
        self._format = log_format

    def set_level(self, level: str) -> None:
        """Set the log level for this sidecar."""
        level_upper = level.upper()
        if level_upper not in _LEVEL_ORDER:
            raise ValueError(
                f"Invalid log level: {level}. Must be DEBUG, INFO, WARNING, or ERROR"
            )
        self._level = level_upper

    def set_identifier(self, identifier: str) -> None:
        """Set custom string identifier for this sidecar."""
        self.identifier = identifier

    def set_include_function_name(self, include: bool) -> None:
        """Enable or disable function name logging.

        Args:
            include: True to include function name in logs, False to disable.
                     Default: True
        """
        self._include_function_name = include

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable logging for this sidecar.

        Args:
            enabled: True to enable logging, False to disable.
                     Default: True

        Note: If parent is disabled, child cannot be enabled.
        """
        if not enabled:
            self._enabled = False
        else:
            if self._is_enabled_by_parent():
                self._enabled = True


class LogAgent(LogSidecar):
    """Agent node in logging hierarchy. Can create sub-agents and sidecars.

    Inherits emit methods from LogSidecar but adds child management:
    - get_agent(name) -> LogAgent (sub-agent with full prefix)
    - get_sidecar(name) -> LogSidecar (leaf with full prefix)

    State:
        Inherits from LogSidecar
        _sub_agents – { name: LogAgent }
        _sidecars   – { name: LogSidecar }

    Methods (inherited):
        debug, info, warning, error – emit log messages
        set_format, set_level, set_identifier – configure

    Methods (new):
        get_agent(name)    – Create or get sub-agent
        get_sidecar(name)  – Create or get sidecar
        set_child_level(name, level)          – Set level for specific child
        set_child_format(name, format)         – Set format for specific child
        set_child_identifier(name, identifier) – Set identifier for specific child
        set_all_children_level(level)         – Set level for all children
        set_all_children_format(format)        – Set format for all children
    """

    def __init__(
        self,
        component_name: str,
        logger: "Logger",
        identifier: Optional[str] = None,
        parent: Optional["LogSidecar"] = None,
    ) -> None:
        super().__init__(component_name, logger, identifier, parent)
        self._sub_agents: Dict[str, "LogAgent"] = {}
        self._sidecars: Dict[str, LogSidecar] = {}

    async def get_agent(self, agent_name: str) -> "LogAgent":
        """Create or return existing sub-agent.

        Args:
            agent_name: Name of the sub-agent (e.g., "session", "worker")

        Returns:
            LogAgent with component_name = parent.component_name.agent_name
        """
        if agent_name in self._sub_agents:
            return self._sub_agents[agent_name]

        full_name = f"{self.component_name}.{agent_name}"
        agent = LogAgent(
            component_name=full_name, logger=self._logger, identifier=None, parent=self
        )
        self._sub_agents[agent_name] = agent
        return agent

    async def get_sidecar(self, sidecar_name: str) -> LogSidecar:
        """Create or return existing sidecar.

        Args:
            sidecar_name: Name of the sidecar (e.g., "http", "db")

        Returns:
            LogSidecar with component_name = parent.component_name.sidecar_name
        """
        if sidecar_name in self._sidecars:
            return self._sidecars[sidecar_name]

        full_name = f"{self.component_name}.{sidecar_name}"
        sidecar = LogSidecar(
            component_name=full_name, logger=self._logger, identifier=None, parent=self
        )
        self._sidecars[sidecar_name] = sidecar
        return sidecar

    def set_child_level(self, child_name: str, level: str) -> None:
        """Set log level for a specific child (agent or sidecar)."""
        if child_name in self._sub_agents:
            self._sub_agents[child_name].set_level(level)
        elif child_name in self._sidecars:
            self._sidecars[child_name].set_level(level)

    def set_child_format(self, child_name: str, log_format: LogFormat) -> None:
        """Set log format for a specific child (agent or sidecar)."""
        if child_name in self._sub_agents:
            self._sub_agents[child_name].set_format(log_format)
        elif child_name in self._sidecars:
            self._sidecars[child_name].set_format(log_format)

    def set_child_identifier(self, child_name: str, identifier: str) -> None:
        """Set identifier for a specific child (agent or sidecar)."""
        if child_name in self._sub_agents:
            self._sub_agents[child_name].set_identifier(identifier)
        elif child_name in self._sidecars:
            self._sidecars[child_name].set_identifier(identifier)

    def set_all_children_level(self, level: str) -> None:
        """Set log level for all children (agents and sidecars)."""
        for agent in self._sub_agents.values():
            agent.set_level(level)
        for sidecar in self._sidecars.values():
            sidecar.set_level(level)

    def set_all_children_format(self, log_format: LogFormat) -> None:
        """Set log format for all children (agents and sidecars)."""
        for agent in self._sub_agents.values():
            agent.set_format(log_format)
        for sidecar in self._sidecars.values():
            sidecar.set_format(log_format)

    def set_child_enabled(self, child_name: str, enabled: bool) -> None:
        """Enable or disable logging for a specific child (agent or sidecar)."""
        if child_name in self._sub_agents:
            self._sub_agents[child_name].set_enabled(enabled)
        elif child_name in self._sidecars:
            self._sidecars[child_name].set_enabled(enabled)

    def set_all_children_enabled(self, enabled: bool) -> None:
        """Enable or disable logging for all children (agents and sidecars)."""
        for agent in self._sub_agents.values():
            agent.set_enabled(enabled)
        for sidecar in self._sidecars.values():
            sidecar.set_enabled(enabled)


class Logger:
    """Root of the logging hierarchy. Creates LogAgent instances only.

    Responsibilities:
    - Maintain agent_registry keyed by component name
    - Create LogAgent instances via get_agent()
    - Expose set_level() for runtime level changes

    Methods:
        get_agent(agent_name)   – Create LogAgent (root-level agent)
        set_level(level)        – Update log level for all agents
        set_level(level, name)   – Update log level for specific agent
    """

    def __init__(
        self,
        log_format: LogFormat = LogFormat.NORMAL,
        logging_file_path: Union[str, bool, None] = False,
    ) -> None:
        self._registry: Dict[str, str] = {}
        self.log: LogAgent = None  # type: ignore[assignment]
        self._format = log_format
        self.logging_file_path = logging_file_path
        self._agents: Dict[str, LogAgent] = {}
        self._output_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=10000)
        self._writer_task: Optional[asyncio.Task] = None
        self._dropped_lines = 0
        self._warned_no_loop = False
        self._file_handle: Optional[TextIO] = None
        self._active_file_path: Optional[Path] = None
        self._initialize()

    async def get_agent(self, agent_name: str) -> LogAgent:
        """Create or return existing root-level agent.

        Args:
            agent_name: Name of the agent (e.g., "engine", "session_supervisor")

        Returns:
            LogAgent with component_name = agent_name
        """
        if agent_name in self._agents:
            return self._agents[agent_name]

        agent = LogAgent(
            component_name=agent_name, logger=self, identifier=None, parent=self
        )
        self._agents[agent_name] = agent
        self._registry[agent_name] = "INFO"
        return agent

    async def set_level(self, level: str, component_name: Optional[str] = None) -> None:
        """Update log level at runtime.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            component_name: Optional specific component to set level for
        """
        level_upper = level.upper()
        if level_upper not in _LEVEL_ORDER:
            raise ValueError(
                f"Invalid log level: {level}. Must be DEBUG, INFO, WARNING, or ERROR"
            )

        if component_name:
            self._registry[component_name] = level_upper
        else:
            for key in self._registry:
                self._registry[key] = level_upper

        if self.log:
            target = component_name or "all components"
            await self.log.info(f"Log level set to {level_upper} for {target}")

    def _initialize(self) -> None:
        """Create own agent after registry is ready."""
        if "logger" not in self._registry:
            self._registry["logger"] = "INFO"
        self.log = LogAgent(component_name="logger", logger=self, identifier=None)

    async def enqueue_output_line(self, line: str) -> None:
        """Enqueue a formatted log line for async batched stdout writes.

        Falls back to direct stdout writes if called outside an active event loop.
        """
        self._ensure_writer_started()
        if self._writer_task is None:
            # Fallback path when no running event loop is available.
            self._write_batch([line])
            return

        try:
            self._output_queue.put_nowait(line)
        except asyncio.QueueFull:
            # Drop under heavy pressure to protect the event loop.
            self._dropped_lines += 1

    def _ensure_writer_started(self) -> None:
        """Start background writer task once per process when loop is active."""
        if self._writer_task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if not self._warned_no_loop:
                self._warned_no_loop = True
                self._write_batch(
                    [
                        f"{datetime.now(timezone.utc).isoformat()} | WARNING | logger | No running event loop; using sync stdout logging fallback"
                    ]
                )
            return

        self._writer_task = loop.create_task(self._output_writer_loop())

    async def _output_writer_loop(self) -> None:
        """Drain queued log lines and write to stdout in batches."""
        while True:
            first = await self._output_queue.get()
            batch = [first]
            dequeued_count = 1

            if self._dropped_lines:
                dropped = self._dropped_lines
                self._dropped_lines = 0
                batch.insert(
                    0,
                    f"{datetime.now(timezone.utc).isoformat()} | WARNING | logger | Dropped {dropped} log lines due to backpressure",
                )

            # Coalesce available lines to reduce syscall overhead.
            for _ in range(255):
                try:
                    batch.append(self._output_queue.get_nowait())
                    dequeued_count += 1
                except asyncio.QueueEmpty:
                    break

            try:
                # Write directly from the dedicated async writer task to avoid thread hop overhead.
                self._write_batch(batch)
            finally:
                # Mark done only for real queue items; synthetic drop warnings are not dequeued.
                for _ in range(dequeued_count):
                    self._output_queue.task_done()

    def _write_batch(self, lines: list[str]) -> None:
        if not lines:
            return
        if self.logging_file_path and isinstance(self.logging_file_path, str):
            self._write_batch_to_file(lines)
            return
        self._write_batch_to_stdout(lines)

    @staticmethod
    def _write_batch_to_stdout(lines: list[str]) -> None:
        if not lines:
            return
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

    def _write_batch_to_file(self, lines: list[str]) -> None:
        if not lines:
            return
        try:
            handle = self._get_or_open_file_handle()
            handle.write("\n".join(lines) + "\n")
            # Flush each batch for better durability while still reusing fd.
            handle.flush()
        except Exception as e:
            # If file logging fails, safely fallback to stdout for visibility.
            self._reset_file_handle()
            self._write_batch_to_stdout(
                [
                    f"{datetime.now(timezone.utc).isoformat()} | WARNING | logger | File logging failed, falling back to stdout | error={e}"
                ]
                + lines
            )

    def _get_or_open_file_handle(self) -> TextIO:
        """Return a reusable file handle for the configured logging path."""
        file_path = Path(self.logging_file_path)
        if (
            self._file_handle is not None
            and self._active_file_path is not None
            and self._active_file_path == file_path
            and not self._file_handle.closed
        ):
            return self._file_handle

        self._reset_file_handle()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Keep one persistent append-mode handle for fast batched writes.
        self._file_handle = file_path.open("a", encoding="utf-8")
        self._active_file_path = file_path
        return self._file_handle

    def _reset_file_handle(self) -> None:
        """Close and clear any existing file handle."""
        if self._file_handle is not None:
            try:
                self._file_handle.close()
            except Exception:
                pass
        self._file_handle = None
        self._active_file_path = None

    async def shutdown(self) -> None:
        """Drain pending log lines then close resources.

        Call this on service shutdown instead of close() to avoid losing
        buffered lines that haven't been written yet.
        """
        if self._writer_task is not None:
            try:
                await self._output_queue.join()
            except Exception:
                pass
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
            self._writer_task = None
        self._reset_file_handle()

    def close(self) -> None:
        """Close logger resources (file handle). Does NOT drain pending lines.

        Prefer shutdown() in async contexts to avoid log loss on exit.
        """
        self._reset_file_handle()
