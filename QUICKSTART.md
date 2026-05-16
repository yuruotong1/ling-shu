# 灵枢引擎 - 快速启动

## 1. 配置环境变量

```bash
cp .env.example .env
# 修改 .env 中的 PLATFORM_API_KEY 等配置
```

## 2. 一键启动（Docker）

```bash
docker-compose up --build
```

启动后访问：
- 管理界面：http://localhost
- 后端API文档：http://localhost/docs
- 直接后端：http://localhost:8000

## 3. 使用OpenAI SDK调用

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost/v1",
    api_key="sk-platform-dev"  # 与 .env 中 PLATFORM_API_KEY 一致
)

# 调用已配置的Agent
response = client.chat.completions.create(
    model="agent-客服系统",
    messages=[{"role": "user", "content": "我要退货"}]
)
print(response.choices[0].message.content)
```

## 4. 本地开发（不用Docker）

### 后端
```bash
cd backend
pip install -r requirements.txt
# 配置 .env（指向本地PostgreSQL）
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev  # 访问 http://localhost:5173
```

## 5. 使用流程

1. **配置模型** → 模型配置页面，添加LLM供应商（OpenAI/Azure/Anthropic等）
2. **注册工具** → 工具管理页面，注册HTTP外部API
3. **创建Skill** → Skill管理页面，编写提示词，绑定工具
4. **创建Agent** → Agent管理页面，组合Skill，编写推理提示词
5. **在线测试** → 在Agent/Skill详情页测试效果
6. **创建评估集** → 数据集页面，添加测试样本
7. **创建评估器** → 评估器页面，定义评分标准
8. **运行实验** → 实验页面，运行评估，查看评分报告
9. **AI自动优化** → 实验详情页，触发AI优化Skill
10. **查看链路** → 调用链路页面，查看每次Agent执行的完整Trace

## 6. API接口列表

### OpenAI兼容接口（需API Key）
- `POST /v1/chat/completions` - 聊天（model="agent-{名称}"调用Agent）
- `GET /v1/models` - 列出所有Agent

### 管理接口（无需认证）
- `GET/POST /api/v1/agents` - Agent管理
- `GET/POST /api/v1/skills` - Skill管理  
- `GET/POST /api/v1/tools` - 工具管理
- `GET/POST /api/v1/model-configs` - 模型配置
- `GET/POST /api/v1/evaluators` - 评估器
- `GET/POST /api/v1/evaluation-sets` - 评估集
- `GET/POST /api/v1/experiments` - 实验
- `GET /api/v1/traces` - 调用链路
