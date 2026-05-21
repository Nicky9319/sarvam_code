import asyncio
from typing import Any, Optional

from classes.Logger.logger import LogSidecar
from engine.event_bus import (
    CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
    SUMMARIZATION_ALL_BATCHES_COMPLETED_EVENT,
    ClassificationAllBatchesCompletedPayload,
    EventBus,
    SummarizationAllBatchesCompletedPayload,
)


class FutureManager:
    """Maps request_id to asyncio.Future; resolves on classification_all_batches_completed or summarization_all_batches_completed."""

    def __init__(self, event_bus: EventBus, logger: LogSidecar) -> None:
        self._event_bus = event_bus
        self._logger = logger
        self._classification_futures: dict[str, asyncio.Future[str]] = {}
        self._summarization_futures: dict[str, asyncio.Future[str]] = {}

    async def initialize(self) -> None:
        await self._event_bus.subscribe(
            CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
            self._on_classification_all_batches_completed,
        )
        await self._event_bus.subscribe(
            SUMMARIZATION_ALL_BATCHES_COMPLETED_EVENT,
            self._on_summarization_all_batches_completed,
        )
        await self._logger.info("FutureManager subscribed to classification and summarization events")

    def register(self, request_id: str, future_type: str = "classification") -> asyncio.Future[str]:
        """Register a future for a request. future_type is 'classification' or 'summarization'."""
        if future_type == "classification":
            if request_id in self._classification_futures:
                raise ValueError(f"Classification future already registered for request_id={request_id}")
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._classification_futures[request_id] = future
            return future
        elif future_type == "summarization":
            if request_id in self._summarization_futures:
                raise ValueError(f"Summarization future already registered for request_id={request_id}")
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._summarization_futures[request_id] = future
            return future
        else:
            raise ValueError(f"Unknown future_type: {future_type}. Use 'classification' or 'summarization'.")

    async def wait(self, request_id: str, timeout: Optional[float] = 2000, future_type: str = "classification") -> str:
        """Wait for a future to resolve. future_type is 'classification' or 'summarization'."""
        if future_type == "classification":
            future = self._classification_futures.get(request_id)
        elif future_type == "summarization":
            future = self._summarization_futures.get(request_id)
        else:
            raise ValueError(f"Unknown future_type: {future_type}. Use 'classification' or 'summarization'.")

        if future is None:
            raise KeyError(f"No {future_type} future registered for request_id={request_id}")

        try:
            if timeout is not None:
                return await asyncio.wait_for(future, timeout=timeout)
            return await future
        finally:
            await self._logger.info(
                f"{future_type.capitalize()} future resolved",
                request_id=request_id,
            )
            if future_type == "classification":
                self._classification_futures.pop(request_id, None)
            else:
                self._summarization_futures.pop(request_id, None)

    async def _on_classification_all_batches_completed(self, data: Any) -> None:
        payload = ClassificationAllBatchesCompletedPayload.model_validate(data)
        request_id = payload.request_id

        future = self._classification_futures.get(request_id)
        if future is None:
            await self._logger.debug(
                "No pending classification future for event",
                request_id=request_id,
            )
            return

        if future.done():
            await self._logger.debug(
                "Classification future already resolved",
                request_id=request_id,
            )
            return

        future.set_result(request_id)
        await self._logger.info(
            "Resolved classification future",
            request_id=request_id,
            batch_count=payload.batch_count,
        )

    async def _on_summarization_all_batches_completed(self, data: Any) -> None:
        payload = SummarizationAllBatchesCompletedPayload.model_validate(data)
        request_id = payload.request_id

        future = self._summarization_futures.get(request_id)
        if future is None:
            await self._logger.debug(
                "No pending summarization future for event",
                request_id=request_id,
            )
            return

        if future.done():
            await self._logger.debug(
                "Summarization future already resolved",
                request_id=request_id,
            )
            return

        future.set_result(request_id)
        await self._logger.info(
            "Resolved summarization future",
            request_id=request_id,
            summary_length=len(payload.summary),
        )

    async def cleanup(self) -> None:
        for request_id, future in list(self._classification_futures.items()):
            if not future.done():
                future.cancel()
        self._classification_futures.clear()

        for request_id, future in list(self._summarization_futures.items()):
            if not future.done():
                future.cancel()
        self._summarization_futures.clear()
