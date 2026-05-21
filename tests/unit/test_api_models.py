import pytest
from pydantic import ValidationError

from engine.models.api_request_models import ProcessingEstimate, TicketParseBatchResponse, TicketParseRequest


def test_ticket_parse_request_max_500():
    with pytest.raises(ValidationError):
        TicketParseRequest(tickets=["t"] * 501)


def test_ticket_parse_request_accepts_500():
    req = TicketParseRequest(tickets=["t"] * 500)
    assert len(req.tickets) == 500


def test_batch_response_computed_fields():
    resp = TicketParseBatchResponse(
        success=[],
        failures=["a", "b"],
        processing_estimate=ProcessingEstimate(estimated_batch_count=1, estimated_duration_seconds=5.0),
    )
    assert resp.total == 2
    assert resp.failure_count == 2
    assert resp.success_count == 0
