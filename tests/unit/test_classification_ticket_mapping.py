import json
from unittest.mock import AsyncMock

import pytest

from engine.models.classification_models import ClassificationResponseModel, TicketClassificationResult
from engine.operators.classification_channel import ClassificationChannel
from tests.conftest import make_ticket_record


@pytest.fixture
def channel():
    ch = ClassificationChannel(logger=AsyncMock(), db_ref=None, http_api_client=None, worker_count=1)
    return ch


@pytest.mark.asyncio
async def test_exact_id_match(channel):
    tickets = [
        make_ticket_record("1", "a", "queued", None),
        make_ticket_record("2", "b", "queued", None),
    ]
    parsed = ClassificationResponseModel(
        ticket_classifications=[
            TicketClassificationResult(ticket_id="1", category="hardware_issue"),
            TicketClassificationResult(ticket_id="2", category="billing"),
        ],
        summary="ok",
    )
    updates = await channel._build_ticket_updates(tickets, parsed, "batch-1")
    assert len(updates) == 2
    assert all(u.state == "completed" for u in updates)
    assert updates[0].response == "hardware_issue"


@pytest.mark.asyncio
async def test_single_ticket_fallback(channel):
    tickets = [make_ticket_record("1", "only", "queued", None)]
    parsed = ClassificationResponseModel(
        ticket_classifications=[TicketClassificationResult(ticket_id="wrong", category="other")],
        summary="s",
    )
    updates = await channel._build_ticket_updates(tickets, parsed, "batch-1")
    assert updates[0].state == "completed"
    assert updates[0].response == "other"


@pytest.mark.asyncio
async def test_index_order_fallback(channel):
    tickets = [
        make_ticket_record("1", "a", "queued", None),
        make_ticket_record("2", "b", "queued", None),
    ]
    parsed = ClassificationResponseModel(
        ticket_classifications=[
            TicketClassificationResult(ticket_id="x", category="software_issue"),
            TicketClassificationResult(ticket_id="y", category="billing"),
        ],
        summary="s",
    )
    updates = await channel._build_ticket_updates(tickets, parsed, "batch-1")
    assert updates[0].response == "software_issue"
    assert updates[1].response == "billing"


@pytest.mark.asyncio
async def test_unmapped_ticket_failed(channel):
    tickets = [
        make_ticket_record("1", "a", "queued", None),
        make_ticket_record("2", "b", "queued", None),
    ]
    parsed = ClassificationResponseModel(
        ticket_classifications=[TicketClassificationResult(ticket_id="1", category="other")],
        summary="s",
    )
    updates = await channel._build_ticket_updates(tickets, parsed, "batch-1")
    by_id = {u.ticket_id: u for u in updates}
    assert by_id["1"].state == "completed"
    assert by_id["2"].state == "failed"
