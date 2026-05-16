from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """用于非迁移启动时自动建表（SQLite开发模式）"""
    from app.models import (  # noqa
        ModelConfig, Tool, Skill, SkillVersion, skill_tools,
        Agent, AgentVersion, agent_skills,
        Evaluator, EvaluationSet, EvaluationItem,
        Experiment, ExperimentResult, Trace,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add columns introduced after initial schema creation
        for stmt in [
            "ALTER TABLE skills ADD COLUMN kb_namespaces TEXT DEFAULT '[]'",
            "ALTER TABLE tools ADD COLUMN tool_type TEXT DEFAULT 'http'",
            "ALTER TABLE tools ADD COLUMN kb_namespace TEXT",
            "ALTER TABLE tools ADD COLUMN kb_operation TEXT",
            "ALTER TABLE tools ADD COLUMN steps TEXT DEFAULT '[]'",
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # column already exists
