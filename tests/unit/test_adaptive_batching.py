import os

import pytest

from engine.batching import create_adaptive_batches, estimate_processing_seconds, estimate_tokens
from engine.constants import BASELINE_THROUGHPUT_TICKETS_PER_SEC, SUMMARIZATION_ESTIMATE_SECONDS


def test_estimate_tokens_minimum_one():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 4


def test_estimate_tokens_scales_with_length():
    text = "a" * 400
    assert estimate_tokens(text) == 400


def test_empty_tickets_returns_empty():
    assert create_adaptive_batches([]) == []


def test_small_tickets_single_batch(monkeypatch):
    monkeypatch.delenv("MAX_BATCH_TOKENS", raising=False)
    tickets = ["short"] * 5
    batches = create_adaptive_batches(tickets, max_batch_tokens=1000)
    assert len(batches) == 1
    assert batches[0].ticket_count == 5
    assert batches[0].estimated_token_count == 5 * estimate_tokens("short")


def test_exceeding_limit_splits_batches():
    ticket = "x" * 1000
    batches = create_adaptive_batches([ticket, ticket], max_batch_tokens=1000)
    assert len(batches) == 2
    assert all(b.ticket_count == 1 for b in batches)


def test_oversized_single_ticket_own_batch():
    ticket = "y" * 5000
    batches = create_adaptive_batches([ticket], max_batch_tokens=1000)
    assert len(batches) == 1
    assert batches[0].ticket_count == 1
    assert batches[0].estimated_token_count > 1000


def test_greedy_packing_order_preserved():
    tickets = ["a", "b", "c"]
    batches = create_adaptive_batches(tickets, max_batch_tokens=10000)
    assert len(batches) == 1
    assert batches[0].tickets == ["a", "b", "c"]


def test_estimate_processing_seconds():
    est = estimate_processing_seconds(50, 5)
    expected = 50 / BASELINE_THROUGHPUT_TICKETS_PER_SEC + SUMMARIZATION_ESTIMATE_SECONDS
    assert est == pytest.approx(expected)


def test_max_batch_tokens_from_env(monkeypatch):
    monkeypatch.setenv("MAX_BATCH_TOKENS", "4")
    ticket = "aaaa"
    batches = create_adaptive_batches([ticket, ticket, ticket], max_batch_tokens=None)
    assert sum(b.ticket_count for b in batches) == 3
    assert len(batches) == 3
