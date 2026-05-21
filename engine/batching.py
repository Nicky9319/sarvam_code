import os
from dataclasses import dataclass

from engine.constants import DEFAULT_MAX_BATCH_TOKENS


def estimate_tokens(text: str) -> int:
    """Input token estimate: 1 token = 1 character (see README.md)."""
    return max(1, len(text))


@dataclass(frozen=True)
class AdaptiveBatch:
    tickets: list[str]
    ticket_count: int
    estimated_token_count: int


def create_adaptive_batches(
    tickets: list[str],
    max_batch_tokens: int | None = None,
) -> list[AdaptiveBatch]:
    """
    Greedy-pack tickets so estimated input tokens per batch do not exceed max_batch_tokens.
    A single ticket exceeding the limit becomes its own batch.
    """
    if max_batch_tokens is None:
        max_batch_tokens = int(os.getenv("MAX_BATCH_TOKENS", str(DEFAULT_MAX_BATCH_TOKENS)))

    if not tickets:
        return []

    batches: list[AdaptiveBatch] = []
    current: list[str] = []
    current_tokens = 0

    for ticket in tickets:
        ticket_tokens = estimate_tokens(ticket)

        if ticket_tokens > max_batch_tokens:
            if current:
                batches.append(
                    AdaptiveBatch(
                        tickets=current,
                        ticket_count=len(current),
                        estimated_token_count=current_tokens,
                    )
                )
                current = []
                current_tokens = 0
            batches.append(
                AdaptiveBatch(
                    tickets=[ticket],
                    ticket_count=1,
                    estimated_token_count=ticket_tokens,
                )
            )
            continue

        if current and current_tokens + ticket_tokens > max_batch_tokens:
            batches.append(
                AdaptiveBatch(
                    tickets=current,
                    ticket_count=len(current),
                    estimated_token_count=current_tokens,
                )
            )
            current = []
            current_tokens = 0

        current.append(ticket)
        current_tokens += ticket_tokens

    if current:
        batches.append(
            AdaptiveBatch(
                tickets=current,
                ticket_count=len(current),
                estimated_token_count=current_tokens,
            )
        )

    return batches


def estimate_processing_seconds(ticket_count: int, batch_count: int) -> float:
    """Pre-flight duration estimate from Tier 1 baseline throughput."""
    from engine.constants import BASELINE_THROUGHPUT_TICKETS_PER_SEC, SUMMARIZATION_ESTIMATE_SECONDS

    if ticket_count == 0:
        return 0.0
    classification_estimate = ticket_count / BASELINE_THROUGHPUT_TICKETS_PER_SEC
    return classification_estimate + SUMMARIZATION_ESTIMATE_SECONDS
