from typing import Optional

from engine.operators.operators import TicketPipelineOperators
from engine.models.api_request_models import TicketParseBatchResponse, TicketParseRequest
from engine.operators.db.db import DBDatabase


class TicketPipelineApplication:
    def __init__(
        self,
        reducers,
        logger,
        operators: Optional[TicketPipelineOperators] = None,
    ) -> None:
        self.reducers = reducers
        self.logger = logger
        self.operators = operators


    async def initialize(self) -> None:
        self.db : DBDatabase = self.operators._db


    async def create_batches(self, tickets: list[str]) -> list[list[str]]:
        """Creates batches of up to 25 tickets each."""
        return [tickets[i:i + 25] for i in range(0, len(tickets), 25)]

    async def process_tickets_request(self, request: TicketParseRequest) -> TicketParseBatchResponse:
        """
        Processes incoming ticket requests:
            1. Adds the ticket request to the database
            2. Splits tickets into batches and adds batches to the DB
            3. Adds tickets to the DB associated with their batch and request
        """
        # Step 1: Add the request to the DB with details from the request
        request_id = await self.db.add_request(
            state="classification",
            request_id=None
        )
        await self.logger.info(f"Request added to database with id: {request_id}")

        # Step 2: Create batches and add them to the DB (no extra batch info supported, just number from db.py)
        batches = await self.create_batches(request.tickets)
        batch_numbers = []
        for batch in batches:
            batch_number = await self.db.add_batch(
                request_id=request_id,
                batch_state="queued",
                batch_summary=None
            )
            batch_numbers.append(batch_number)
            await self.logger.info(f"Batch {batch_number} added to database for request id: {request_id}")

        # Step 3: Add tickets to the DB, linked to both request and their batch using db.py functions
        for batch, batch_number in zip(batches, batch_numbers):
            for ticket_content in batch:
                ticket_id = await self.db.add_ticket(
                    request_id=request_id,
                    content=ticket_content,
                    batch_number=batch_number,
                    state="queued",
                    response=None,
                    ticket_id=None
                )
                await self.logger.info(
                    f"Ticket added to database with id: {ticket_id} (batch_number: {batch_number})"
                )

        # Placeholder for future processing steps
        pass