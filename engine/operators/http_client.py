from typing import Optional

from openai import AsyncOpenAI

from classes.Logger.logger import LogAgent
from engine.models.http_client_models import SarvamAPIRequest


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

    async def initialize_client(self) -> None:
        self._sarvam_client = AsyncOpenAI(
            api_key=self._sarvam_api_key,
            base_url=self._sarvam_base_url,
        )

    async def send_request_to_sarvam(self, request: SarvamAPIRequest) -> str:
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
        return content.strip()

    async def cleanup(self) -> None:
        if self._sarvam_client is not None:
            await self._sarvam_client.close()
            self._sarvam_client = None
