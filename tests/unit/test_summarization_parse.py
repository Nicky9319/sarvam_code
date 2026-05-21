import json

import pytest

from engine.operators.summarization_channel import SummarizationChannel


def _channel() -> SummarizationChannel:
    return SummarizationChannel(logger=None, db_ref=None, http_api_client=None, event_bus=None, worker_count=1)


def test_parse_json_summary():
    ch = _channel()
    raw = json.dumps({"summary": "All tickets relate to billing."})
    assert ch._parse_summarization_response(raw) == "All tickets relate to billing."


def test_parse_plain_text_fallback():
    ch = _channel()
    assert ch._parse_summarization_response("Plain summary sentence.") == "Plain summary sentence."


def test_parse_quoted_string_fallback():
    ch = _channel()
    assert ch._parse_summarization_response('"Quoted summary."') == "Quoted summary."


def test_parse_strips_thinking():
    ch = _channel()
    raw = '<think>t</think>' + json.dumps({"summary": "ok"})
    assert ch._parse_summarization_response(raw) == "ok"


def test_parse_empty_raises():
    ch = _channel()
    with pytest.raises(ValueError, match="empty"):
        ch._parse_summarization_response("   ")
