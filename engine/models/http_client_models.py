from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SarvamMessages(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class SarvamAPIRequest(BaseModel):
    model: str
    messages: List[SarvamMessages]
    max_tokens: int = Field(
        2000,
        description="The maximum number of tokens to generate in the completion.",
    )


class SarvamTokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class SarvamAPIResult(BaseModel):
    content: str
    usage: SarvamTokenUsage = Field(default_factory=SarvamTokenUsage)