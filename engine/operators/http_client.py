from classes.Logger.logger import LogAgent
from pydantic import BaseModel, Field
from typing import List, Literal
from openai import OpenAI\

from engine.models.http_client_models import SarvamMessages, SarvamAPIRequest

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
    
    async def intialize_client(self):
        self.sarvam_client = OpenAI(
            api_key=self._sarvam_api_key,
            base_url=self._sarvam_base_url
        )

    async def send_request_to_sarvam(self, request: SarvamAPIRequest) -> dict:
        response = await self.sarvam_client.completions.create(
            model=request.model,
            messages=request.messages,
            max_tokens=request.max_tokens
        )

        return response.choices[0].message.content

