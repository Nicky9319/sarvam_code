"""Tier 2 load benchmark helpers (optional live runs)."""

import pytest

from engine.constants import BASELINE_THROUGHPUT_TICKETS_PER_SEC


@pytest.mark.load
def test_aggregate_throughput_formula():
    """Documented formula used in Tier 2 load tables."""
    per_request_durations = [4.0, 5.0, 6.0]
    ticket_counts = [1, 25, 50]
    total_tickets = sum(ticket_counts)
    wall = max(per_request_durations)
    aggregate = total_tickets / wall
    assert aggregate > 0
    assert BASELINE_THROUGHPUT_TICKETS_PER_SEC == 11.0
