import json
from datetime import datetime, timezone

import pytest

from engine.constants import BASELINE_THROUGHPUT_TICKETS_PER_SEC
from engine.models.db_models import GetTickerResponsesOutput, TicketRecord, TicketResponseOutput

pytest_plugins = []


@pytest.fixture
def baseline_throughput():
    return BASELINE_THROUGHPUT_TICKETS_PER_SEC


def make_ticket_record(
    ticket_id: str = "1",
    content: str = "test",
    state: str = "completed",
    response: str | None = "hardware_issue",
) -> TicketRecord:
    now = datetime.now(timezone.utc)
    return TicketRecord(
        ticket_id=ticket_id,
        request_id="req-1",
        batch_id="batch-1",
        content=content,
        state=state,
        batch_number=1,
        response=response,
        createdAt=now,
        updatedAt=now,
    )


def make_tickets_output(records: list[TicketRecord]) -> GetTickerResponsesOutput:
    return GetTickerResponsesOutput(
        responses=[
            TicketResponseOutput(
                ticket_id=r.ticket_id,
                content=r.content,
                state=r.state,
                response=r.response,
                batch_number=r.batch_number,
            )
            for r in records
        ]
    )


@pytest.fixture
def classification_json_single():
    return json.dumps(
        {
            "ticket_classifications": [{"ticket_id": "1", "category": "hardware_issue"}],
            "summary": "Battery issue.",
        }
    )


@pytest.fixture
def classification_json_multi():
    return json.dumps(
        {
            "ticket_classifications": [
                {"ticket_id": "1", "category": "hardware_issue"},
                {"ticket_id": "2", "category": "billing"},
            ],
            "summary": "Mixed issues.",
        }
    )
