import asyncio
import json
import os
import re

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from classes.Logger.logger import LogSidecar
from engine.models.classification_models import (
    ClassificationRequestMessageInputModel,
    ClassificationResponseModel,
    TickerInformation,
)
from engine.models.db_models import TicketRecord, TicketUpdateItem, UpdateBatchInput
from engine.models.http_client_models import SarvamAPIRequest, SarvamMessages
from engine.operators.db.db import DBDatabase
from engine.operators.http_client import HTTPAPIClient

classification_job_system_message = """
You are a technical assistant with more than 10 years of experience.
You will be given a list of tickets. Classify each ticket into exactly one of:
hardware_issue, software_issue, model_quality, billing, other

At the end, generate one crisp, insightful sentence summarizing all tickets.

CRITICAL: In ticket_classifications, each ticket_id MUST be copied exactly from the input JSON.
Do not invent or reuse example IDs.

Respond in valid JSON only (no trailing commas):
{
    "ticket_classifications": [
        {
            "ticket_id": "1",
            "category": "hardware_issue"
        },
        {
            "ticket_id": "2",
            "category": "software_issue"
        }
    ],
    "summary": "Summary of the tickets"
}

Examples:
Input:
[
    {
        "ticket_id": "1",
        "description": "The device is overheating and shutting down unexpectedly."
    },
    {
        "ticket_id": "2",
        "description": "The software crashes when I try to open it."
    }
]

Output:
{
    "ticket_classifications": [
        {
            "ticket_id": "1",
            "category": "hardware_issue"
        },
        {
            "ticket_id": "2",
            "category": "software_issue"
        }
    ],
    "summary": "Half of tickets relate to hardware overheating and half to software crashes."
}
"""


