"""Pipeline-wide constants derived from production benchmarks (see benchmark.md)."""

BASELINE_THROUGHPUT_TICKETS_PER_SEC = 11.0
"""Conservative tickets/s from Tier 1 real Sarvam API runs (peak ~12.76 at 500 tickets)."""

SUMMARIZATION_ESTIMATE_SECONDS = 2.0
"""Fixed overhead added to duration estimates for summarization stage."""

DEFAULT_MAX_BATCH_TOKENS = 1000
"""Max estimated input tokens per classification batch (env: MAX_BATCH_TOKENS)."""

DEFAULT_SARVAM_HTTP_TIMEOUT_SEC = 120.0
"""HTTP timeout for Sarvam OpenAI client (env: SARVAM_HTTP_TIMEOUT)."""
