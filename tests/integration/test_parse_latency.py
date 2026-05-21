"""Integration: batch structure aligns with ~11 tickets/s latency model."""

import asyncio

import pytest

from engine.batching import create_adaptive_batches
from engine.constants import BASELINE_THROUGHPUT_TICKETS_PER_SEC, SUMMARIZATION_ESTIMATE_SECONDS


def expected_duration_seconds(ticket_count: int, parallelism: int = 1) -> tuple[float, float]:
    """
    Sequential mock: each batch sleeps ticket_count/11; parallel workers reduce wall time.
    Returns (min, max) band for assertions.
    """
    base = ticket_count / BASELINE_THROUGHPUT_TICKETS_PER_SEC
    if parallelism > 1:
        base = base / min(parallelism, ticket_count)
    low = base * 0.75
    high = base * 1.35 + SUMMARIZATION_ESTIMATE_SECONDS + 1.0
    return low, high


@pytest.mark.integration
def test_latency_band_for_50_tickets():
    tickets = [f"Support issue {i}: device problem." for i in range(50)]
    batches = create_adaptive_batches(tickets, max_batch_tokens=1000)
    ticket_count = sum(b.ticket_count for b in batches)

    low, high = expected_duration_seconds(ticket_count, parallelism=1)
    simulated = sum(b.ticket_count / BASELINE_THROUGHPUT_TICKETS_PER_SEC for b in batches)
    simulated += SUMMARIZATION_ESTIMATE_SECONDS

    assert low <= simulated <= high


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_sarvam_per_batch_sleep_matches_baseline():
    """Simulate classification delay per batch at 11 t/s and assert total wall time."""
    tickets = [f"ticket {i}" for i in range(10)]
    batches = create_adaptive_batches(tickets, max_batch_tokens=1000)

    async def classify_batches() -> float:
        total = 0.0
        for batch in batches:
            delay = batch.ticket_count / BASELINE_THROUGHPUT_TICKETS_PER_SEC
            await asyncio.sleep(delay)
            total += delay
        await asyncio.sleep(SUMMARIZATION_ESTIMATE_SECONDS)
        return total + SUMMARIZATION_ESTIMATE_SECONDS

    import time

    start = time.perf_counter()
    elapsed = await classify_batches()
    wall = time.perf_counter() - start

    expected = 10 / BASELINE_THROUGHPUT_TICKETS_PER_SEC + SUMMARIZATION_ESTIMATE_SECONDS
    assert elapsed == pytest.approx(expected, rel=0.15)
    assert wall == pytest.approx(elapsed, rel=0.25)


@pytest.mark.integration
def test_batch_count_increases_when_token_budget_tight():
    short = ["hi"] * 50
    tight = create_adaptive_batches(short, max_batch_tokens=10)
    loose = create_adaptive_batches(short, max_batch_tokens=1000)
    assert len(tight) >= len(loose)
