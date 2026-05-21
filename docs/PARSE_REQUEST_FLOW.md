# Parse Request Flow Documentation

This document describes the complete flow of a ticket parse request through the Sarvam Ticket Pipeline system.

## Overview

The parse request flow handles incoming HTTP requests to classify support tickets into categories (hardware_issue, software_issue, model_quality, billing, other). It uses a worker pool pattern with event-driven completion notification.

**Key Characteristics:**
- Rate limited: 5 requests/minute per client
- Batches tickets into groups of 25 for efficient API calls
- 10 parallel workers process classification requests
- Async coordination via asyncio.Future and EventBus

---

## Sequence Diagram

```mermaid
sequenceDiagram
    participant Client
    participant APIHandler as APIRoutesHandler<br/>(FastAPI)
    participant App as TicketPipelineApplication
    participant DB as DBDatabase<br/>(MongoDB)
    participant FM as FutureManager
    participant Queue as ClassificationChannel<br/>(PriorityQueue)
    participant Worker1 as ClassificationWorker #1
    participant Worker2 as ClassificationWorker #2
    participant WorkerN as ClassificationWorker #N
    participant EB as EventBus
    participant Sarvam as Sarvam API

    Client->>APIHandler: POST /api/v1/tickets/parse
    Note over APIHandler: Rate limited: 5/min

    APIHandler->>App: process_tickets_request(TicketParseRequest)
    App->>DB: add_request(state="classification")
    DB-->>App: request_id (UUID4)
    App->>FM: register(request_id)
    Note over FM: Creates asyncio.Future

    App->>App: create_batches(tickets, batch_size=25)

    loop For each batch
        App->>DB: add_batch(request_id, batch_state="queued")
        DB-->>App: batch_id, batch_number

        loop For each ticket in batch
            App->>DB: add_ticket(request_id, batch_id, content)
            DB-->>App: ticket_id
        end
    end

    App->>Queue: add_batches_jobs_to_queue(batch_ids)
    Note over Queue: Batches added to PriorityQueue

    App->>FM: wait(request_id, timeout=2000s)
    Note over App: BLOCKS HERE until future resolved

    par Workers Process in Parallel
        Worker1->>Queue: get() [priority=batch_number]
        Worker2->>Queue: get() [priority=batch_number]
        WorkerN->>Queue: get() [priority=batch_number]
    end

    loop For each worker
        Worker1->>DB: get_batch_info_and_tickets(batch_id)
        DB-->>Worker1: batch + tickets

        Worker1->>Worker1: _build_sarvam_request()
        Worker1->>Sarvam: POST classification request
        Sarvam-->>Worker1: JSON response (LLM classified)

        Worker1->>Worker1: _parse_classification_response()
        Note over Worker1: Strips thinking blocks

        Worker1->>DB: update_batch(batch_id, state="processed")
    end

    Note over DB: Checks if ALL batches complete

    DB->>EB: emit(CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT)
    EB->>FM: _on_classification_all_batches_completed()
    FM-->>FM: future.set_result(request_id)

    App-->>App: wait() returns
    App->>DB: get_ticket_responses(request_id)
    DB-->>App: ticket responses

    App->>App: _to_parse_response()
    APIHandler-->>Client: TicketParseBatchResponse

    Note over Client: 200 OK<br/>success: [...], failures: [...]
```

---

## Architecture Diagram

