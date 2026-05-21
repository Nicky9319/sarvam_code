import asyncio
import json
import re

from classes.Logger.logger import LogSidecar
from engine.models.classification_models import (
    ClassificationRequestMessageInputModel,
    ClassificationResponseModel,
    TickerInformation,
)
from engine.models.db_models import TicketUpdateItem, UpdateBatchInput
from engine.models.http_client_models import SarvamAPIRequest, SarvamMessages
from engine.operators.db.db import DBDatabase
from engine.operators.http_client import HTTPAPIClient
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


classification_job_system_message = """
    You are Technical assistant having more than 10 years of expereince, 
            you will be given a list of tickets you need to summarize each ticket in one of following categories
            hardware_issue,
            software_issue,
            model_quality,
            billing
            other 

            At the end make sure to generate a one sentence detailed summmary of all the tickets.
            the summary should be crisp but still insightful and should give a clear picture of the overall situation.

            Make sure to give the response in json format as mentioned below
            {
                "ticket_classifications": [
                    {
                        "ticket_id": "12345",
                        "category": "hardware_issue",
                    },
                    {
                        "ticket_id": "12346",
                        "category": "software_issue",
                    }
                ],
                "summary": "Summary of the tickets"
            }


            Examples:
            Input:
            [
                {
                    "ticket_id": "12345",
                    "description": "The device is overheating and shutting down unexpectedly."
                },
                {
                    "ticket_id": "12346",
                    "description": "The software crashes when I try to open it."
                }
            ]

            Output:
            {
                "ticket_classifications": [
                    {
                        "ticket_id": "12345",
                        "category": "hardware_issue",
                    },
                    {
                        "ticket_id": "12346",
                        "category": "software_issue",
                    }
                ],
                "summary": "There are 50 percent tickets related to hardware issues and 50 percent tickets related to software issues. The main hardware issue is overheating and the main software issue is crashing."
            }
    """


class ClassificationChannel:
    """Runtime channel for ticket classification."""

    def __init__(
        self,
        logger: LogSidecar,
        db_ref: DBDatabase,
        http_api_client: HTTPAPIClient,
        worker_count: int = 10,
    ) -> None:
        self._logger: LogSidecar = logger
        self._db_ref: DBDatabase = db_ref
        self.http_api_client: HTTPAPIClient = http_api_client
        self._worker_count = worker_count
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

    # Queue Operations

    async def add_batch_job_to_queue(self, batch_id: str, batch_number: int = 0) -> None:
        self._classification_queue.put_nowait((batch_number, batch_id))

    async def add_batches_jobs_to_queue(self, batch_jobs: list[tuple[int, str]]) -> None:
        for batch_number, batch_id in batch_jobs:
            self._classification_queue.put_nowait((batch_number, batch_id))


    # Helper Functions
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

    # Build the Sarvam API Request
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

    # Worker Nodes

    async def classification_worker(self) -> None:
        """
        1. Wait for a batch_id from the queue.
        2. Fetch the batch information and its tickets.
        3. Call the Sarvam API for classification.
        4. On failure, mark batch processed and tickets failed via update_batch.
        5. On success, update batch summary and tickets as completed with responses.
        6. update_batch emits classification_all_batches_completed when all batches are done.
        """
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

                await self._db_ref.update_batch(
                    UpdateBatchInput(
                        batch_id=batch_id,
                        batch_state="processed",
                        batch_summary=parsed.summary,
                        ticket_updates=[
                            TicketUpdateItem(
                                ticket_id=item.ticket_id,
                                state="completed",
                                response=item.category,
                            )
                            for item in parsed.ticket_classifications
                        ],
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
        return await self.http_api_client.send_request_to_sarvam(sarvam_request)

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
