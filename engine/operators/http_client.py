import os
from typing import Optional

from openai import AsyncOpenAI

from classes.Logger.logger import LogAgent
from engine.constants import DEFAULT_SARVAM_HTTP_TIMEOUT_SEC
from engine.models.http_client_models import SarvamAPIRequest, SarvamAPIResult, SarvamTokenUsage


class HTTPAPIClient:
    def __init__(
        self,
        sarvam_base_url: str,
        sarvam_api_key: str,
        logger: LogAgent,
    ) -> None:
        self._sarvam_base_url = sarvam_base_url.rstrip("/")
        self._sarvam_api_key = sarvam_api_key
        self._logger = logger
        self._sarvam_client: Optional[AsyncOpenAI] = None
        self._cumulative_usage = SarvamTokenUsage()

    def reset_usage_totals(self) -> None:
        self._cumulative_usage = SarvamTokenUsage()

    def get_usage_totals(self) -> SarvamTokenUsage:
        return self._cumulative_usage.model_copy()

    async def initialize_client(self) -> None:
        timeout = float(os.getenv("SARVAM_HTTP_TIMEOUT", str(DEFAULT_SARVAM_HTTP_TIMEOUT_SEC)))
        self._sarvam_client = AsyncOpenAI(
            api_key=self._sarvam_api_key,
            base_url=self._sarvam_base_url,
            timeout=timeout,
        )

    async def send_request_to_sarvam(self, request: SarvamAPIRequest) -> SarvamAPIResult:
        if self._sarvam_client is None:
            raise RuntimeError("HTTPAPIClient not initialized; call initialize_client() first")

        response = await self._sarvam_client.chat.completions.create(
            model=request.model,
            messages=[m.model_dump() for m in request.messages],
            max_tokens=request.max_tokens,
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Sarvam API returned empty message content")

        usage = SarvamTokenUsage()
        if response.usage is not None:
            usage = SarvamTokenUsage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        self._cumulative_usage.prompt_tokens += usage.prompt_tokens
        self._cumulative_usage.completion_tokens += usage.completion_tokens
        self._cumulative_usage.total_tokens += usage.total_tokens

        return SarvamAPIResult(content=content.strip(), usage=usage)

    async def cleanup(self) -> None:
        if self._sarvam_client is not None:
            await self._sarvam_client.close()
            self._sarvam_client = None