```mermaid
flowchart TB

    %% =========================
    %% External Systems
    %% =========================
    subgraph External["External Systems"]
        Client["HTTP Client"]
        SarvamAPI["Sarvam API<br/>(api.sarvam.ai)"]
    end

    %% =========================
    %% Main Orchestrator
    %% =========================
    subgraph Orchestrator["TicketPipeline Orchestrator"]
        direction TB

        EventBus["EventBus<br/>(event_bus.py)"]
        Reducers["TicketPipelineReducers<br/>(reducers.py)"]
        OperatorsLayer["TicketPipelineOperators<br/>(operators.py)"]
        Application["TicketPipelineApplication<br/>(application.py)"]
    end

    %% =========================
    %% Operators Layer
    %% =========================
    subgraph Operators["Operators Layer"]
        direction TB

        APIRoutes["APIRoutesHandler<br/>(FastAPI + Rate Limiter)"]

        HTTPClient["HTTPAPIClient<br/>(Sarvam API Client)"]

        DB["DBDatabase<br/>(MongoDB Wrapper)"]

        ClassChannel["ClassificationChannel<br/>(10 Workers + Queue)"]

        FutureMgr["FutureManager<br/>(request_id → asyncio.Future)"]
    end

    %% =========================
    %% Classification Workers
    %% =========================
    subgraph ClassificationWorkers["ClassificationChannel Internals"]
        direction TB

        Queue["asyncio.PriorityQueue"]

        Worker1["ClassificationWorker #1"]
        Worker2["ClassificationWorker #2"]
        Worker10["ClassificationWorker #10"]
    end

    %% =========================
    %% MongoDB Collections
    %% =========================
    subgraph Database["MongoDB"]
        direction TB

        ReqColl["requests collection"]
        BatchColl["batches collection"]
        TicketColl["tickets collection"]
    end

    %% =========================
    %% Request Flow
    %% =========================
    Client -->|"POST /api/v1/tickets/parse"| APIRoutes

    APIRoutes --> Application

    Application --> DB
    Application --> FutureMgr
    Application --> ClassChannel

    %% =========================
    %% Queue + Workers
    %% =========================
    ClassChannel --> Queue

    Queue --> Worker1
    Queue --> Worker2
    Queue --> Worker10

    %% =========================
    %% Worker → API
    %% =========================
    Worker1 --> HTTPClient
    Worker2 --> HTTPClient
    Worker10 --> HTTPClient

    HTTPClient --> SarvamAPI

    %% =========================
    %% Database Relations
    %% =========================
    DB --> ReqColl
    DB --> BatchColl
    DB --> TicketColl

    ClassChannel --> DB

    %% =========================
    %% Event Flow
    %% =========================
    DB --> EventBus

    EventBus --> Reducers
    EventBus --> FutureMgr

    FutureMgr -.->|"future.set_result()"| Application
```

---

## Classification Worker Pool Diagram

```mermaid
flowchart LR
    subgraph Input
        NewBatch["New Batch<br/>from Application"]
    end

    subgraph Queue["Priority Queue"]
        direction TB
        PQ["asyncio.PriorityQueue"]
        NotePQ["Lower batch_number<br/>= Higher priority"]
    end

    subgraph Workers["10 Classification Workers"]
        direction LR
        W1["Worker 1"]
        W2["Worker 2"]
        W3["Worker 3"]
        W4["Worker 4"]
        W5["Worker 5"]
        W6["Worker 6"]
        W7["Worker 7"]
        W8["Worker 8"]
        W9["Worker 9"]
        W10["Worker 10"]
    end

    subgraph Processing["Per-Worker Processing"]
        direction TB
        Fetch["1. get_batch_info_and_tickets()"]
        Build["2. _build_sarvam_request()"]
        Call["3. send_request_to_sarvam()"]
        Parse["4. _parse_classification_response()"]
        Update["5. update_batch()"]
    end

    subgraph Output["Database Updates"]
        direction TB
        BatchState["batch_state: queued → processed"]
        Tickets["ticket responses updated"]
        Event["EventBus emit if all complete"]
    end

    NewBatch -->|"add_batches_jobs_to_queue()"| PQ
    PQ -->|"get()"| W1
    PQ -->|"get()"| W2
    PQ -->|"get()"| W10
    W1 --> Fetch
    W2 --> Fetch
    W10 --> Fetch
    Fetch --> Build
    Build --> Call
    Call --> Parse
    Parse --> Update
    Update --> BatchState
    Update --> Tickets
    Tickets -->|"if all batches done"| Event
```

---

## State Machine

### Request States

```mermaid
stateDiagram-v2
    [*] --> classification : add_request()
    classification --> [*] : Response sent

    note right of classification
        Initial state for all requests.
        Created in MongoDB requests collection.
    end note
```

### Batch States

```mermaid
stateDiagram-v2
    [*] --> queued : add_batch()
    queued --> processing : Worker picks up batch
    processing --> processed : update_batch() with results

    note right of queued
        Batches waiting in PriorityQueue.
        Worker fetches batch_info_and_tickets.
    end note

    note right of processed
        Classification complete.
        Tickets updated with responses.
    end note
```

### Ticket States

```mermaid
stateDiagram-v2
    [*] --> queued : add_ticket()
    queued --> completed : update_batch() with response
    queued --> failed : update_batch() with failure

    note right of queued
        Tickets are created within a batch.
        Content is the raw ticket description.
    end note

    note right of completed
        response field contains
        classification category.
    end note
```

### Classification Categories

The system classifies tickets into these categories:

