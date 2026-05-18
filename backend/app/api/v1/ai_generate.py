"""通用 AI 生成接口"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.model_config import ModelConfig
from app.models.user import User
from app.services import model_client

router = APIRouter(prefix="/ai-generate", tags=["ai-generate"])


class PromptGenerateRequest(BaseModel):
    type: str  # agent | skill | evaluator
    description: str


class SchemaGenerateRequest(BaseModel):
    description: str


PROMPT_TEMPLATES = {
    "agent": (
        "你是一个专业的 AI Agent 提示词工程师。根据用户的需求描述，生成一段高质量的系统提示词（system prompt）。\n"
        "要求：\n"
        "1. 明确定义 Agent 的角色和职责\n"
        "2. 描述推理规则和决策逻辑\n"
        "3. 说明如何判断任务完成\n"
        "4. 只输出提示词本身，不要有任何解释性文字\n"
        "5. 使用中文输出"
    ),
    "skill": (
        "你是一个专业的 AI Skill 提示词工程师。根据用户的需求描述，生成一段高质量的 Skill 提示词。\n"
        "要求：\n"
        "1. 明确定义 Skill 的功能边界\n"
        "2. 给出具体的处理规则和约束\n"
        "3. 提供输入输出格式示例\n"
        "4. 只输出提示词本身，不要有任何解释性文字\n"
        "5. 使用中文输出"
    ),
    "evaluator": (
        "你是一个专业的 AI 评估器提示词工程师。根据用户的需求描述，生成一段高质量的评估提示词。\n"
        "要求：\n"
        "1. 明确评估维度和评分标准\n"
        "2. 给出每个分数段的具体定义\n"
        "3. 说明评分时需要关注的关键点\n"
        "4. 只输出提示词本身，不要有任何解释性文字\n"
        "5. 使用中文输出"
    ),
}


@router.post("/prompt")
async def generate_prompt(
    body: PromptGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """根据描述和类型，调用大模型生成提示词。"""
    if body.type not in PROMPT_TEMPLATES:
        raise HTTPException(400, f"不支持的类型：{body.type}，可选：agent, skill, evaluator")
    if not body.description.strip():
        raise HTTPException(400, "描述不能为空")

    mc_result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    mc = mc_result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(500, "No model config available")

    system_prompt = PROMPT_TEMPLATES[body.type]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请为以下需求生成提示词：\n{body.description}"},
    ]

    result = await model_client.chat_completion(mc=mc, messages=messages, temperature=0.3)
    content = result["choices"][0]["message"].get("content", "")

    if not content.strip():
        raise HTTPException(500, "模型未返回有效内容，请重试")

    return {"prompt": content.strip()}


@router.post("/schema")
async def generate_schema(
    body: SchemaGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """根据自然语言描述，调用大模型生成 JSON Schema。"""
    if not body.description.strip():
        raise HTTPException(400, "描述不能为空")

    mc_result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    mc = mc_result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(500, "No model config available")

    system_prompt = (
        "你是一个 JSON Schema 生成专家。根据用户的自然语言描述，生成一个合法的 JSON Schema。\n"
        "要求：\n"
        "1. 只输出 JSON Schema 本身，不要输出任何解释性文字\n"
        "2. 必须包含 type='object' 和 properties\n"
        "3. 为每个字段添加 description\n"
        "4. 合理设置 required 字段\n"
        "5. 输出必须是合法的 JSON 格式"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请为以下需求生成 JSON Schema：\n{body.description}"},
    ]

    result = await model_client.chat_completion(mc=mc, messages=messages, temperature=0.2)
    content = result["choices"][0]["message"].get("content", "")

    # 尝试从响应中提取 JSON
    import json
    import re
    schema = None
    try:
        schema = json.loads(content)
    except Exception:
        pass
    if schema is None:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            try:
                schema = json.loads(m.group(1))
            except Exception:
                pass
    if schema is None:
        m = re.search(r"(\{[\s\S]*\})", content)
        if m:
            try:
                schema = json.loads(m.group(1))
            except Exception:
                pass

    if schema is None:
        raise HTTPException(500, "模型未返回合法的 JSON Schema，请重试或手动编写")

    return {"schema": schema}
