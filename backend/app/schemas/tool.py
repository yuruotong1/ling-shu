import uuid
from datetime import datetime
from pydantic import BaseModel


class ToolCreate(BaseModel):
    name: str
    description: str
    api_url: str = ""
    method: str = "POST"
    input_schema: dict = {}
    output_schema: dict = {}
    auth_config: dict = {}
    tool_type: str = "http"
    kb_namespace: str | None = None
    kb_operation: str | None = None
    steps: list[dict] = []


class ToolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    api_url: str | None = None
    method: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    auth_config: dict | None = None
    is_active: bool | None = None
    tool_type: str | None = None
    kb_namespace: str | None = None
    kb_operation: str | None = None
    steps: list[dict] | None = None


class ToolOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    api_url: str
    method: str
    input_schema: dict
    output_schema: dict
    auth_config: dict
    tool_type: str
    kb_namespace: str | None
    kb_operation: str | None
    steps: list[dict] = []
    is_active: bool
    call_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ToolTestRequest(BaseModel):
    params: dict = {}
