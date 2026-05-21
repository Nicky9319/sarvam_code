import asyncio
from typing import Any, Optional

from classes.Logger.logger import LogSidecar
from engine.event_bus import (
    CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
    ClassificationAllBatchesCompletedPayload,
    EventBus,
)


class FutureManager:
    """Maps request_id to asyncio.Future; resolves on classification_all_batches_completed."""

    def __init__(self, event_bus: EventBus, logger: LogSidecar) -> None:
        self._event_bus = event_bus
        self._logger = logger
        self._futures: dict[str, asyncio.Future[str]] = {}

    async def initialize(self) -> None:
        await self._event_bus.subscribe(
            CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
            self._on_classification_all_batches_completed,
        )
        await self._logger.info("FutureManager subscribed to classification_all_batches_completed")

    def register(self, request_id: str) -> asyncio.Future[str]:
        if request_id in self._futures:
            raise ValueError(f"Future already registered for request_id={request_id}")

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._futures[request_id] = future
        return future

    async def wait(self, request_id: str, timeout: Optional[float] = 2000) -> str:
        future = self._futures.get(request_id)
        if future is None:
            raise KeyError(f"No future registered for request_id={request_id}")

        try:
            if timeout is not None:
                return await asyncio.wait_for(future, timeout=timeout)
            return await future
        finally: 
            await self._logger.info(
                "Future resolved",
                request_id=request_id,
            )
            self._futures.pop(request_id, None)

    async def _on_classification_all_batches_completed(self, data: Any) -> None:
        payload = ClassificationAllBatchesCompletedPayload.model_validate(data)
        request_id = payload.request_id

        future = self._futures.get(request_id)
        if future is None:
            await self._logger.debug(
                "No pending future for classification completion event",
                request_id=request_id,
            )
            return

        if future.done():
            await self._logger.debug(
                "Future already resolved for classification completion event",
                request_id=request_id,
            )
            return

        future.set_result(request_id)
        await self._logger.info(
            "Resolved classification future",
            request_id=request_id,
            batch_count=payload.batch_count,
        )

    async def cleanup(self) -> None:
        for request_id, future in list(self._futures.items()):
            if not future.done():
                future.cancel()
        self._futures.clear()
