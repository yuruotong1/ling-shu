import uuid
from datetime import datetime
from pydantic import BaseModel


class ModelConfigCreate(BaseModel):
    name: str
    provider: str  # openai/azure/anthropic/custom
    endpoint: str
    api_key: str | None = None
    default_model: str
    default_params: dict = {}


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    default_params: dict | None = None
    is_active: bool | None = None


class ModelConfigOut(BaseModel):
    id: uuid.UUID
    name: str
    provider: str
    endpoint: str
    default_model: str
    default_params: dict
    is_active: bool
    has_api_key: bool = False
    api_key: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
