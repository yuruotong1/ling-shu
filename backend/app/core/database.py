from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event
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

# 启用 SQLite 外键约束
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
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
    from app.models.user import User  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 增量字段（SQLite 不支持 IF NOT EXISTS，用 try/except）
        for stmt in [
            "ALTER TABLE skills ADD COLUMN kb_namespaces TEXT DEFAULT '[]'",
            "ALTER TABLE skills ADD COLUMN active_version_id TEXT",
            "ALTER TABLE tools ADD COLUMN tool_type TEXT DEFAULT 'http'",
            "ALTER TABLE tools ADD COLUMN kb_namespace TEXT",
            "ALTER TABLE tools ADD COLUMN kb_operation TEXT",
            "ALTER TABLE tools ADD COLUMN steps TEXT DEFAULT '[]'",
            "ALTER TABLE agents ADD COLUMN response_format TEXT",
            "ALTER TABLE agents ADD COLUMN response_format_locked INTEGER DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN active_version_id TEXT",
            "ALTER TABLE traces ADD COLUMN agent_id TEXT",
            "ALTER TABLE traces ADD COLUMN session_id TEXT",
            "ALTER TABLE traces ADD COLUMN turn_index INTEGER DEFAULT 0",
            "ALTER TABLE traces ADD COLUMN user_rating TEXT",
            "ALTER TABLE traces ADD COLUMN reference_output TEXT",
            "ALTER TABLE agent_versions ADD COLUMN skills_snapshot TEXT DEFAULT '[]'",
            "ALTER TABLE evaluation_sets ADD COLUMN agent_id TEXT",
            "ALTER TABLE experiments ADD COLUMN agent_id TEXT",
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # column already exists

    await _seed_initial_data()


_DEMO_RESPONSE_FORMAT = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["查询", "购买", "投诉", "咨询", "其他"],
            "description": "识别出的意图类别",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "置信度（0-1）",
        },
        "reason": {
            "type": "string",
            "description": "判断理由",
        },
    },
    "required": ["intent", "confidence", "reason"],
}


async def _seed_initial_data():
    """初始化种子数据：默认用户 + 演示 Skill + 演示 Agent"""
    from app.models.user import User
    from app.models.skill import Skill
    from app.models.agent import Agent
    from app.core.security import hash_password
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # ── 默认用户 ──────────────────────────────────────────────────
        for username, password, role in [
            ("admin", "admin123", "admin"),
            ("operator", "operator123", "operator"),
        ]:
            exists = await db.execute(select(User).where(User.username == username))
            if exists.scalar_one_or_none() is None:
                db.add(User(username=username, hashed_password=hash_password(password), role=role))
        await db.commit()

        # ── 演示 Skill ────────────────────────────────────────────────
        skill_name = "用户意图识别"
        sk_result = await db.execute(select(Skill).where(Skill.name == skill_name))
        if sk_result.scalar_one_or_none() is None:
            db.add(Skill(
                name=skill_name,
                description="识别用户输入的意图，返回结构化分类结果",
                prompt=(
                    "你是一个意图识别专家。根据用户的输入，判断其意图类别和置信度。\n\n"
                    "意图类别包括：查询、购买、投诉、咨询、其他。"
                ),
            ))
            await db.commit()

        # ── 演示 Agent（带 response_format）──────────────────────────
        agent_name = "意图识别 Agent"
        ag_result = await db.execute(select(Agent).where(Agent.name == agent_name))
        demo_agent = ag_result.scalar_one_or_none()
        if demo_agent is None:
            db.add(Agent(
                name=agent_name,
                description="演示 Agent，返回结构化 JSON 意图分析",
                system_prompt="你是一个智能客服意图分析助手，负责分析用户意图并输出结构化结果。",
                response_format=_DEMO_RESPONSE_FORMAT,
                response_format_locked=True,
            ))
            await db.commit()
        elif demo_agent.response_format is None:
            demo_agent.response_format = _DEMO_RESPONSE_FORMAT
            demo_agent.response_format_locked = True
            await db.commit()
