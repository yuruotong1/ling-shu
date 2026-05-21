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


class ToolGenerateRequest(BaseModel):
    description: str


class AgentGenerateRequest(BaseModel):
    description: str


class SkillGenerateRequest(BaseModel):
    description: str


class EvaluatorGenerateRequest(BaseModel):
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


async def _get_active_model(db: AsyncSession) -> ModelConfig:
    """获取第一个可用的模型配置"""
    mc_result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    mc = mc_result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(500, "未配置可用的大模型，请先在「模型配置」页面添加模型")
    return mc


async def _call_llm(mc: ModelConfig, system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
    """调用大模型，捕获异常返回友好错误"""
    import openai
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    try:
        result = await model_client.chat_completion(mc=mc, messages=messages, temperature=temperature)
        content = result["choices"][0]["message"].get("content", "")
        if not content.strip():
            raise HTTPException(500, "模型未返回有效内容，请重试")
        return content.strip()
    except openai.AuthenticationError:
        raise HTTPException(500, "模型 API Key 认证失败，请检查「模型配置」中的 API Key")
    except openai.BadRequestError as e:
        raise HTTPException(500, f"模型请求参数错误: {e.message}")
    except openai.RateLimitError:
        raise HTTPException(500, "模型调用频率超限，请稍后再试")
    except openai.APIConnectionError:
        raise HTTPException(500, "无法连接到模型服务，请检查「模型配置」中的 Endpoint 地址")
    except openai.APIStatusError as e:
        raise HTTPException(500, f"模型服务异常 ({e.status_code}): {e.message}")
    except Exception as e:
        raise HTTPException(500, f"模型调用失败: {e}")


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

    mc = await _get_active_model(db)
    system_prompt = PROMPT_TEMPLATES[body.type]
    content = await _call_llm(mc, system_prompt, f"请为以下需求生成提示词：\n{body.description}")
    return {"prompt": content}


@router.post("/schema")
async def generate_schema(
    body: SchemaGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """根据自然语言描述，调用大模型生成 JSON Schema。"""
    if not body.description.strip():
        raise HTTPException(400, "描述不能为空")

    mc = await _get_active_model(db)
    system_prompt = (
        "你是一个 JSON Schema 生成专家。根据用户的自然语言描述，生成一个合法的 JSON Schema。\n"
        "要求：\n"
        "1. 只输出 JSON Schema 本身，不要输出任何解释性文字\n"
        "2. 必须包含 type='object' 和 properties\n"
        "3. 为每个字段添加 description\n"
        "4. 合理设置 required 字段\n"
        "5. 输出必须是合法的 JSON 格式"
    )
    content = await _call_llm(mc, system_prompt, f"请为以下需求生成 JSON Schema：\n{body.description}", temperature=0.2)

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


@router.post("/tool")
async def generate_tool(
    body: ToolGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    根据自然语言描述，调用大模型生成完整的工具配置。
    返回包含 name, description, api_url, method, auth_type, auth_config, input_schema 的 JSON。
    """
    if not body.description.strip():
        raise HTTPException(400, "描述不能为空")

    mc = await _get_active_model(db)
    system_prompt = (
        "你是一个 API 工具设计专家。根据用户的自然语言描述，生成一个完整的 HTTP API 工具配置。\n"
        "要求：\n"
        "1. 只输出一个合法的 JSON 对象，不要有任何解释性文字\n"
        "2. JSON 必须包含以下字段：\n"
        "   - name: 工具的英文标识名（小写+下划线，如 query_order）\n"
        "   - description: 工具的功能描述（中文，供 LLM 决策是否调用）\n"
        "   - api_url: 示例 API 地址（如 https://api.example.com/orders/query）\n"
        "   - method: HTTP 方法（GET/POST/PUT/DELETE）\n"
        "   - auth_type: 认证方式（none / bearer / apikey）\n"
        "   - auth_config: 认证配置对象，根据 auth_type 设置\n"
        "   - input_schema: 入参 JSON Schema（包含 type, properties, required）\n"
        "3. 如果 auth_type 为 bearer，auth_config 为 {type: 'bearer', token: ''}\n"
        "4. 如果 auth_type 为 apikey，auth_config 为 {type: 'apikey', key_name: 'X-API-Key', key_value: ''}\n"
        "5. 如果 auth_type 为 none，auth_config 为 {}\n"
        "6. 所有字段必须有合理的值，不要留空"
        "7. 输出必须是合法的 JSON 格式"
    )
    content = await _call_llm(mc, system_prompt, f"请为以下需求生成工具配置：\n{body.description}", temperature=0.2)

    import json
    import re
    config = None
    try:
        config = json.loads(content)
    except Exception:
        pass
    if config is None:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            try:
                config = json.loads(m.group(1))
            except Exception:
                pass
    if config is None:
        m = re.search(r"(\{[\s\S]*\})", content)
        if m:
            try:
                config = json.loads(m.group(1))
            except Exception:
                pass

    if config is None:
        raise HTTPException(500, "模型未返回合法的工具配置 JSON，请重试")

    # 校验必需字段
    required_fields = ["name", "description", "api_url", "method", "auth_type", "auth_config", "input_schema"]
    missing = [f for f in required_fields if f not in config]
    if missing:
        raise HTTPException(500, f"模型返回的配置缺少字段: {', '.join(missing)}")

    return {"tool": config}


@router.post("/agent")
async def generate_agent(
    body: AgentGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    根据自然语言描述，生成完整的 Agent 配置（名称 + 描述 + 系统提示词）。
    """
    if not body.description.strip():
        raise HTTPException(400, "描述不能为空")

    mc = await _get_active_model(db)
    system_prompt = (
        "你是一个 AI Agent 设计专家。根据用户的需求描述，生成一个完整的 Agent 配置。\n"
        "要求：\n"
        "1. 只输出一个合法的 JSON 对象，不要有任何解释性文字\n"
        "2. JSON 必须包含以下字段：\n"
        "   - name: Agent 名称（中文，如 客服助手）\n"
        "   - description: 功能描述（一句话概括）\n"
        "   - system_prompt: 完整的系统提示词（定义角色、规则、可用 Skill、决策逻辑）\n"
        "3. 所有字段必须有合理的值，不要留空\n"
        "4. 输出必须是合法的 JSON 格式"
    )
    content = await _call_llm(mc, system_prompt, f"请为以下需求生成 Agent 配置：\n{body.description}", temperature=0.3)

    import json
    import re
    config = None
    for pattern in [lambda c: json.loads(c), lambda c: json.loads(re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", c).group(1)), lambda c: json.loads(re.search(r"(\{[\s\S]*\})", c).group(1))]:
        if config is not None:
            break
        try:
            config = pattern(content)
        except Exception:
            pass

    if config is None:
        raise HTTPException(500, "模型未返回合法的 JSON，请重试")

    return {"agent": config}


@router.post("/skill")
async def generate_skill(
    body: SkillGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    根据自然语言描述，生成完整的 Skill 配置（名称 + 描述 + 提示词）。
    """
    if not body.description.strip():
        raise HTTPException(400, "描述不能为空")

    mc = await _get_active_model(db)
    system_prompt = (
        "你是一个 AI Skill 设计专家。根据用户的需求描述，生成一个完整的 Skill 配置。\n"
        "要求：\n"
        "1. 只输出一个合法的 JSON 对象，不要有任何解释性文字\n"
        "2. JSON 必须包含以下字段：\n"
        "   - name: Skill 名称（中文，如 用例生成）\n"
        "   - description: 功能描述（一句话概括）\n"
        "   - prompt: 完整的 Skill 提示词（定义角色、规则、输入输出格式、示例）\n"
        "3. 所有字段必须有合理的值，不要留空\n"
        "4. 输出必须是合法的 JSON 格式"
    )
    content = await _call_llm(mc, system_prompt, f"请为以下需求生成 Skill 配置：\n{body.description}", temperature=0.3)

    import json
    import re
    config = None
    for pattern in [lambda c: json.loads(c), lambda c: json.loads(re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", c).group(1)), lambda c: json.loads(re.search(r"(\{[\s\S]*\})", c).group(1))]:
        if config is not None:
            break
        try:
            config = pattern(content)
        except Exception:
            pass

    if config is None:
        raise HTTPException(500, "模型未返回合法的 JSON，请重试")

    return {"skill": config}


@router.post("/evaluator")
async def generate_evaluator(
    body: EvaluatorGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    根据自然语言描述，生成完整的 Evaluator 配置（名称 + 描述 + 评估提示词 + 评分范围 + 输出格式）。
    """
    if not body.description.strip():
        raise HTTPException(400, "描述不能为空")

    mc = await _get_active_model(db)
    system_prompt = (
        "你是一个 AI 评估器设计专家。根据用户的需求描述，生成一个完整的评估器配置。\n"
        "要求：\n"
        "1. 只输出一个合法的 JSON 对象，不要有任何解释性文字\n"
        "2. JSON 必须包含以下字段：\n"
        "   - name: 评估器名称（中文，如 用例质量评估）\n"
        "   - description: 功能描述（一句话概括）\n"
        "   - prompt: 完整的评估提示词（定义评估维度、评分标准、关注点）\n"
        "   - score_range: 评分范围，格式为 [min, max]，如 [0, 1]\n"
        "   - output_format: 输出格式说明，如 {score: 'float', issues: ['string'], suggestion: 'string'}\n"
        "3. 所有字段必须有合理的值，不要留空\n"
        "4. 输出必须是合法的 JSON 格式"
    )
    content = await _call_llm(mc, system_prompt, f"请为以下需求生成评估器配置：\n{body.description}", temperature=0.3)

    import json
    import re
    config = None
    for pattern in [lambda c: json.loads(c), lambda c: json.loads(re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", c).group(1)), lambda c: json.loads(re.search(r"(\{[\s\S]*\})", c).group(1))]:
        if config is not None:
            break
        try:
            config = pattern(content)
        except Exception:
            pass

    if config is None:
        raise HTTPException(500, "模型未返回合法的 JSON，请重试")

    return {"evaluator": config}