| Category | Description |
|----------|-------------|
| `hardware_issue` | Physical equipment problems |
| `software_issue` | Application/software bugs |
| `model_quality` | AI model output issues |
| `billing` | Payment/invoice problems |
| `other` | Doesn't fit other categories |

---

## Component Details

### 1. APIRoutesHandler (`engine/operators/api_routes_handler.py`)

**Purpose:** FastAPI server with rate limiting

**Endpoint:** `POST /api/v1/tickets/parse`

```python
@app.post("/api/v1/tickets/parse", response_model=TicketParseBatchResponse)
@self._limiter.limit("5/minute")
async def parse_tickets(request: Request, body: TicketParseRequest):
    response = await self.application.process_tickets_request(body)
    return response
```

**Rate Limit:** 5 requests per minute per client

**Request Model:** `TicketParseRequest`
```python
class TicketParseRequest(BaseModel):
    tickets: list[TicketInput]  # Max 25 per batch, batches auto-created
```

**Response Model:** `TicketParseBatchResponse`
```python
class TicketParseBatchResponse(BaseModel):
    success: list[TicketParseSuccessItem]  # Classified tickets
    failures: list[str]  # Failed ticket descriptions
```

---

### 2. TicketPipelineApplication (`engine/application.py`)

**Purpose:** Business logic orchestration

**Key Method:** `process_tickets_request()`

```python
async def process_tickets_request(self, request: TicketParseRequest) -> TicketParseBatchResponse:
    # 1. Create request record
    request_output = await self.db.add_request(state="classification", request_id=None)
    request_id = request_output.request_id

    # 2. Register future for this request
    self.operators.future_manager.register(request_id)

    # 3. Create batches (max 25 tickets each)
    batches = await self.create_batches(request.tickets)

    # 4. For each batch: create DB records
    for batch in batches:
        batch_output = await self.db.add_batch(request_id=request_id, ...)
        for ticket in batch:
            await self.db.add_ticket(...)

    # 5. Enqueue batches for classification
    await self.operators.classification_channel.add_batches_jobs_to_queue(batch_ids)

    # 6. Wait for classification to complete
    await self.operators.future_manager.wait(request_id)

    # 7. Get results and return
    tickets_output = await self.db.get_ticket_responses(request_id)
    return self._to_parse_response(tickets_output)
```

---

### 3. ClassificationChannel (`engine/operators/classification_channel.py`)

**Purpose:** Worker pool for async classification processing

**Initialization:**
```python
async def initialize(self):
    self._classification_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
    self._worker_tasks = [asyncio.create_task(self.classification_worker()) for i in range(10)]
```

**Worker Loop:**
```python
async def classification_worker(self):
    while True:
        _, batch_id = await self._classification_queue.get()

        # Fetch batch and tickets from DB
        batch_info_and_tickets = await self._db_ref.get_batch_info_and_tickets(batch_id)

        # Build request to Sarvam
        classification_input = ClassificationRequestMessageInputModel(
            tickets=[TickerInformation(ticket_id=t.ticket_id, description=t.content) for t in tickets]
        )

        # Call Sarvam API with retry (3 attempts, exponential backoff)
        classification_response = await self.invoke_sarvam_for_classification(classification_input)

        # Parse response (strips thinking blocks)
        parsed = self._parse_classification_response(classification_response)

        # Update batch and tickets in DB
        await self._db_ref.update_batch(UpdateBatchInput(
            batch_id=batch_id,
            batch_state="processed",
            batch_summary=parsed.summary,
            ticket_updates=[TicketUpdateItem(ticket_id=item.ticket_id, state="completed", response=item.category) ...]
        ))
```

**Sarvam Request Format:**
```python
SarvamAPIRequest(
    model="sarvam-m",
    max_tokens=2000,
    messages=[
        SarvamMessages(role="system", content=classification_job_system_message),
        SarvamMessages(role="user", content=json.dumps([t.model_dump() for t in classification_input.tickets]))
    ]
)
```

**System Prompt:** Instructs LLM to classify into: hardware_issue, software_issue, model_quality, billing, other

---

### 4. FutureManager (`engine/operators/future_manager.py`)

**Purpose:** Maps request_id to asyncio.Future for async coordination

**Key Methods:**

