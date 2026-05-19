from pydantic import BaseModel
from typing import Any


class ChatMessage(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict] | None = None
    tool_choice: Any = None
    session_id: str | None = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: ChatUsage
    trace_id: str | None = None
    session_id: str | None = None


class ModelObject(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "platform"
    created: int = 0


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelObject]
