"""Base EventBus — reusable BuBus wrapper for service-specific event buses.

Provides a foundation for event-driven architecture with:
- Pub/sub event delivery via BuBus
- Topic-specific event classes (no generic topic filtering)
- Async/sync handler support
- Acknowledgement mode (two-way vs fire-and-forget)
- Dynamic fallback event class creation for unknown topics

Child classes (EngineEventBus, SessionSupervisorEventBus) define specific event topics
and inherit emit/subscribe logic from this base class.
"""

from __future__ import annotations

import inspect
import re
import sys
from typing import Any, Callable, Type, Optional, Dict

from bubus import EventBus as BuBus, BaseEvent


class _BaseEventPayload(BaseEvent):
    """Base payload for topic-specific BuBus events."""

    data: Any | None = None


class BaseEventBus:
    """Reusable event bus wrapper built on top of BuBus.

    Responsibilities:
    - Event subscription management (subscribe/unsubscribe)
    - Event emission with acknowledgement mode support
    - Handler wrapper creation for async/sync handlers
    - Dynamic fallback event class creation for unknown topics

    Child classes should:
    - Define EVENT_CLASS_MAP mapping topics to event classes
    - Optionally provide logger for trace debugging
    """

    EVENT_CLASS_MAP: dict[str, Type[_BaseEventPayload]] = {}

    def __init__(self, logger: Any = None):
        self.bus: BuBus = BuBus()
        self.logger = logger
        self.trace_calls = False
        # Maps (topic, id(handler)) -> wrapper function so unsubscribe() can
        # remove the exact wrapper that was registered with BuBus.
        self._handler_wrappers: Dict[tuple, Callable] = {}

    async def cleanup(self) -> None:
        """Cleanup EventBus. Clears all subscriptions and pending tasks."""
        if self.bus and hasattr(self.bus, 'handlers'):
            self.bus.handlers.clear()
        self._handler_wrappers.clear()

    def _get_event_class(self, topic: str) -> Type[_BaseEventPayload]:
        """Get event class for a topic, creating a dynamic fallback if needed.

        Processing Steps:
        Step 1: Check child class EVENT_CLASS_MAP for known topic
        Step 2: Check if dynamically created class exists
        Step 3: Create new dynamic event class if not found

        Args:
            topic: Event topic name

        Returns:
            Event class for the topic
        """
        # Step 1: Check child class registry
        event_class = self.EVENT_CLASS_MAP.get(topic)
        if event_class is not None:
            return event_class

        # Step 2: Check if dynamically created class exists
        if topic in self.EVENT_CLASS_MAP:
            return self.EVENT_CLASS_MAP[topic]

        # Step 3: Create dynamic fallback event class
        class_name = re.sub(r"[^0-9a-zA-Z_]+", "_", topic.title())
        if not class_name.endswith("Event"):
            class_name = f"{class_name}Event"
        event_class = type(class_name, (_BaseEventPayload,), {})
        self.EVENT_CLASS_MAP[topic] = event_class
        return event_class

    async def emit(
        self, topic: str, data: Any = None, acknowledgement: bool = False
    ) -> Any:
        """Publish a domain event to all subscribers.

        Processing Steps:
        Step 1: Get event class for the topic
        Step 2: Dispatch event via BuBus
        Step 3: Handle based on acknowledgement mode:
          - acknowledgement=True: Wait for handler results
          - acknowledgement=False: Fire-and-forget with async task

        Args:
            topic: Event topic name
            data: Event payload (optional)
            acknowledgement: If True, wait for handler results (two-way).
                           If False, fire-and-forget (one-way, default)
        """
        if self.trace_calls and self.logger:
            caller_frame = sys._getframe(1)
            await self.logger.debug(
                f"Emitting event {topic}",
                caller_module=caller_frame.f_globals.get("__name__", "unknown"),
                caller_file=caller_frame.f_code.co_filename,
                caller_function=caller_frame.f_code.co_name,
                caller_line=caller_frame.f_lineno,
            )

        event_class = self._get_event_class(topic)
        dispatched = self.bus.dispatch(event_class(data=data))

        if acknowledgement:
            return await dispatched.event_result()
        else:
            return None
            # await dispatched.event_result(raise_if_none=False)

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Any], Any],
    ) -> None:
        """Subscribe to a domain event topic.

        Registers a handler to be called whenever an event is published
        on the given topic. Multiple handlers CAN subscribe to the same topic.

        Processing Steps:
        Step 1: Get event class for the topic
        Step 2: Create wrapper that handles async/sync and payload presence
        Step 3: Register wrapper on BuBus for specific event class

        Args:
            topic: Event topic name (e.g., 'user.excessive_connected_user')
            handler: Async or sync callable to invoke when event published
        """
        if self.trace_calls and self.logger:
            caller_frame = sys._getframe(1)
            await self.logger.debug(
                f"Subscribing handler to event {topic}",
                caller_module=caller_frame.f_globals.get("__name__", "unknown"),
                caller_file=caller_frame.f_code.co_filename,
                caller_function=caller_frame.f_code.co_name,
                caller_line=caller_frame.f_lineno,
                handler_name=getattr(handler, "__name__", repr(handler)),
            )

        event_class = self._get_event_class(topic)

        async def wrapper(event: _BaseEventPayload):
            try:
                if inspect.iscoroutinefunction(handler):
                    if event.data is not None:
                        return await handler(event.data)
                    else:
                        return await handler()
                else:
                    if event.data is not None:
                        return handler(event.data)
                    else:
                        return handler()
            except Exception as e:
                if self.logger:
                    await self.logger.error(
                        f"Event handler raised an exception",
                        topic=topic,
                        handler_name=getattr(handler, "__name__", repr(handler)),
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                raise

        wrapper.__name__ = f"wrapper_{topic}_{id(handler)}"
        self.bus.on(event_class, wrapper)
        # Track so unsubscribe() can remove the exact wrapper later
        self._handler_wrappers[(topic, id(handler))] = wrapper

    async def unsubscribe(self, topic: str, handler: Callable) -> None:
        """Unsubscribe a handler from a topic.

        Looks up the wrapper that was registered on behalf of `handler` during
        subscribe() and removes it from BuBus. This is necessary because BuBus
        tracks wrappers, not original handlers.

        Args:
            topic: Event topic name
            handler: Original handler passed to subscribe()
        """
        key = (topic, id(handler))
        wrapper = self._handler_wrappers.pop(key, None)
        if wrapper is None:
            # Handler was never subscribed or already removed — treat as no-op
            if self.logger:
                await self.logger.debug(
                    "unsubscribe: no wrapper found for handler (already removed or never subscribed)",
                    topic=topic,
                    handler_name=getattr(handler, "__name__", repr(handler)),
                )
            return

        event_class = self._get_event_class(topic)
        event_key = event_class.__name__
        if hasattr(self.bus, 'handlers') and event_key in self.bus.handlers:
            try:
                self.bus.handlers[event_key].remove(wrapper)
            except ValueError:
                pass  # Already removed
