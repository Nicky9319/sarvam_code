"""Functional integration: parse flow shape with mocked Sarvam and DB coordination."""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.application import TicketPipelineApplication
from engine.batching import create_adaptive_batches
from engine.models.api_request_models import TicketParseRequest
from engine.models.db_models import GetTickerResponsesOutput, TicketResponseOutput


def _classification_response(ticket_ids: list[str]) -> str:
    return json.dumps(
        {
            "ticket_classifications": [
                {"ticket_id": tid, "category": "other"} for tid in ticket_ids
            ],
            "summary": "Batch summary.",
        }
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_adaptive_batches_match_db_metadata():
    """Batches formed for 25 short tickets should carry ticket_count and token metadata."""
    tickets = [f"Ticket {i} short text." for i in range(25)]
    batches = create_adaptive_batches(tickets, max_batch_tokens=1000)
    assert sum(b.ticket_count for b in batches) == 25
    assert all(b.estimated_token_count <= 1000 for b in batches)
    assert all(b.ticket_count > 0 for b in batches)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_processing_estimate_on_empty_request():
    app = TicketPipelineApplication(reducers=None, logger=AsyncMock(), event_bus=None, operators=_mock_operators_empty())
    app.db = AsyncMock()
    app.db.add_request = AsyncMock(return_value=MagicMock(request_id="r1"))

    resp = await app.process_tickets_request(TicketParseRequest(tickets=[]))
    assert resp.processing_estimate is not None
    assert resp.processing_estimate.estimated_batch_count == 0
    assert resp.processing_estimate.estimated_duration_seconds == 0.0


def _mock_operators_empty():
    ops = MagicMock()
    ops.http_api_client.reset_usage_totals = MagicMock()
    ops.http_api_client.get_usage_totals = MagicMock(
        return_value=MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    )
    return ops
