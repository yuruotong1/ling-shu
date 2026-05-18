import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Uuid
from app.core.database import Base


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    input: Mapped[list] = mapped_column(JSON, nullable=False)
    output: Mapped[str] = mapped_column(Text, default="")
    loop_steps: Mapped[list] = mapped_column(JSON, default=list)
    total_loops: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 多轮对话：session_id 相同的 Trace 属于同一会话
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    turn_index: Mapped[int] = mapped_column(Integer, default=0)
    # 用户对本轮输出的评价
    user_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)   # good | bad
    reference_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
