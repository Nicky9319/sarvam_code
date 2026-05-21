import asyncio
from unittest.mock import AsyncMock

import pytest

from engine.event_bus import EventBus
from engine.operators.future_manager import FutureManager


@pytest.fixture
def event_bus():
    return EventBus(logger=AsyncMock())


@pytest.mark.asyncio
async def test_register_and_resolve_via_event(event_bus):
    fm = FutureManager(event_bus=event_bus, logger=AsyncMock())
    await fm.initialize()

    request_id = "req-test-1"
    fm.register(request_id, future_type="classification")

    await fm._on_classification_all_batches_completed(
        {"request_id": request_id, "batch_count": 2},
    )
    result = await fm.wait(request_id, timeout=2.0, future_type="classification")
    assert result == request_id


@pytest.mark.asyncio
async def test_duplicate_register_raises(event_bus):
    fm = FutureManager(event_bus=event_bus, logger=AsyncMock())
    await fm.initialize()
    fm.register("req-dup", future_type="classification")
    with pytest.raises(ValueError, match="already registered"):
        fm.register("req-dup", future_type="classification")


@pytest.mark.asyncio
async def test_wait_without_register_raises(event_bus):
    fm = FutureManager(event_bus=event_bus, logger=AsyncMock())
    await fm.initialize()
    with pytest.raises(KeyError):
        await fm.wait("missing", timeout=0.1, future_type="classification")
