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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 首次启动自动建表并初始化默认用户和演示数据
```

### 前端
```bash
cd frontend
npm install
npm run dev  # 访问 http://localhost:5173
```

## 5. 默认账号

首次启动后自动创建：

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| admin | admin123 | admin | 全权限，可管理用户和锁定格式 |
| operator | operator123 | operator | 只能修改业务提示词，不能改返回格式 |

登录获取 Token：
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

## 6. 使用流程

### 基础使用
1. **配置模型** → 模型配置页面，添加LLM供应商（OpenAI/Azure等）
2. **注册工具** → 工具管理页面，注册HTTP外部API
3. **创建Skill** → Skill管理页面，编写提示词，绑定工具
4. **创建Agent** → Agent管理页面，组合Skill，编写推理提示词
5. **在线测试** → 在Agent/Skill详情页测试效果

### 结构化输出（v1.1 新增）
6. **设置返回格式** → 管理员在 Skill 的 response-format 接口设置 JSON Schema
7. **锁定格式** → `response_format_locked=true` 后业务人员无法修改该字段

### 评估与优化
8. **创建评估集** → 数据集页面，添加测试样本
9. **创建评估器** → 评估器页面，定义评分标准
10. **运行实验** → 实验页面，运行评估，查看评分报告
11. **AI自动优化** → 实验详情页，触发AI优化Skill提示词

### 对话驱动流水线（v1.1 新增）
12. **创建对话** → `POST /api/v1/conversations`（绑定 skill_id）
13. **追加消息** → 每轮 user/assistant 交替追加，assistant 轮可标注 rating
14. **确认满意后提交** → `POST /api/v1/conversations/{id}/submit`
15. **流水线自动触发** → 评估集生成 → AI优化 → 实验跑分 → 达标自动上线

## 7. API接口列表

### OpenAI兼容接口（需 API Key）
- `POST /v1/chat/completions` — 聊天（model="agent-{名称}"调用Agent）
- `GET  /v1/models` — 列出所有Agent

### 认证接口
- `POST /api/v1/auth/login` — 登录，返回 JWT Token
- `GET  /api/v1/auth/me` — 当前用户信息

### 用户管理（Admin only）
- `GET/POST   /api/v1/users` — 用户列表 / 新建用户
- `PUT/DELETE /api/v1/users/{id}` — 修改 / 删除用户

### Skill 管理
- `GET/POST      /api/v1/skills` — 列表 / 新建
- `GET/PUT/DELETE /api/v1/skills/{id}` — 详情 / 更新 / 删除
- `GET/PUT       /api/v1/skills/{id}/response-format` — 查看 / 设置返回格式（PUT: Admin only）
- `GET           /api/v1/skills/{id}/versions` — 版本历史
- `POST          /api/v1/skills/{id}/rollback/{version_id}` — 版本回滚（Admin only）

### 对话会话
- `GET/POST   /api/v1/conversations` — 列表 / 新建
- `GET/DELETE /api/v1/conversations/{id}` — 详情 / 删除
- `POST       /api/v1/conversations/{id}/messages` — 追加消息
- `POST       /api/v1/conversations/{id}/submit` — 提交并触发流水线

### 其他管理接口
- `GET/POST /api/v1/agents` — Agent管理
- `GET/POST /api/v1/tools` — 工具管理
- `GET/POST /api/v1/model-configs` — 模型配置
- `GET/POST /api/v1/evaluators` — 评估器
- `GET/POST /api/v1/experiments` — 实验
- `GET      /api/v1/traces` — 调用链路