class ClassificationChannel:
    """Runtime channel for ticket classification."""

    def __init__(
        self,
        logger: LogSidecar,
        db_ref: DBDatabase,
        http_api_client: HTTPAPIClient,
        worker_count: int = None,
    ) -> None:
        self._logger: LogSidecar = logger
        self._db_ref: DBDatabase = db_ref
        self.http_api_client: HTTPAPIClient = http_api_client
        self._worker_count = worker_count if worker_count is not None else int(os.getenv("CLASSIFICATION_WORKER_COUNT", "10"))
        self._worker_tasks: list[asyncio.Task] = []

    async def initialize(self) -> None:
        self._classification_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._worker_tasks = [
            asyncio.create_task(
                self.classification_worker(),
                name=f"classification_worker_{i}",
            )
            for i in range(self._worker_count)
        ]
        await self._logger.info(
            f"Spawned {self._worker_count} classification workers"
        )

    async def add_batch_job_to_queue(self, batch_id: str, batch_number: int = 0) -> None:
        self._classification_queue.put_nowait((batch_number, batch_id))

    async def add_batches_jobs_to_queue(self, batch_jobs: list[tuple[int, str]]) -> None:
        for batch_number, batch_id in batch_jobs:
            self._classification_queue.put_nowait((batch_number, batch_id))

    def _parse_classification_response(self, raw_response: str) -> ClassificationResponseModel:
        cleaned_output = re.sub(
            r"<think>.*?</think>",
            "",
            raw_response,
            flags=re.DOTALL,
        ).strip()

        if not cleaned_output:
            raise ValueError("Sarvam response empty after removing thinking blocks")

        parsed_json = json.loads(cleaned_output)
        return ClassificationResponseModel.model_validate(parsed_json)

    async def _build_ticket_updates(
        self,
        db_tickets: list[TicketRecord],
        parsed: ClassificationResponseModel,
        batch_id: str,
    ) -> list[TicketUpdateItem]:
        """Map LLM classifications to DB tickets using ticket_id as the verification key."""
        valid_ids = {t.ticket_id for t in db_tickets}
        mapped: dict[str, str] = {}
        classifications = list(parsed.ticket_classifications)

        for item in classifications:
            if item.ticket_id in valid_ids and item.ticket_id not in mapped:
                mapped[item.ticket_id] = item.category

        if len(db_tickets) == 1 and len(classifications) == 1:
            sole_id = db_tickets[0].ticket_id
            if sole_id not in mapped:
                mapped[sole_id] = classifications[0].category
                await self._logger.warning(
                    "Classification used single-ticket fallback",
                    batch_id=batch_id,
                    db_ticket_id=sole_id,
                    returned_ticket_id=classifications[0].ticket_id,
                )

        unmapped_db = [t for t in db_tickets if t.ticket_id not in mapped]
        remaining_classifications = [c for c in classifications if c.ticket_id not in mapped]
        if unmapped_db and len(unmapped_db) == len(remaining_classifications):
            for ticket, item in zip(unmapped_db, remaining_classifications):
                mapped[ticket.ticket_id] = item.category
                await self._logger.warning(
                    "Classification used index-order fallback",
                    batch_id=batch_id,
                    db_ticket_id=ticket.ticket_id,
                    returned_ticket_id=item.ticket_id,
                )

        updates: list[TicketUpdateItem] = []
        for ticket in db_tickets:
            if ticket.ticket_id in mapped:
                updates.append(
                    TicketUpdateItem(
                        ticket_id=ticket.ticket_id,
                        state="completed",
                        response=mapped[ticket.ticket_id],
                    )
                )
            else:
                await self._logger.warning(
                    "No classification matched for ticket",
                    batch_id=batch_id,
                    ticket_id=ticket.ticket_id,
                )
                updates.append(
                    TicketUpdateItem(
                        ticket_id=ticket.ticket_id,
                        state="failed",
                        response=None,
                    )
                )

        return updates

    def _build_sarvam_request(
        self, classification_input: ClassificationRequestMessageInputModel
    ) -> SarvamAPIRequest:
        return SarvamAPIRequest(
            model="sarvam-m",
            max_tokens=2000,
            messages=[
                SarvamMessages(role="system", content=classification_job_system_message),
                SarvamMessages(
                    role="user",
                    content=json.dumps(
                        [t.model_dump() for t in classification_input.tickets]
                    ),
                ),
            ],
        )

    async def classification_worker(self) -> None:
        while True:
            _, batch_id = await self._classification_queue.get()

            try:
                batch_info_and_tickets = await self._db_ref.get_batch_info_and_tickets(batch_id)
                if batch_info_and_tickets.batch is None:
                    raise ValueError(f"Batch not found: {batch_id}")
                tickets = batch_info_and_tickets.tickets

                classification_input = ClassificationRequestMessageInputModel(
                    tickets=[
                        TickerInformation(
                            ticket_id=t.ticket_id,
                            description=t.content,
                        )
                        for t in tickets
                    ]
                )

                classification_response = await self.invoke_sarvam_for_classification(
                    classification_input
                )
                parsed = self._parse_classification_response(classification_response)

                ticket_updates = await self._build_ticket_updates(tickets, parsed, batch_id)

                await self._db_ref.update_batch(
                    UpdateBatchInput(
                        batch_id=batch_id,
                        batch_state="processed",
                        batch_summary=parsed.summary,
                        ticket_updates=ticket_updates,
                    )
                )

            except Exception as e:
                await self._logger.error(
                    "Classification failed for batch",
                    batch_id=batch_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                await self._db_ref.update_batch(
                    UpdateBatchInput(
                        batch_id=batch_id,
                        batch_state="processed",
                        batch_summary=str(e),
                        mark_all_tickets_failed=True,
                    )
                )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=10, jitter=1),
        reraise=True,
    )
    async def invoke_sarvam_for_classification(
        self, request: ClassificationRequestMessageInputModel
    ) -> str:
        sarvam_request = self._build_sarvam_request(request)
        result = await self.http_api_client.send_request_to_sarvam(sarvam_request)
        return result.content

    async def cleanup(self) -> None:
        for task in self._worker_tasks:
            if not task.done():
                task.cancel()
        for task in self._worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._worker_tasks.clear()