```python
class FutureManager:
    def register(self, request_id: str) -> asyncio.Future[str]:
        """Create a new future for this request"""
        future = loop.create_future()
        self._futures[request_id] = future
        return future

    async def wait(self, request_id: str, timeout: float = 2000) -> str:
        """Block until future is resolved"""
        return await asyncio.wait_for(self._futures[request_id], timeout=timeout)

    async def _on_classification_all_batches_completed(self, data: Any) -> None:
        """EventBus callback - resolves the future"""
        payload = ClassificationAllBatchesCompletedPayload.model_validate(data)
        future = self._futures.get(payload.request_id)
        future.set_result(payload.request_id)
```

**Event Subscription:**
```python
async def initialize(self):
    await self._event_bus.subscribe(
        CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
        self._on_classification_all_batches_completed,
    )
```

---

### 5. EventBus (`engine/event_bus.py`)

**Purpose:** Pub/sub for domain events

**Key Event:** `CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT`

**Emission Point** (`engine/operators/db/db.py`):
```python
async def update_batch(self, input: UpdateBatchInput) -> None:
    # ... update logic ...

    # Check if all batches complete
    batches_completed = await self.get_all_batches_completed(request_id)
    if batches_completed.completed and self._event_bus is not None:
        await self._event_bus.emit(
            CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
            data=ClassificationAllBatchesCompletedPayload(
                request_id=request_id,
                batch_count=batch_count,
            ).model_dump(),
        )
```

**Payload:**
```python
class ClassificationAllBatchesCompletedPayload(BaseModel):
    request_id: str
    batch_count: int
```

---

### 6. DBDatabase (`engine/operators/db/db.py`)

**Purpose:** MongoDB wrapper with schema validation

**Collections:**
- `requests` - Parse requests
- `batches` - Batches of tickets
- `tickets` - Individual ticket records

**Key Methods:**

| Method | Description |
|--------|-------------|
| `add_request()` | Create request record |
| `add_batch()` | Create batch record |
| `add_ticket()` | Create ticket record |
| `get_batch_info_and_tickets()` | Fetch batch + tickets for processing |
| `update_batch()` | Update batch state and ticket responses |
| `get_all_batches_completed()` | Check if all batches for request are processed |
| `get_ticket_responses()` | Get all tickets with their responses |

**Schema Validation:** Auto-applied from `schema.json` on initialization

---

## API Reference

### POST /api/v1/tickets/parse

**Request:**
```json
{
  "tickets": [
    {
      "description": "My screen is flickering when I connect to the projector"
    },
    {
      "description": "The billing amount seems incorrect for last month"
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "success": [
    {
      "description": "My screen is flickering when I connect to the projector",
      "classification": "hardware_issue"
    }
  ],
  "failures": []
}
```

**Response with Failures (200 OK):**
```json
{
  "success": [],
  "failures": [
    "The billing amount seems incorrect for last month"
  ]
}
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Sarvam API timeout | Retry 3 times with exponential backoff |
| Invalid response format | Log error, mark ticket as failure |
| All batches timeout (>2000s) | Raise asyncio.TimeoutError |
| Rate limit exceeded | Return 429 Too Many Requests |
| MongoDB connection failure | Raise connection exception |

---

## File Structure

```
engine/
├── main.py                          # Entry point
├── orchestrator.py                  # TicketPipeline - component wiring
├── application.py                   # TicketPipelineApplication - business logic
├── event_bus.py                     # EventBus - pub/sub
├── reducers.py                      # TicketPipelineReducers - state management
├── models/
│   ├── api_request_models.py        # HTTP request/response models
│   ├── classification_models.py     # Classification request/response
│   ├── db_models.py                 # Database models
│   └── http_client_models.py        # HTTP client models
└── operators/
    ├── operators.py                 # TicketPipelineOperators - composition
    ├── api_routes_handler.py        # FastAPI server + rate limiting
    ├── classification_channel.py    # Worker pool
    ├── future_manager.py            # Future coordination
    └── db/
        ├── db.py                    # DBDatabase - MongoDB wrapper
        └── schema.json              # Schema validation
```

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SARVAM_API_KEY` | - | Required. API key for Sarvam AI |
| `SARVAM_BASE_URL` | `https://api.sarvam.ai/v1` | Sarvam API base URL |
| `MONGO_HOST` | `localhost` | MongoDB host |
| `MONGO_PORT` | `27017` | MongoDB port |
| `WORKER_COUNT` | `10` | Number of classification workers |
| `BATCH_SIZE` | `25` | Max tickets per batch |
| `RATE_LIMIT` | `5/minute` | API rate limit |
| `FUTURE_TIMEOUT` | `2000s` | Max wait time for classification |