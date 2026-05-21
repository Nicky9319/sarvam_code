import asyncio
import json
import os
import re
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from classes.Logger.logger import LogSidecar
from engine.event_bus import (
    SUMMARIZATION_ALL_BATCHES_COMPLETED_EVENT,
    EventBus,
    SummarizationAllBatchesCompletedPayload,
)
from engine.models.http_client_models import SarvamAPIRequest, SarvamMessages
from engine.models.summarization_models import SummarizationResponseModel
from engine.operators.db.db import DBDatabase
from engine.operators.http_client import HTTPAPIClient

summarization_job_system_message = """
You are a technical summarization assistant. You will be given a list of batch summaries,
each containing the summary of a batch of support tickets.

Your task is to create a single, cohesive summary that:
1. Consolidates all the batch summaries into one coherent overview
2. Highlights the key themes and patterns across all tickets
3. Provides actionable insights about the overall situation
4. Is concise but informative (2-4 sentences max)

Respond in JSON format only:
{
    "summary": "Your consolidated summary here"
}

Examples:
Input:
[
    {
        "batch_number": 1,
        "summary": "Most tickets are related to hardware issues like overheating and screen flickering. Some software bugs were reported."
    },
    {
        "batch_number": 2,
        "summary": "Billing issues appeared in 30% of tickets. Model quality concerns were raised in a few cases."
    }
]

Output:
{
    "summary": "Overall, hardware issues dominate the ticket volume with overheating and display problems being most common. Software bugs and billing concerns form the secondary categories, while model quality feedback is minimal but worth monitoring."
}
"""


class SummarizationChannel:
    """Runtime channel for creating consolidated summaries from batch summaries."""

    def __init__(
        self,
        logger: LogSidecar,
        db_ref: DBDatabase,
        http_api_client: HTTPAPIClient,
        event_bus: Optional[EventBus],
        worker_count: int = None,
    ) -> None:
        self._logger: LogSidecar = logger
        self._db_ref: DBDatabase = db_ref
        self.http_api_client: HTTPAPIClient = http_api_client
        self._event_bus = event_bus
        self._worker_count = worker_count if worker_count is not None else int(os.getenv("SUMMARIZATION_WORKER_COUNT", "5"))
        self._worker_tasks: list[asyncio.Task] = []
        self._summarization_queue: asyncio.Queue = None

    async def initialize(self) -> None:
        self._summarization_queue = asyncio.Queue()
        self._worker_tasks = [
            asyncio.create_task(
                self.summarization_worker(),
                name=f"summarization_worker_{i}",
            )
            for i in range(self._worker_count)
        ]
        await self._logger.info(
            f"Spawned {self._worker_count} summarization workers"
        )

    async def add_job_to_queue(self, request_id: str) -> None:
        """Add a request_id to the summarization queue."""
        self._summarization_queue.put_nowait(request_id)

    async def add_jobs_to_queue(self, request_ids: list[str]) -> None:
        """Add multiple request_ids to the summarization queue."""
        for request_id in request_ids:
            self._summarization_queue.put_nowait(request_id)

    def _parse_summarization_response(self, raw_response: str) -> str:
        """Parse the raw response from Sarvam API, stripping thinking blocks."""
        cleaned_output = re.sub(
            r"<think>.*?</think>",
            "",
            raw_response,
            flags=re.DOTALL,
        ).strip()

        if not cleaned_output:
            raise ValueError("Sarvam response empty after removing thinking blocks")

        try:
            parsed = SummarizationResponseModel.model_validate(json.loads(cleaned_output))
            return parsed.summary
        except (json.JSONDecodeError, ValueError):
            # Fallback when model returns plain text instead of JSON
            if cleaned_output.startswith('"') and cleaned_output.endswith('"'):
                return cleaned_output[1:-1]
            return cleaned_output

    def _build_sarvam_request(self, batch_summaries: list[dict]) -> SarvamAPIRequest:
        """Build the Sarvam API request for summarization."""
        return SarvamAPIRequest(
            model="sarvam-m",
            max_tokens=1000,
            messages=[
                SarvamMessages(role="system", content=summarization_job_system_message),
                SarvamMessages(
                    role="user",
                    content=json.dumps(batch_summaries),
                ),
            ],
        )

    async def summarization_worker(self) -> None:
        """
        Worker loop for summarization:
        1. Wait for a request_id from the queue.
        2. Fetch all batch summaries for this request.
        3. Call the Sarvam API for summarization.
        4. Update the request record with the final summary.
        5. Emit summarization_all_batches_completed event.
        """
        while True:
            request_id = await self._summarization_queue.get()

            try:
                batch_summaries = await self._db_ref.get_batch_summaries_for_request(request_id)

                if not batch_summaries:
                    await self._logger.warning(
                        "No batch summaries found for request",
                        request_id=request_id,
                    )
                    final_summary = "No tickets to summarize."
                else:
                    summarization_input = [item.model_dump() for item in batch_summaries]

                    raw_response = await self.invoke_sarvam_for_summarization(summarization_input)
                    final_summary = self._parse_summarization_response(raw_response)

                await self._db_ref.update_request_summary(request_id, final_summary)

                if self._event_bus is not None:
                    await self._event_bus.emit(
                        SUMMARIZATION_ALL_BATCHES_COMPLETED_EVENT,
                        data=SummarizationAllBatchesCompletedPayload(
                            request_id=request_id,
                            summary=final_summary,
                        ).model_dump(),
                    )

                await self._logger.info(
                    "Summarization completed",
                    request_id=request_id,
                    summary_length=len(final_summary),
                )

            except Exception as e:
                await self._logger.error(
                    "Summarization failed for request",
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                await self._db_ref.update_request_summary(
                    request_id,
                    f"Summarization failed: {str(e)}",
                )
                if self._event_bus is not None:
                    await self._event_bus.emit(
                        SUMMARIZATION_ALL_BATCHES_COMPLETED_EVENT,
                        data=SummarizationAllBatchesCompletedPayload(
                            request_id=request_id,
                            summary=f"Summarization failed: {str(e)}",
                        ).model_dump(),
                    )
            finally:
                self._summarization_queue.task_done()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=10, jitter=1),
        reraise=True,
    )
    async def invoke_sarvam_for_summarization(self, batch_summaries: list[dict]) -> str:
        """Call Sarvam API to generate consolidated summary."""
        sarvam_request = self._build_sarvam_request(batch_summaries)
        return await self.http_api_client.send_request_to_sarvam(sarvam_request)

    async def cleanup(self) -> None:
        """Cancel and await all worker tasks."""
        for task in self._worker_tasks:
            if not task.done():
                task.cancel()
        for task in self._worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._worker_tasks.clear()
