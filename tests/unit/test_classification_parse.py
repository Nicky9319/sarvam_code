import json

import pytest

from engine.operators.classification_channel import ClassificationChannel


def _channel() -> ClassificationChannel:
    return ClassificationChannel(logger=None, db_ref=None, http_api_client=None, worker_count=1)


def test_parse_valid_json(classification_json_single):
    channel = _channel()
    parsed = channel._parse_classification_response(classification_json_single)
    assert len(parsed.ticket_classifications) == 1
    assert parsed.ticket_classifications[0].category == "hardware_issue"
    assert parsed.summary == "Battery issue."


def test_parse_strips_thinking_blocks():
    channel = _channel()
    raw = (
        '<think>secret</think>'
        + json.dumps(
            {
                "ticket_classifications": [{"ticket_id": "1", "category": "other"}],
                "summary": "s",
            }
        )
    )
    parsed = channel._parse_classification_response(raw)
    assert parsed.ticket_classifications[0].category == "other"


def test_parse_empty_after_thinking_raises():
    channel = _channel()
    with pytest.raises(ValueError, match="empty"):
        channel._parse_classification_response("<think>x</think>")
