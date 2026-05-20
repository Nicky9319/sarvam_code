from classes.Logger.logger import LogAgent
from pydantic import BaseModel, Field
from typing import List, Literal
from openai import OpenAI

class SarvamMessages(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class SarvamAPIRequest(BaseModel):
    model: str
    messages: List[SarvamMessages]
    max_tokens: int = Field(
        5000, description="The maximum number of tokens to generate in the completion. The token count of your prompt plus max_tokens cannot exceed the model's context length. Most models have a context length of 2048 tokens (except for the newest models, which support 4096). Default is 16."
    )

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

