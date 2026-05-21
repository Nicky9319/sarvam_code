"""Ticket Pipeline Engine Event Bus — BuBus wrapper for domain event pub/sub.

Wraps BuBus for domain event pub/sub.
Inherits from BaseEventBus for common dispatch logic.

Domain Event Topics:
- classification_all_batches_completed: All batches for a request finished classification
"""

from typing import Any

from pydantic import BaseModel, Field

from classes.BaseEventBus.base_event_bus import BaseEventBus, _BaseEventPayload

# ============================================================================
# DOMAIN EVENT TOPICS (Constants for consistency)
# ============================================================================
CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT = "classification_all_batches_completed"
SUMMARIZATION_ALL_BATCHES_COMPLETED_EVENT = "summarization_all_batches_completed"


class ClassificationAllBatchesCompletedPayload(BaseModel):
    """Payload emitted when every batch for a request reaches processed state."""

    request_id: str = Field(description="Request whose batches are all processed")
    batch_count: int = Field(description="Total batches processed for this request")


class ClassificationAllBatchesCompletedEvent(_BaseEventPayload):
    """Event emitted when all batches for a request complete classification."""


class SummarizationAllBatchesCompletedPayload(BaseModel):
    """Payload emitted when summarization completes for a request."""

    request_id: str = Field(description="Request whose summarization is complete")
    summary: str = Field(description="The final consolidated summary")


class SummarizationAllBatchesCompletedEvent(_BaseEventPayload):
    """Event emitted when all batches for a request complete summarization."""


# ============================================================================
# TOPIC TO EVENT CLASS REGISTRY
# ============================================================================

EVENT_CLASS_MAP = {
    CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT: ClassificationAllBatchesCompletedEvent,
    SUMMARIZATION_ALL_BATCHES_COMPLETED_EVENT: SummarizationAllBatchesCompletedEvent,
}


class EventBus(BaseEventBus):
    """Event Bus — BuBus wrapper for ticket pipeline domain events.

    Manages subscriptions and publishes domain events that other
    components can listen to without direct coupling.

    Inherits emit/subscribe logic from BaseEventBus.

    Event topics follow the pattern:
    - Noun-verb: "classification_all_batches_completed"
    - One topic per discrete event type
    """

    EVENT_CLASS_MAP = EVENT_CLASS_MAP

    def __init__(self, logger: Any = None) -> None:
        """Initialize EventBus with BuBus instance.

        Args:
            logger: Optional logger for trace debugging
        """
        super().__init__(logger)

    async def cleanup(self) -> None:
        """Cleanup EventBus. Called during service shutdown."""
        await super().cleanup()
        if self.logger:
            await self.logger.debug("EventBus cleanup — all subscriptions cleared")
