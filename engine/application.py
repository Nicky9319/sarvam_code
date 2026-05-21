from typing import Optional

from engine.models.api_request_models import (
    TicketParseBatchResponse,
    TicketParseRequest,
    TicketParseSuccessItem,
)
from engine.models.db_models import GetTickerResponsesOutput
from engine.operators.db.db import DBDatabase
from engine.operators.operators import TicketPipelineOperators


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
        """Creates batches of up to 25 tickets each."""
        return [tickets[i : i + 25] for i in range(0, len(tickets), 25)]

    def _to_parse_response(self, tickets_output: GetTickerResponsesOutput) -> TicketParseBatchResponse:
        success: list[TicketParseSuccessItem] = []
        failures: list[str] = []

        for ticket in tickets_output.responses:
            if ticket.state == "completed":
                success.append(
                    TicketParseSuccessItem(
                        description=ticket.content,
                        classification=ticket.response or "",
                    )
                )
            else:
                failures.append(ticket.content)

        return TicketParseBatchResponse(success=success, failures=failures)

    async def process_tickets_request(self, request: TicketParseRequest) -> TicketParseBatchResponse:
        """
        Processes incoming ticket requests:
            1. Adds the ticket request to the database
            2. Splits tickets into batches and adds batches to the DB
            3. Adds tickets to the DB associated with their batch and request
            4. Enqueues each batch for classification
            5. Waits for all batches to complete via FutureManager
            6. Returns classified tickets as TicketParseBatchResponse
        """
        request_output = await self.db.add_request(
            state="classification",
            request_id=None,
        )
        request_id = request_output.request_id
        await self.logger.info(f"Request added to database with id: {request_id}")

        if not request.tickets:
            return TicketParseBatchResponse(success=[], failures=[])

        self.operators.future_manager.register(request_id)

        batches = await self.create_batches(request.tickets)
        batch_ids: list[str] = []
        for batch in batches:
            batch_output = await self.db.add_batch(
                request_id=request_id,
                batch_state="queued",
                batch_summary=None,
            )
            batch_number = batch_output.batch_number
            batch_ids.append(batch_output.batch_id)
            await self.logger.info(
                f"Batch {batch_number} ({batch_output.batch_id}) added for request {request_id}"
            )

            for ticket_content in batch:
                ticket_output = await self.db.add_ticket(
                    request_id=request_id,
                    batch_id=batch_output.batch_id,
                    content=ticket_content,
                    batch_number=batch_number,
                    state="queued",
                    response=None,
                    ticket_id=None,
                )
                await self.logger.info(
                    f"Ticket {ticket_output.ticket_id} added to batch {batch_output.batch_id}"
                )


        await self.operators.classification_channel.add_batches_jobs_to_queue(batch_ids)
        await self.logger.info(f"Enqueued {len(batch_ids)} batches for classification")

        await self.operators.future_manager.wait(request_id)
        await self.logger.info(f"Classification completed for request {request_id}")

        tickets_output = await self.db.get_ticket_responses(request_id)
        return self._to_parse_response(tickets_output)
