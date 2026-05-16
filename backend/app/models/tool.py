import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Uuid
from app.core.database import Base


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    api_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="POST")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    auth_config: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_type: Mapped[str] = mapped_column(String(20), default="http", server_default="http")
    kb_namespace: Mapped[str | None] = mapped_column(String(200), nullable=True)
    kb_operation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
