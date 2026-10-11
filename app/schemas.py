from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RecipientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    event_name: str = Field(min_length=1, max_length=160)
    completion_date: date
    recipients: list[RecipientInput] = Field(min_length=1, max_length=1000)


class RecipientResult(BaseModel):
    id: UUID
    name: str
    email: str
    status: Literal["pending", "generated", "failed"]
    error: str | None = None
    download_url: str | None = None


class JobResult(BaseModel):
    id: UUID
    event_name: str
    completion_date: date
    status: Literal["queued", "running", "completed", "partial", "failed"]
    total: int
    processed: int
    generated: int
    failed: int
    progress_percent: float
    created_at: str
    recipients: list[RecipientResult]
