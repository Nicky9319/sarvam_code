from pydantic import BaseModel, Field


class SummarizationResponseModel(BaseModel):
    summary: str = Field(description="Consolidated summary across all batch summaries")
