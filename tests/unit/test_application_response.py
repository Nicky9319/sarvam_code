from engine.application import TicketPipelineApplication
from tests.conftest import make_ticket_record, make_tickets_output


def _app() -> TicketPipelineApplication:
    return TicketPipelineApplication(reducers=None, logger=None, event_bus=None, operators=None)


def test_get_success_items_only_completed():
    app = _app()
    output = make_tickets_output(
        [
            make_ticket_record("1", "ok", "completed", "hardware_issue"),
            make_ticket_record("2", "bad", "failed", None),
        ]
    )
    success = app._get_success_items(output)
    assert len(success) == 1
    assert success[0].ticket_id == "1"
    assert success[0].classification == "hardware_issue"


def test_get_failure_items_non_completed():
    app = _app()
    output = make_tickets_output(
        [
            make_ticket_record("1", "ok", "completed"),
            make_ticket_record("2", "fail text", "failed"),
        ]
    )
    failures = app._get_failure_items(output)
    assert failures == ["fail text"]


def test_to_parse_response_includes_estimate():
    app = _app()
    from engine.models.api_request_models import ProcessingEstimate

    output = make_tickets_output([make_ticket_record()])
    response = app._to_parse_response(
        output,
        summary="Done",
        duration_seconds=1.5,
        processing_estimate=ProcessingEstimate(estimated_batch_count=2, estimated_duration_seconds=10.0),
    )
    assert response.summary == "Done"
    assert response.duration_seconds == 1.5
    assert response.processing_estimate.estimated_batch_count == 2
    assert response.total == 1
