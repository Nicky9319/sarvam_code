from classes.BaseEventBus import BaseEventBus
from typing import Any
import bubus as BuBus


class EventBus(BaseEventBus):
    """EventBus wrapper for Session Supervisor domain events.

    Wraps BuBus for pub/sub event delivery with acknowledgement mode support.
    Inherits emit/subscribe logic from BaseEventBus.

    Architecture:
    - Bottom-up domain-driven: Reducers emit events when state reaches conditions
    - Fire-and-forget dispatch: Non-awaited dispatch() naturally queues events
    - No recursion depth issues: BuBus processes queued events after handler completes
    """

    def __init__(self, logger: Any = None):
        """Initialize EventBus with BuBus instance.

        Args:   
            logger: Optional logger for trace debugging
        """
        super().__init__(logger)
        self.bus = BuBus()

    async def cleanup(self) -> None:
        """Cleanup EventBus. Called during service shutdown."""
        pass
