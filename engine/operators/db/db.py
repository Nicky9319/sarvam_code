import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from pymongo import MongoClient
from engine.event_bus import (
    CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
    ClassificationAllBatchesCompletedPayload,
    EventBus,
)
from engine.models.db_models import (
    AddBatchOutput,
    AddRequestOutput,
    AddTicketOutput,
    BatchRecord,
    GetAllBatchesCompletedOutput,
    GetBatchInfoAndTicketsOutput,
    GetTickerResponsesOutput,
    TicketRecord,
    TicketResponseOutput,
    UpdateBatchInput,
    UpdateBatchOutput,
)
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import CollectionInvalid, PyMongoError

from classes.Logger.logger import LogSidecar


class DBDatabase:
    """
    MongoDB service wrapper that manages multiple databases.
    Auto-creates collections with schema validation on initialization.

    Usage:
        db = DBDatabase(host="localhost", port=27017, logger=logger)
        await db.initialize()

        request_output = await db.add_request()
        batch_output = await db.add_batch(request_output.request_id)
        ticket_output = await db.add_ticket(
            request_output.request_id,
            batch_output.batch_id,
            "ticket content",
            batch_output.batch_number,
        )

        completed = await db.get_all_batches_completed(request_output.request_id)
        responses = await db.get_ticker_responses(request_output.request_id)
    """

    DEFAULT_DATABASE = "ticket_pipeline"

    def __init__(
        self,
        host: str,
        port: int,
        logger: LogSidecar,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._logger: LogSidecar = logger
        self._event_bus = event_bus
        self._client: Optional[MongoClient] = None

        # Database references (created dynamically)
        self._databases: Dict[str, Database] = {}

        # Schema path for auto-creation
        self._schema_path = os.path.join(os.path.dirname(__file__), "schema.json")

        # Set logging level to DEBUG
        self._logger.set_level("DEBUG")

    async def initialize(self) -> None:
        """
        Initialize MongoDB connection and auto-create collections from schema.

        This method connects to MongoDB and creates collections with JSON schema
        validation based on schema.json.

        Processing Steps:
        Step 1: Establish MongoDB client connection
        Step 2: Auto-create collections from schema.json validators
        """
        try:
            await self._logger.info(
                "Function started",
                host=self._host,
                port=self._port
            )

            self._client = MongoClient(
                host=self._host,
                port=self._port,
            )

            await self._logger.debug(
                "MongoDB client created",
                host=self._host,
                port=self._port
            )

            await self._create_collections_from_schema()

            await self._logger.info(
                "Function ended successfully"
            )

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def initialize_async(self) -> None:
        """Async alias for initialize."""
        await self.initialize()

    async def cleanup(self) -> None:
        """
        Close MongoDB client connection and clear database references.

        Processing Steps:
        Step 1: Close MongoDB client connection
        Step 2: Clear database references
        """
        try:
            await self._logger.info("Function started")

            if self._client:
                self._client.close()
                self._client = None
                await self._logger.debug("MongoDB client closed")

            self._databases.clear()

            await self._logger.info("Function ended successfully")

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    @property
    def is_initialized(self) -> bool:
        return self._client is not None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _load_schema(self) -> Dict[str, Any]:
        with open(self._schema_path, 'r') as f:
            return json.load(f)

    def _get_database(self, db_name: str) -> Database:
        """Get or create a database reference."""
        if db_name not in self._databases:
            self._databases[db_name] = self._client[db_name]
        return self._databases[db_name]

    def _db(self) -> Database:
        """Shorthand for default database."""
        return self._get_database(self.DEFAULT_DATABASE)

    async def _create_collections_from_schema(self) -> None:
        """
        Create collections based on schema.json validators.

        Processing Steps:
        Step 1: Load schema from schema.json
        Step 2: For each database and collection, create if not exists
        Step 3: Apply JSON schema validation to each collection
        """
        try:
            await self._logger.info("Function started")

            schema_data = self._load_schema()
            await self._logger.debug("Schema loaded", schema_path=self._schema_path)

            # Support both formats: {"database": "...", "collections": [...]} and {"databases": {...}}
            if "databases" in schema_data:
                databases_config = schema_data.get("databases", {})
                for db_name, collections in databases_config.items():
                    db = self._get_database(db_name)
                    await self._apply_collections(db, collections, db_name)
            else:
                # Simpler format: single database with "database" and "collections" keys
                db_name = schema_data.get("database", self.DEFAULT_DATABASE)
                db = self._get_database(db_name)
                await self._apply_collections(db, schema_data.get("collections", []), db_name)

            await self._logger.info("Function ended successfully")

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def _apply_collections(self, db: Database, collections: List[Dict[str, Any]], db_name: str) -> None:
        """
        Apply collection schemas to a database.

        Processing Steps:
        Step 1: Iterate through each collection config
        Step 2: Create collection if not exists
        Step 3: Apply JSON schema validation via collMod
        """
        try:
            await self._logger.debug("Applying collections", db_name=db_name, count=len(collections))

            for collection_info in collections:
                collection_name = collection_info["name"]

                try:
                    # Check if collection exists
                    if collection_name not in db.list_collection_names():
                        db.create_collection(collection_name)
                        await self._logger.info(f"Created collection: {db_name}.{collection_name}")

                    # Apply schema validation
                    db.command({
                        'collMod': collection_name,
                        'validator': collection_info["validator"],
                        'validationLevel': collection_info.get("validationLevel", "strict"),
                        'validationAction': collection_info.get("validationAction", "error")
                    })
                    await self._logger.debug(f"Applied schema validation to: {db_name}.{collection_name}")

                except Exception as e:
                    await self._logger.error(
                        "Error applying collection schema",
                        collection=f"{db_name}.{collection_name}",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    raise

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    @property
    def client(self) -> MongoClient:
        if not self._client:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._client

    # Collection references
    @property
    def requests_collection(self) -> Collection:
        return self._db()["requests"]

    @property
    def batches_collection(self) -> Collection:
        return self._db()["batches"]

    @property
    def tickets_collection(self) -> Collection:
        return self._db()["tickets"]

    # Request operations
    async def add_request(
        self,
        state: str = "classification",
        response_summary: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> AddRequestOutput:
        """
        Add a new request record.

        This function creates a new request in the requests collection with
        auto-generated UUID4 if request_id not provided.

        Processing Steps:
        Step 1: Generate UUID4 for request_id if not provided
        Step 2: Create document with timestamps
        Step 3: Insert into requests collection
        """
        try:
            await self._logger.info(
                "Function started",
                state=state,
                request_id=request_id
            )

            if request_id is None:
                request_id = str(uuid.uuid4())
                await self._logger.debug("Generated new request_id", request_id=request_id)

            now = self._now()
            doc = {
                "request_id": request_id,
                "state": state,
                "response_summary": response_summary,
                "createdAt": now,
                "updatedAt": now,
            }

            await self._logger.debug("Inserting request document", request_id=request_id)

            try:
                self.requests_collection.insert_one(doc)
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB insert failed",
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.info(
                "Function ended successfully",
                request_id=request_id,
                state=state
            )
            return AddRequestOutput(request_id=request_id)

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def update_request(self, request_id: str, **kwargs) -> None:
        """
        Update a request record.

        Processing Steps:
        Step 1: Build update document with updatedAt timestamp
        Step 2: Update the request document in collection
        """
        try:
            await self._logger.info(
                "Function started",
                request_id=request_id,
                fields=list(kwargs.keys())
            )

            update = {**kwargs, "updatedAt": self._now()}

            try:
                result = self.requests_collection.update_one(
                    {"request_id": request_id},
                    {"$set": update}
                )
                await self._logger.debug(
                    "Update completed",
                    request_id=request_id,
                    matched_count=result.matched_count
                )
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB update failed",
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.info("Function ended successfully")

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    # Batch operations
    async def add_batch(
        self,
        request_id: str,
        batch_state: str = "queued",
        batch_summary: Optional[str] = None,
    ) -> AddBatchOutput:
        """
        Add a new batch record.

        This function creates a new batch in the batches collection with
        auto-incremented batch_number for the given request_id.

        Processing Steps:
        Step 1: Count existing batches for request_id
        Step 2: Calculate next batch_number
        Step 3: Create document with timestamps
        Step 4: Insert into batches collection
        """
        try:
            await self._logger.info(
                "Function started",
                request_id=request_id,
                batch_state=batch_state
            )

            # Get next batch number for this request
            try:
                existing = self.batches_collection.count_documents({"request_id": request_id})
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB count failed",
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            batch_number = existing + 1
            batch_id = str(uuid.uuid4())
            await self._logger.debug(
                "Calculated next batch_number",
                request_id=request_id,
                batch_number=batch_number,
                batch_id=batch_id,
            )

            now = self._now()
            doc = {
                "batch_id": batch_id,
                "batch_number": batch_number,
                "request_id": request_id,
                "batch_state": batch_state,
                "batch_summary": batch_summary,
                "createdAt": now,
                "updatedAt": now,
            }

            await self._logger.debug("Inserting batch document", batch_number=batch_number)

            try:
                self.batches_collection.insert_one(doc)
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB insert failed",
                    batch_number=batch_number,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.info(
                "Function ended successfully",
                batch_id=batch_id,
                batch_number=batch_number,
                request_id=request_id
            )
            return AddBatchOutput(batch_id=batch_id, batch_number=batch_number)

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def update_batch(self, update: UpdateBatchInput) -> UpdateBatchOutput:
        """
        Update a batch and its tickets after classification.

        Processing Steps:
        Step 1: Load batch by batch_id
        Step 2: Update batch_state and batch_summary
        Step 3: Update tickets (per-item updates or mark all failed)
        Step 4: If all batches for the request are processed, emit domain event
        """
        try:
            await self._logger.info(
                "Function started",
                batch_id=update.batch_id,
                batch_state=update.batch_state,
                mark_all_tickets_failed=update.mark_all_tickets_failed,
                ticket_update_count=len(update.ticket_updates or []),
            )

            try:
                batch = self.batches_collection.find_one({"batch_id": update.batch_id})
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB query failed",
                    batch_id=update.batch_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

            if not batch:
                raise ValueError(f"Batch not found for batch_id={update.batch_id}")

            request_id = batch["request_id"]
            now = self._now()

            batch_fields: Dict[str, Any] = {
                "batch_state": update.batch_state,
                "updatedAt": now,
            }
            if update.batch_summary is not None:
                batch_fields["batch_summary"] = update.batch_summary

            try:
                batch_result = self.batches_collection.update_one(
                    {"batch_id": update.batch_id},
                    {"$set": batch_fields},
                )
                await self._logger.debug(
                    "Batch update completed",
                    batch_id=update.batch_id,
                    matched_count=batch_result.matched_count,
                )
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB batch update failed",
                    batch_id=update.batch_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

            if update.mark_all_tickets_failed:
                try:
                    ticket_result = self.tickets_collection.update_many(
                        {"batch_id": update.batch_id},
                        {"$set": {"state": "failed", "updatedAt": now}},
                    )
                    await self._logger.debug(
                        "Marked all tickets failed",
                        batch_id=update.batch_id,
                        modified_count=ticket_result.modified_count,
                    )
                except PyMongoError as e:
                    await self._logger.error(
                        "MongoDB ticket bulk update failed",
                        batch_id=update.batch_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise
            elif update.ticket_updates:
                for ticket_update in update.ticket_updates:
                    ticket_fields: Dict[str, Any] = {
                        "state": ticket_update.state,
                        "updatedAt": now,
                    }
                    if ticket_update.response is not None:
                        ticket_fields["response"] = ticket_update.response

                    try:
                        self.tickets_collection.update_one(
                            {
                                "batch_id": update.batch_id,
                                "ticket_id": ticket_update.ticket_id,
                            },
                            {"$set": ticket_fields},
                        )
                    except PyMongoError as e:
                        await self._logger.error(
                            "MongoDB ticket update failed",
                            batch_id=update.batch_id,
                            ticket_id=ticket_update.ticket_id,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        raise

            batches_completed = await self.get_all_batches_completed(request_id)
            event_emitted = False

            if batches_completed.completed and self._event_bus is not None:
                batch_count = self.batches_collection.count_documents(
                    {"request_id": request_id}
                )
                await self._event_bus.emit(
                    CLASSIFICATION_ALL_BATCHES_COMPLETED_EVENT,
                    data=ClassificationAllBatchesCompletedPayload(
                        request_id=request_id,
                        batch_count=batch_count,
                    ).model_dump(),
                )
                event_emitted = True
                await self._logger.info(
                    "Emitted classification_all_batches_completed",
                    request_id=request_id,
                    batch_count=batch_count,
                )
            else:
                await self._logger.debug(
                    "Not all batches completed yet, skipping event emit",
                    request_id=request_id,
                    all_batches_completed=batches_completed.completed,
                )
                

            output = UpdateBatchOutput(
                batch_id=update.batch_id,
                request_id=request_id,
                all_batches_completed=batches_completed.completed,
                event_emitted=event_emitted,
            )

            await self._logger.info(
                "Function ended successfully",
                batch_id=update.batch_id,
                all_batches_completed=batches_completed.completed,
                event_emitted=event_emitted,
            )
            return output

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    # Ticket operations
    async def add_ticket(
        self,
        request_id: str,
        batch_id: str,
        content: str,
        batch_number: int,
        state: str = "queued",
        response: Optional[str] = None,
        ticket_id: Optional[str] = None,
    ) -> AddTicketOutput:
        """
        Add a new ticket record.

        This function creates a new ticket in the tickets collection with
        auto-generated UUID4 if ticket_id not provided.

        Processing Steps:
        Step 1: Generate UUID4 for ticket_id if not provided
        Step 2: Create document with request_id, batch_number, content, timestamps
        Step 3: Insert into tickets collection
        """
        try:
            await self._logger.info(
                "Function started",
                request_id=request_id,
                batch_number=batch_number,
                state=state,
                ticket_id=ticket_id
            )

            if ticket_id is None:
                ticket_id = str(uuid.uuid4())
                await self._logger.debug("Generated new ticket_id", ticket_id=ticket_id)

            now = self._now()
            doc = {
                "ticket_id": ticket_id,
                "request_id": request_id,
                "batch_id": batch_id,
                "content": content,
                "state": state,
                "batch_number": batch_number,
                "response": response,
                "createdAt": now,
                "updatedAt": now,
            }

            await self._logger.debug("Inserting ticket document", ticket_id=ticket_id)

            try:
                self.tickets_collection.insert_one(doc)
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB insert failed",
                    ticket_id=ticket_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.info(
                "Function ended successfully",
                ticket_id=ticket_id,
                request_id=request_id
            )
            return AddTicketOutput(ticket_id=ticket_id)

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def update_ticket(self, ticket_id: str, **kwargs) -> None:
        """
        Update a ticket record.

        Processing Steps:
        Step 1: Build update document with updatedAt timestamp
        Step 2: Update the ticket document in collection
        """
        try:
            await self._logger.info(
                "Function started",
                ticket_id=ticket_id,
                fields=list(kwargs.keys())
            )

            update = {**kwargs, "updatedAt": self._now()}

            try:
                result = self.tickets_collection.update_one(
                    {"ticket_id": ticket_id},
                    {"$set": update}
                )
                await self._logger.debug(
                    "Update completed",
                    ticket_id=ticket_id,
                    matched_count=result.matched_count
                )
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB update failed",
                    ticket_id=ticket_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.info("Function ended successfully")

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    # Query operations
    async def get_all_batches_completed(self, request_id: str) -> GetAllBatchesCompletedOutput:
        """
        Check if all batches for a request are in 'processed' state.

        Processing Steps:
        Step 1: Query all batches for request_id
        Step 2: Return False if no batches found
        Step 3: Check if all batches have batch_state='processed'
        """
        try:
            await self._logger.info(
                "Function started",
                request_id=request_id
            )

            try:
                batches = list(self.batches_collection.find({"request_id": request_id}))
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB query failed",
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.debug(
                "Batches query completed",
                request_id=request_id,
                count=len(batches)
            )

            if not batches:
                await self._logger.debug("No batches found for request_id", request_id=request_id)
                await self._logger.info("Function ended successfully", result=False)
                return GetAllBatchesCompletedOutput(completed=False)

            completed = all(b.get("batch_state") == "processed" for b in batches)

            await self._logger.info(
                "Function ended successfully",
                result=completed,
                total_batches=len(batches)
            )
            return GetAllBatchesCompletedOutput(completed=completed)

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def get_ticket_responses(self, request_id: str) -> GetTickerResponsesOutput:
        """
        Get all tickets for a request with their state and content.

        Processing Steps:
        Step 1: Query all tickets for request_id
        Step 2: Map each ticket to include ticket_id, content, state, response, batch_number
        """
        try:
            await self._logger.info(
                "Function started",
                request_id=request_id
            )

            try:
                tickets = list(self.tickets_collection.find({"request_id": request_id}))
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB query failed",
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.debug(
                "Tickets query completed",
                request_id=request_id,
                count=len(tickets)
            )

            responses = [
                TicketResponseOutput(
                    ticket_id=t["ticket_id"],
                    content=t["content"],
                    state=t["state"],
                    response=t.get("response"),
                    batch_number=t["batch_number"],
                )
                for t in tickets
            ]

            await self._logger.info(
                "Function ended successfully",
                count=len(responses)
            )
            return GetTickerResponsesOutput(responses=responses)

        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def get_batch_info_and_tickets(self, batch_id: str) -> GetBatchInfoAndTicketsOutput:
        """
        Get the batch information and tickets for a batch.

        Processing Steps:
        Step 1: Query the batch information
        Step 2: Query the tickets for the batch
        """
        try:
            await self._logger.info(
                "Function started",
                batch_id=batch_id
            )

            try:
                batch = self.batches_collection.find_one({"batch_id": batch_id})
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB query failed",
                    batch_id=batch_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            try:
                tickets = list(self.tickets_collection.find({"batch_id": batch_id}))
            except PyMongoError as e:
                await self._logger.error(
                    "MongoDB query failed",
                    batch_id=batch_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

            await self._logger.debug(
                "Tickets query completed",
                batch_id=batch_id,
                count=len(tickets)
            )

            batch_record = BatchRecord.model_validate(batch) if batch else None
            ticket_records = [TicketRecord.model_validate(t) for t in tickets]
            return GetBatchInfoAndTicketsOutput(batch=batch_record, tickets=ticket_records)
        except Exception as e:
            await self._logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__
            )
            raise