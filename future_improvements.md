# Future Improvements

This document outlines planned improvements and enhancements for the Ticket Pipeline system.

---

## 1. Token-Based Batching

**Current State:** Batches are fixed at 25 tickets per batch regardless of token count.

**Improvement:** Implement token-based batching that groups tickets by total token count rather than ticket count. This would:
- Optimize API usage by packing more tokens per request
- Better utilize the `max_tokens` budget (currently 2000 for classification, 1000 for summarization)
- Reduce total API calls for the same number of tickets

**Why:** The Sarvam free plan has token limits, not ticket limits. Batching by token count would be more efficient.

**Implementation Notes:**
- Need to estimate token count per ticket before classification
- Track cumulative token count when adding tickets to a batch
- Stop adding tickets when `estimated_tokens + current_tokens > max_tokens`

---

## 2. System-Level Batching Optimization

**Current State:** Each API call (classification, summarization) is treated independently. Batching only happens at the individual API level.

**Improvement:** Coordinate batching across all APIs to optimize system throughput:
- Consider overall ticket volume and queue depth when deciding batch sizes
- Dynamic batch sizing based on system load
- Batch classification outputs directly into summarization without separate queue

**Why:** The current approach optimizes individual API calls but not the overall system. A holistic approach could reduce latency and improve throughput.

**Implementation Notes:**
- Introduce a batch orchestrator that knows both queues
- Use adaptive batch sizing based on queue depth
- Consider pipelining classification output to summarization input

---

## 3. Priority Queue for Requests

**Current State:** All requests are processed with equal priority (FIFO via batch number).

**Improvement:** Implement priority-based request processing using the existing `asyncio.PriorityQueue`:
- Allow high-priority requests to jump ahead in the queue
- Support multiple priority levels (e.g., `critical`, `high`, `normal`, `low`)
- API endpoint to specify priority when submitting tickets

**Why:** In production, some requests may be more time-sensitive than others (e.g., urgent customer issues vs. batch processing).

**Implementation Notes:**
- Add `priority` field to `TicketParseRequest` (default: `normal`)
- Modify `ClassificationChannel` to respect priority ordering
- Consider priority inheritance for batches with mixed priority tickets

---

## 4. Polling Mechanism for Long-Running Requests

**Current State:** The API blocks until the request is complete, returning results in the same response.

**Improvement:** Implement an async polling pattern:
1. Client submits request → receives `request_id` immediately
2. Client polls `GET /api/v1/tickets/status/{request_id}` at regular intervals
3. When complete, polling returns results (success, failures, summary)

**Why:**
- **Resilience:** If the server crashes/restarts, client can reconnect and poll for results
- **Cancellation:** Client can cancel the poll but request continues server-side
- **Scalability:** Long-running requests don't hold HTTP connections open
- **UX:** Client can show progress to user while waiting

**Implementation Notes:**
- Store request state and results in MongoDB (already exists)
- New endpoint: `GET /api/v1/tickets/status/{request_id}` returning current state
- Return `completed` with results when done, `processing` when in progress, `failed` on error

---

## 5. Queue Restart / Failure Recovery

**Current State:** If the server crashes, queued jobs are lost and must be resubmitted.

**Improvement:** Implement persistent queue with restart recovery:
- Persist queued jobs to MongoDB before adding to in-memory queue
- On startup, reload pending jobs from MongoDB into the queue
- Implement job acknowledgments to prevent duplicate processing

**Why:**
- **Durability:** Jobs survive server restarts
- **Exactly-once processing:** Prevent double-processing of jobs after restart
- **Audit trail:** Track all queued jobs for debugging

**Implementation Notes:**
- Add `job_state` field to batches: `queued`, `processing`, `completed`, `failed`
- On worker startup, query for `queued` batches and re-add to queue
- Use optimistic locking or job acknowledgments to prevent race conditions

---

## Related Documentation

- [architecture.md](architecture.md) — Current system architecture
- [benchmark.md](benchmark.md) — Performance benchmarks
- [schema.md](schema.md) — Database schema
- [experiment.md](experiment.md) — Benchmarking guide