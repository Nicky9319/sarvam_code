from typing import List, Literal
from pydantic import BaseModel, Field

class SarvamMessages(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class SarvamAPIRequest(BaseModel):
    model: str
    messages: List[SarvamMessages]
    max_tokens: int = Field(
        2000, description="The maximum number of tokens to generate in the completion. The token count of your prompt plus max_tokens cannot exceed the model's context length. Most models have a context length of 2048 tokens (except for the newest models, which support 4096). Default is 16."
    )