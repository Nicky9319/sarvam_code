from typing import Optional

from engine.models.api_request_models import (
    TicketParseBatchResponse,
    TicketParseRequest,
    TicketParseSuccessItem,
)
from engine.models.db_models import GetTickerResponsesOutput
from engine.operators.db.db import DBDatabase
from engine.operators.operators import TicketPipelineOperators

import time



class TicketPipelineApplication:
    def __init__(
        self,
        reducers,
        logger,
        event_bus,
        operators: Optional[TicketPipelineOperators] = None,
    ) -> None:
        self.reducers = reducers
        self.logger = logger
        self.event_bus = event_bus
        self.operators = operators

    async def initialize(self) -> None:
        self.db: DBDatabase = self.operators._db

    async def create_batches(self, tickets: list[str]) -> list[list[str]]:
        """Creates batches of up to 10 tickets each."""
        return [tickets[i : i + 10] for i in range(0, len(tickets), 10)]

    def _to_parse_response(
        self,
        tickets_output: GetTickerResponsesOutput,
        summary: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> TicketParseBatchResponse:
        return TicketParseBatchResponse(
            success=self._get_success_items(tickets_output),
            failures=self._get_failure_items(tickets_output),
            summary=summary,
            duration_seconds=duration_seconds,
        )

    async def process_tickets_request(self, request: TicketParseRequest) -> TicketParseBatchResponse:
        """
        Processes incoming ticket requests:
            1. Adds the ticket request to the database
            2. Splits tickets into batches and adds batches to the DB
            3. Adds tickets to the DB associated with their batch and request
            4. Enqueues each batch for classification
            5. Waits for classification to complete via FutureManager
            6. Enqueues request for summarization
            7. Waits for summarization to complete via FutureManager
            8. Returns classified tickets with consolidated summary as TicketParseBatchResponse
        """
        start_time = time.time()

        request_output = await self.db.add_request(
            state="classification",
            request_id=None,
        )
        request_id = request_output.request_id
        await self.logger.info(f"Request added to database with id: {request_id}")

        if not request.tickets:
            duration_seconds = time.time() - start_time
            return TicketParseBatchResponse(success=[], failures=[], summary=None, duration_seconds=duration_seconds)

        self.operators.future_manager.register(request_id, future_type="classification")

        batches = await self.create_batches(request.tickets)
        batch_jobs: list[tuple[int, str]] = []
        ticket_index = 0
        for batch in batches:
            batch_output = await self.db.add_batch(
                request_id=request_id,
                batch_state="queued",
                batch_summary=None,
            )
            batch_number = batch_output.batch_number
            batch_jobs.append((batch_number, batch_output.batch_id))
            await self.logger.info(
                f"Batch {batch_number} ({batch_output.batch_id}) added for request {request_id}"
            )

            for ticket_content in batch:
                ticket_index += 1
                assigned_ticket_id = str(ticket_index)
                ticket_output = await self.db.add_ticket(
                    request_id=request_id,
                    batch_id=batch_output.batch_id,
                    content=ticket_content,
                    batch_number=batch_number,
                    state="queued",
                    response=None,
                    ticket_id=assigned_ticket_id,
                )
                await self.logger.info(
                    f"Ticket {ticket_output.ticket_id} added to batch {batch_output.batch_id}",
                    ticket_id=ticket_output.ticket_id,
                )

        await self.operators.classification_channel.add_batches_jobs_to_queue(batch_jobs)
        await self.logger.info(f"Enqueued {len(batch_jobs)} batches for classification")

        await self.operators.future_manager.wait(request_id, future_type="classification")
        await self.logger.info(f"Classification completed for request {request_id}")

        await self.db.update_request_state(request_id, "summarization")
        self.operators.future_manager.register(request_id, future_type="summarization")
        await self.operators.summarization_channel.add_job_to_queue(request_id)
        await self.logger.info(f"Enqueued request {request_id} for summarization")

        await self.operators.future_manager.wait(request_id, future_type="summarization")
        await self.logger.info(f"Summarization completed for request {request_id}")

        tickets_output = await self.db.get_ticket_responses(request_id)
        request_record = await self.db.get_request(request_id)
        summary = request_record.get("response_summary") if request_record else None

        duration_seconds = time.time() - start_time

        success_count = len([t for t in tickets_output.responses if t.state == "completed"])
        failure_count = len([t for t in tickets_output.responses if t.state != "completed"])

        await self.db.add_metrics(
            request_id=request_id,
            duration_seconds=duration_seconds,
            classification_worker_count=self.operators.classification_worker_count,
            summarization_worker_count=self.operators.summarization_worker_count,
            batch_count=len(batches),
            ticket_count=len(tickets_output.responses),
            success_count=success_count,
            failure_count=failure_count,
        )

        return self._to_parse_response(tickets_output, summary=summary, duration_seconds=duration_seconds)

    def _get_success_items(self, tickets_output: GetTickerResponsesOutput) -> list[TicketParseSuccessItem]:
        return [
            TicketParseSuccessItem(
                ticket_id=ticket.ticket_id,
                description=ticket.content,
                classification=ticket.response or "",
            )
            for ticket in tickets_output.responses
            if ticket.state == "completed"
        ]

    def _get_failure_items(self, tickets_output: GetTickerResponsesOutput) -> list[str]:
        return [
            ticket.content
            for ticket in tickets_output.responses
            if ticket.state != "completed"
        ]
