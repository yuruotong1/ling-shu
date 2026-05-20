# 灵枢引擎 — AI Agent 生产优化平台

> 版本：v1.2.0 · 评估驱动优化的 AI Agent 生产平台
> 版本：v1.2.0 · 评估驱动优化的 AI Agent 生产平台

## 一、平台概述

### 1.1 介绍

**灵枢引擎**是一个评估驱动优化的AI Agent生产平台。

**解决什么问题**：企业使用AI Agent时，提示词写死在代码里改不动、效果好坏凭感觉、优化靠人工试错、数据用完就丢——这些问题导致AI生产效率低、质量不可控、迭代周期长。

**怎么做**：灵枢引擎把提示词从代码中剥离出来独立托管，修改即时生效；通过评估器量化每次AI输出的好坏，发现问题后AI自动优化Skill提示词，人工只需确认；每次调用的输入输出自动留存，成为评估和迭代的数据基础。

**核心价值**：

- **极轻接入**：业务系统改一个base_url即可接入，调用方式与OpenAI SDK完全兼容，零改造
- **效果可量化**：评估器给每次输出打分，改了什么、效果如何，一目了然
- **自动迭代**：AI基于评估结果自动优化Skill，人工只需确认，大幅缩短优化周期
- **模型自由**：不绑定任何模型生态，任意模型可接入对比
- **结构化输出**：为 Agent 定义 JSON Schema，引擎自动校验并容错重试，接口返回格式零崩溃
- **对话即数据**：多轮对话满意后一键提交，自动触发评估→优化→上线的完整流水线
- **Plugin SDK**：原生 Python 插件动态加载，复杂逻辑无需外部服务即可接入

### 1.2 痛点与解决方案

| 痛点 | 解决方案 |
|-----|---------|
| 配置耦合代码：提示词硬编码，修改需走完整发布流程 | **配置即时生效**：提示词独立托管，修改即时生效，无需代码发布 |
| 效果黑盒化：改了Skill不知效果好坏，缺乏量化对比手段 | **评估即资产**：评估标准越迭代越精准，越用越值钱 |
| 返回格式不稳：业务人员改提示词导致接口 JSON 崩溃 | **Format Response**：在系统提示词中定义 JSON Schema，引擎自动校验并重试，格式永不崩溃 |
| 权责不清：非技术人员能随意修改底层返回格式 | **权限分离**：admin 定义/锁定格式，operator 只能改业务提示词 |
| 优化靠人工：提示词调整依赖经验，迭代周期长 | **自动迭代**：AI基于评估结果自动优化Skill，人工只需确认 |
| 对话数据浪费：测试结束即丢弃，无法沉淀为优化素材 | **触发式流水线**：满意对话一键提交，自动生成评估集→跑分→达标上线 |

---

## 二、v1.1 新增能力

### 2.1 JSON 结构化输出（Format Response）

每个 Agent 可由研发人员配置一个 **JSON Schema** 作为返回格式约束。开启后：

1. 引擎自动在系统提示词末尾追加格式要求，强制模型输出 JSON
2. 收到响应后用 `jsonschema` 校验
3. 校验失败时，把错误原因反馈给模型，最多**自动重试 2 次**
4. 3 次均失败则降级返回原始文本（不抛异常，保证接口可用）

**配置方式**：在 Agent 详情页的"返回格式"Tab 中，直接输入 JSON Schema 文本，支持 JSON 格式校验和示例数据测试。

**接口**

```
GET  /api/v1/agents/{id}/response-format          # 查看当前格式配置
PUT  /api/v1/agents/{id}/response-format          # 设置 JSON Schema（Admin only）
POST /api/v1/agents/{id}/response-format/test     # 测试 Schema（验证示例数据）
```

请求体示例：
```json
{
  "response_format": {
    "type": "object",
    "properties": {
      "intent":     { "type": "string", "enum": ["查询","购买","投诉","咨询","其他"] },
      "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
      "reason":     { "type": "string" }
    },
    "required": ["intent", "confidence", "reason"]
  }
}
```

---

### 2.2 权限与职责隔离

平台引入**两级角色**：

| 角色 | 权限 |
|------|------|
| **admin（管理员）** | 所有权限：用户管理、定义 response_format、删除 Skill/工具、版本回滚 |
| **operator（业务人员）** | 可修改 Agent/Skill 的业务提示词（prompt）、创建/运行对话和实验 |

**认证接口**

```
POST /api/v1/auth/login       # 登录，返回 JWT Token
GET  /api/v1/auth/me          # 当前登录用户信息
```

登录示例：
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
# => { "access_token": "eyJ...", "role": "admin", "username": "admin" }
```

**默认账号**（首次启动自动创建）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | admin |
| operator | operator123 | operator |

**用户管理接口（Admin only）**

```
GET    /api/v1/users              # 用户列表
POST   /api/v1/users              # 新建用户
PUT    /api/v1/users/{id}         # 修改用户（密码/角色/状态）
DELETE /api/v1/users/{id}         # 删除用户
```

---

### 2.3 触发式版本控制与评估流水线

**核心理念**：多轮对话是最廉价的高质量数据来源。用户与 Agent/Skill 交互满意后，一键"提交"，平台自动完成从数据沉淀到上线的全流程。

**流水线步骤**

```
用户确认满意并提交对话
    │
    ▼
Step 1：从对话 user↔assistant 配对中生成评估集（EvaluationSet + EvaluationItem）
    │
    ▼
Step 2：AI 自动优化 Skill 提示词（基于对话内容和失败样本），生成新版本（SkillVersion）
    │
    ▼
Step 3：创建实验（Experiment），调用现有评估器对新版本跑分
    │
    ▼
Step 4：avg_score ≥ auto_deploy_threshold（默认 0.75）→ 自动上线新版本
        否则保留 draft，人工决策
```

**对话接口**

```
POST /api/v1/conversations                         # 创建会话（绑定 agent_id 或 skill_id）
POST /api/v1/conversations/{id}/messages           # 追加消息（role: user/assistant）
GET  /api/v1/conversations/{id}                    # 查看会话详情
POST /api/v1/conversations/{id}/submit             # 提交并触发流水线
GET  /api/v1/conversations                         # 会话列表
DELETE /api/v1/conversations/{id}                  # 删除会话
```

提交请求示例：
```json
{
  "run_pipeline": true,
  "auto_deploy_threshold": 0.75,
  "message_updates": [
    { "message_id": "uuid-of-assistant-turn", "reference_output": "标准答案文本" }
  ]
}
```

提交后，`GET /conversations/{id}` 中的 `pipeline_result` 字段实时反映流水线结果：
```json
{
  "eval_set_id": "...",
  "experiment_id": "...",
  "avg_score": 0.82,
  "pass_rate": 0.90,
  "auto_deployed": true,
  "deployed_version": 3
}
```

---

## 二（续）、v1.2 新增能力

### 2.4 Plugin SDK 插件系统

平台新增 **Python SDK 插件** 接入方式，与原有的 HTTP API 接入并行：

| 接入方式 | 适用场景 | 开发成本 |
|---------|---------|---------|
| HTTP API | 已有服务，通过接口暴露能力 | 低（配置即可） |
| **Plugin SDK** | 需要原生 Python 逻辑（如文档解析、数据计算） | 中（按框架写一个类） |

**使用流程**：

```
开发者按 SDK 编写 Python 插件类
        ↓
  打包为 zip（含 plugin.py + requirements.txt）
        ↓
  上传到平台 → 自动解压 → 安装依赖 → 动态加载
        ↓
  Agent/Skill 直接调用，与 HTTP 工具无差别
```

**关键特性**：
- 一个插件可暴露**多个工具**（`@tool` 装饰多个方法）
- 支持**第三方依赖**（`requirements.txt` 自动安装）
- **热更新**：上传新版本后调用 reload 接口即可，无需重启服务
- **跨平台**：Windows / Linux / macOS 通用

📖 **完整开发文档** → [PLUGIN_SDK.md](./PLUGIN_SDK.md)

---

## 二、模块设计

平台采用B/S架构的Web管理系统，核心由三层构成：**Agent → Skill → Tool**。

```
┌─────────────────────────────────────────────────────────────────────┐
│                          外部系统                                    │
│                                                                     │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐       │
│   │ 业务系统A │   │ 业务系统B │   │ 业务系统C │   │  管理后台  │       │
│   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘       │
│        │              │              │              │               │
└────────┼──────────────┼──────────────┼──────────────┼───────────────┘
         │              │              │              │
         │  OpenAI兼容API              │              │ Web管理界面
         ▼              ▼              ▼              │
┌────────────────────────────────────────────────────┼───────────────┐
│                    灵枢引擎                          │               │
│                                                     ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      API 网关                                │   │
│  │          POST /v1/chat/completions                          │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                      │
│                             │ model="agent-xxx"                    │
│                             ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Agent 调度层                               │  │
│  │                                                              │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐               │  │
│  │  │ Agent-审核 │  │ Agent-客服 │  │ Agent-xxx │  ...          │  │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │  │
│  │        │               │               │                      │  │
│  │        │  思考→行动→观察 循环：分析状态、决定行动、观察结果       │  │
│  └────────┼─────────────┼────────┘   │                           │
│           │             │             │                           │
│           ▼             ▼             ▼                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Skill 执行层                               │  │
│  │                                                              │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │  │
│  │  │act-用例生成│ │act-审核  │ │act-数据拉取│ │act-xxx  │      │  │
│  │  └─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘      │  │
│  │        │            │            │            │             │  │
│  │        │  提示词+逻辑：用哪个工具、怎么处理数据                   │  │
│  └────────┼────────────┼────────────┼────────────┼─────────────┘  │
│           │            │            │            │                  │
│           ▼            ▼            ▼            ▼                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Tool 工具层                                │  │
│  │                                                              │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │  │
│  │  │数据库查询  │ │需求文档读取│ │知识库检索  │ │通知推送  │      │  │
│  │  └─────┬────┘ └─────┬────┘ └─────┬────┘ └─────┬────┘      │  │
│  │        │            │            │            │             │  │
│  │        │  外部能力调用（可选）：HTTP/HTTPS API                     │  │
│  │        │  不绑Tool时：纯文本输入→大模型处理→纯文本输出              │  │
│  └────────┼────────────┼────────────┼────────────┼─────────────┘  │
└───────────┼────────────┼────────────┼────────────┼─────────────────┘
            │            │            │            │
            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          外部服务                                    │
│                                                                     │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐       │
│   │  数据库   │   │ 文档系统  │   │  知识库   │   │ 消息系统  │       │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.1 Agent管理

**概念说明**：Agent是灵枢引擎的**智能决策单元**，负责"思考→行动→再思考"的循环过程。Agent不是简单的Skill路由器，而是一个持续推理的过程——观察当前状态、决定下一步行动、执行后根据结果继续推理，直到任务完成。

**Agent运行机制**：

```
用户输入
  ↓
┌──────────────────────────────────┐
│         Agent 循环过程            │
│                                  │
│   思考：分析当前状态，决定下一步     │
│     ↓                            │
│   行动：调用Skill/Tool/直接回复    │
│     ↓                            │
│   观察：获取行动结果               │
│     ↓                            │
│   判断：任务是否完成？             │
│     ├── 否 → 继续思考             │
│     └── 是 → 返回最终结果         │
│                                  │
└──────────────────────────────────┘
  ↓
最终输出
```

**Agent构成要素**：

| 要素 | 说明 |
|-----|------|
| 提示词 | 定义Agent的角色、推理规则、可用Skill及适用场景 |
| Skill组合 | 绑定的Skill集合，Agent在循环中按需调用 |
| 模型 | 调用的LLM及参数配置 |
| 最大循环次数 | 防止无限循环的安全阈值 |

**功能说明**：

| 功能 | 说明 |
|-----|------|
| Agent列表 | 展示所有Agent，显示名称、绑定Skill数、状态、版本 |
| 创建Agent | 填写名称 → 绑定Skill组合 → 编写推理提示词 → 选择模型 → 设置最大循环次数 |
| 推理提示词编辑 | 定义Agent的思考框架：如何分析问题、何时调用Skill、如何判断任务完成 |
| 版本管理 | 配置变更自动版本化，支持回滚；版本历史可查看每版的系统提示词 |
| 在线测试 | 多轮对话测试，支持 Enter 发送 / Shift+Enter 换行，可查看每轮"思考→行动→观察"的完整过程 |
| 循环过程可视化 | 展示Agent的每一步推理和决策，便于调试和优化 |
| 返回格式 | 支持 JSON Schema 文本配置，内置 JSON 校验和示例数据测试 |

**调用方式**：

Agent通过`model="agent-xxx"`对外暴露，用户自然语言交互，Agent进入思考→行动→再思考的循环：

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://灵枢引擎地址/v1",
    api_key="sk-platform-xxxxx"
)

# 第一轮：用户发起请求
response = client.chat.completions.create(
    model="agent-客服系统",
    messages=[{"role": "user", "content": "我要退货"}]
)
# Agent返回：请问您的订单号是多少？

# 第二轮：用户提供信息，继续对话
response = client.chat.completions.create(
    model="agent-客服系统",
    messages=[
        {"role": "user", "content": "我要退货"},
        {"role": "assistant", "content": "请问您的订单号是多少？"},
        {"role": "user", "content": "OR20250001"}
    ]
)
# Agent返回：订单OR20250001金额299元，确认退款吗？

# 第三轮：用户确认
response = client.chat.completions.create(
    model="agent-客服系统",
    messages=[
        {"role": "user", "content": "我要退货"},
        {"role": "assistant", "content": "请问您的订单号是多少？"},
        {"role": "user", "content": "OR20250001"},
        {"role": "assistant", "content": "订单OR20250001金额299元，确认退款吗？"},
        {"role": "user", "content": "确认"}
    ]
)
# Agent返回：退款299元已处理，预计3-5个工作日到账
```

```
用户: 我要退货

Agent循环过程：
  第1轮 思考: 用户要退货，需要先查询订单信息 → 行动: 调用 act-订单查询
  第1轮 观察: 未提供订单号，需要追问
  第2轮 思考: 信息不足，需要向用户确认订单号 → 行动: 直接回复追问
  第2轮 观察: 用户提供订单号 OR20250001
  第3轮 思考: 已获取订单号，查询订单详情 → 行动: 调用 act-订单查询(OR20250001)
  第3轮 观察: 订单存在，金额299元，符合退货条件
  第4轮 思考: 确认退款，需用户二次确认 → 行动: 直接回复确认
  第4轮 观察: 用户确认
  第5轮 思考: 用户已确认，执行退款 → 行动: 调用 act-退款处理
  第5轮 观察: 退款成功
  → 返回最终结果: 退款299元已处理，预计3-5个工作日到账
```

高风险Skill（如退款）默认需要确认；低风险Skill可配置为直接执行。

**Agent配置示例**：

```json
{
  "name": "客服系统",
  "model": "agent-客服系统",
  "system_prompt": "你是一个客服助手，负责处理用户的订单和退款问题。\n\n## 可用Skill\n- 用例生成：生成测试用例\n- 订单查询：查询订单详情\n- 退款处理：处理退款申请\n\n## 推理规则\n- 先确认用户意图，再决定调用哪个Skill\n- 涉及退款等高风险操作，必须先向用户确认\n- 信息不足时主动追问，不要猜测\n- 任务完成后简洁回复结果",
  "skills": ["用例生成", "订单查询", "退款处理"],
  "max_loops": 10,
  "risk_control": {
    "confirm_required": ["退款处理"],
    "auto_execute": ["用例生成", "订单查询"]
  },
  "model_config": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 4000
  }
}
```

---

### 3.2 Skill管理

**概念说明**：Skill是Agent的**内部执行单元**，封装了提示词和输出规范。Skill不对外暴露，只能被Agent在思考→行动→观察循环中调度执行。

**层级关系**：

```
Agent（思考→行动→观察循环）
  ├── Skill A（具体能力）
  ├── Skill B（具体能力）
  └── Skill C（具体能力）
        └── Tool X（外部能力，可选）
```

**Skill构成要素**：

| 组成部分 | 说明 |
|---------|------|
| 提示词文档（Markdown） | Skill的核心指令，定义角色、行为规则、约束、示例 |
| 内置知识库工具 | 默认绑定的知识库工具，提供数据存取能力，每个Skill自动拥有 |
| 外部工具绑定（可选） | Skill可调用的其他外部能力，不绑时仅靠内置知识库+大模型 |

Skill本质上就是一个Markdown文件，加载到模型上下文中作为指令执行。输入就是用户的messages，输出由模型自主生成。模型配置由所属Agent统一管理，Skill自身不配置模型。每个Skill默认绑定一个知识库工具，用于存取该Skill专属的知识数据。

**Skill配置示例**：

```json
{
  "name": "用例生成",
  "prompt": "# 用例生成\n\n你是一个专业的测试用例生成工程师。\n\n## 规则\n- 根据需求描述生成功能测试用例\n- 每条用例包含：用例编号、前置条件、操作步骤、预期结果\n- 优先覆盖正常场景，再补充异常场景\n- 输出JSON格式\n- 生成前先从知识库检索相关历史用例作为参考\n\n## 示例\n输入：{\"requirement\": \"用户登录功能\"}\n输出：\n{\n  \"test_cases\": [\n    {\n      \"id\": \"TC001\",\n      \"precondition\": \"用户已注册\",\n      \"steps\": \"1. 打开登录页 2. 输入正确账号密码 3. 点击登录\",\n      \"expected\": \"登录成功，跳转首页\"\n    }\n  ]\n}",
  "knowledge_base": "skill-用例生成",
  "tools": []
}
```

`knowledge_base`字段指定该Skill绑定的知识库命名空间，默认为`skill-{Skill名称}`，所有Skill自动拥有。

**功能说明**：

| 功能 | 说明 |
|-----|------|
| Skill列表 | 展示所有Skill，显示名称、绑定工具数、版本、评估得分 |
| 创建/编辑 | 支持修改名称（保证唯一性）、描述、提示词、绑定工具/知识库 |
| 知识库管理 | 管理该Skill专属知识库，上传/删除文档，查看检索结果 |
| 外部工具绑定 | 从已注册工具中选择绑定，配置调用参数和条件 |
| 内嵌测试 | 输入数据直接看效果 |
| 版本管理 | 自动版本化，版本历史可查看每版的提示词内容；支持回滚 |

**版本管理策略**：
- 每次保存自动生成新版本，保留完整历史
- 版本间差异对比
- A/B测试：一键回滚

---

### 3.3 工具管理

**概念说明**：Tool是Skill调用的**底层能力单元**。工具分为两类：**内置工具**（平台自带，开箱即用）和**外部工具**（用户注册的HTTP/HTTPS API）。

#### 内置知识库工具

每个Skill默认绑定一个专属知识库，平台自动提供知识库工具，无需注册即可使用。知识库基于向量检索，Skill在执行时可直接调用存取数据。

**知识库API**：

| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/kb/{namespace}/documents` | POST | 上传文档（支持TXT/Markdown/PDF） |
| `/api/v1/kb/{namespace}/documents` | GET | 获取文档列表 |
| `/api/v1/kb/{namespace}/documents/{id}` | DELETE | 删除文档 |
| `/api/v1/kb/{namespace}/search` | POST | 语义检索，入参：query + top_k |
| `/api/v1/kb/{namespace}/data` | POST | 写入结构化数据（key-value） |
| `/api/v1/kb/{namespace}/data/{key}` | GET | 读取结构化数据 |
| `/api/v1/kb/{namespace}/data/{key}` | DELETE | 删除结构化数据 |

其中`namespace`为知识库命名空间，默认为`skill-{Skill名称}`，Skill调用时自动填充。

**检索接口示例**：

```json
// POST /api/v1/kb/skill-用例生成/search
{
  "query": "登录功能异常场景",
  "top_k": 5
}

// 响应
{
  "results": [
    {
      "content": "密码错误3次锁定账号，锁定时间30分钟...",
      "source": "历史用例集.md",
      "score": 0.89
    }
  ]
}
```

**写入数据示例**：

```json
// POST /api/v1/kb/skill-用例生成/data
{
  "key": "login_edge_cases",
  "value": "密码错误3次锁定、空密码提示、特殊字符密码"
}
```

#### 外部工具

用户注册的HTTP/HTTPS API，统一以标准格式接入。

**工具配置项**：

| 配置项 | 说明 |
|-------|------|
| 名称 | 工具名称（供Skill引用） |
| 描述 | 功能描述（供模型决策是否调用） |
| API地址 | HTTP/HTTPS endpoint |
| 请求方法 | GET / POST / PUT / DELETE |
| 入参Schema | JSON Schema，自动转为Function Calling格式 |
| 出参Schema | 响应结构定义 |
| 认证方式 | API Key / Bearer Token / 自定义Header |

#### Plugin SDK 插件（v1.2 新增）

除 HTTP API 外，平台支持通过 **Python SDK** 开发原生插件。开发者按框架编写 Python 代码，打包为 zip 上传，平台自动解压、安装依赖并动态加载，无需重启服务即可使用。

**核心特点**：
- **跨平台**：不依赖操作系统特性，Windows / Linux / macOS 通用
- **动态加载**：`importlib` 运行时加载，热更新支持
- **无缝集成**：插件工具自动纳入 LLM function calling 体系

**快速示例**：

```python
# plugin.py
from app.plugin_sdk import BasePlugin, tool

class WordParserPlugin(BasePlugin):
    name = "word_parser"
    description = "Word文档解析工具"

    @tool(name="extract_text", description="提取文本", schema={...})
    async def extract_text(self, content: str) -> dict:
        return {"text": content}
```

打包上传后，平台自动暴露为可调用的工具，Agent/Skill 可直接使用。

📖 **完整开发文档** → [PLUGIN_SDK.md](./PLUGIN_SDK.md)

**功能说明**：

| 功能 | 说明 |
|-----|------|
| 工具列表 | 展示所有已注册工具，显示名称、类型、调用次数、状态 |
| 注册工具 | 填写API地址、请求方法、入参/出参Schema |
| 认证配置 | API Key / OAuth / 自定义Header，凭证加密存储 |
| 测试连通 | 一键发送测试请求，验证返回格式 |
| 调用日志 | 完整记录：谁调的、什么时候、入参出参、耗时、状态 |

**接入示例**：

```json
{
  "name": "query_test_cases",
  "description": "查询指定轮次和模块下的测试用例",
  "api_url": "https://内部系统/api/testcases/query",
  "method": "POST",
  "input_schema": {
    "type": "object",
    "required": ["round", "module"],
    "properties": {
      "round": {"type": "integer", "description": "测试轮次"},
      "module": {"type": "string", "description": "模块名称"}
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "testcases": {"type": "array"},
      "total": {"type": "integer"}
    }
  },
  "auth": {"type": "bearer", "token": "xxx"}
}
```

**典型工具场景**：

| 场景 | 工具示例 | 说明 |
|-----|---------|------|
| 数据库查询 | `query_test_cases(round, module)` | 查询测试用例 |
| 需求文档读取 | `fetch_requirement(doc_id)` | 读取需求文档 |
| 知识库检索 | `search_knowledge(query, top_k)` | 语义检索文档 |
| 外部系统通知 | `send_notification(channel, message)` | 发送通知 |

---

### 3.4 模型配置

**功能说明**：

| 功能 | 说明 |
|-----|------|
| 多供应商支持 | OpenAI、Azure OpenAI、Anthropic (Claude)、Ollama/vLLM、自定义OpenAI兼容endpoint |
| 配置项 | API Endpoint、API Key（编辑时可见完整内容）、默认参数（temperature、max_tokens等） |
| 路由策略 | 支持主备自动切换 |
| 状态监控 | 实时显示各模型连接状态和调用量 |

---

### 3.5 质量评估与自动迭代

灵枢引擎的核心闭环：**评估发现问题 → AI自动优化Skill → 验证效果 → 发布上线**。

优化Skill有两条触发路径：

| 路径 | 触发方式 | 场景 |
|-----|---------|------|
| 自动触发 | 评估得分低于阈值 | 系统自动发现质量下降 |
| 人工触发 | 对话中发出优化指令 | 人通过多轮对话发现效果不满意，主动要求优化 |

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   调用自动留存数据 ──→ 评估集 ──→ 评估器打分 ──→ 评估报告             │
│                                                  │                   │
│                                            得分低于阈值？            │
│                                           ┌─────┴─────┐            │
│                                           │ 是        │ 否          │
│                                           ↓           ↓            │
│  人工对话反馈 ──→ AI自动优化Skill          结束                       │
│  （多轮对话后         │                                                │
│   发出优化指令）      ↓                                                │
│              创建新版本 → 跑评估集 → 对比得分                         │
│                                    │                                  │
│                             ┌──────┴──────┐                          │
│                             │ 提升        │ 下降/持平                 │
│                             ↓            ↓                          │
│                          待确认 → 人工决策  丢弃，记录原因             │
│                             │                                        │
│                       采纳/修改采纳/拒绝                               │
│                             │                                        │
│                        发布上线 → 持续观测                             │
│                             │                                        │
│                       效果变差？→ 一键回滚                             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

**评估**：定义"什么叫好"，量化Skill效果。

三个核心概念：

| 概念 | 说明 | 类比 |
|-----|------|------|
| 评估器（Evaluator） | 定义评分标准：评估提示词 + 评分维度 + 输出格式 | 评分规则 |
| 评估集（Evaluation Set） | 标准测试数据：input + reference_output | 考卷 |
| 实验（Experiment） | 指定Agent/Skill版本，跑评估集，生成评分报告 | 考试 |

评估器配置示例：

```json
{
  "name": "用例质量评估",
  "prompt": "你是一个测试用例质量评审专家。请根据以下标准对测试用例评分：\n1. 覆盖度：是否覆盖正常/异常/边界场景\n2. 可执行性：步骤是否明确、可操作\n3. 完整性：是否包含前置条件、操作步骤、预期结果",
  "score_range": [0, 1],
  "output_format": {
    "score": "float",
    "issues": ["string"],
    "suggestion": "string"
  }
}
```

评估运行流程：

1. 选择目标：Agent或Skill（指定版本）
2. 选择评估集 + 评估器
3. 自动执行：逐条输入评估集 → 获取目标输出 → 送入评估器打分
4. 生成报告：平均分、各条目得分、失败样本详情

实验（版本对比）：同时跑两个版本，同一份评估集和评估器，直接对比：

| 版本 | 评估集 | 平均分 | 失败数 | 变更摘要 |
|-----|-------|-------|-------|---------|
| v1.2 | 用例评估集-01 | 0.72 | 8/30 | — |
| v1.3 | 用例评估集-01 | 0.85 | 3/30 | 补充了异常场景约束 |

---

**自动迭代**：评估发现问题后，AI自动优化Skill。

触发条件（Skill级别独立配置）：

| 触发条件 | 说明 |
|---------|------|
| 评估得分低于阈值 | 如：平均分 < 0.7 |
| 失败率超过阈值 | 如：失败率 > 30% |
| 定时触发 | Cron表达式，如每天凌晨 |
| 人工触发 | 手动点击"启动自动迭代" |

版本生命周期：

```
v1.2（当前）──→ AI优化生成 v1.3-draft ──→ 验证通过 ──→ 待确认
                                                        │
                                          ┌─────────────┼─────────────┐
                                          │             │             │
                                       采纳        修改后采纳        拒绝
                                          │             │             │
                                      v1.3上线     v1.3上线       保留v1.2
                                                       (含修改)
                                          │
                                     线上效果变差？→ 一键回滚到v1.2
```

全链路观测：

| 观测项 | 说明 |
|-------|------|
| 调用链路 | 用户输入 → Agent调度 → Skill执行 → 模型调用 → 输出，完整Trace可查 |
| 评估监控 | 每次评估的得分趋势、失败样本分布 |
| 迭代追踪 | 每次自动迭代的完整记录：触发→诊断→修改→验证→决策 |
| 异常告警 | 错误率飙升、耗时异常、评估得分骤降时自动通知 |

---

### 3.6 数据集管理

**概念说明**：数据集是评估体系的基础设施，为评估器提供标准测试用例，为自动迭代提供验证样本。

**数据来源**：

| 方式 | 说明 |
|-----|------|
| 调用自动留存 | 每次调用Agent的输入输出自动保存为数据样本，这是数据集的核心来源 |
| 手动录入 | Web界面逐条添加input + reference_output |
| 文件导入 | 支持TXT、JSON、CSV格式批量导入 |

**调用自动留存机制**：

业务系统通过`model="agent-xxx"`调用灵枢引擎，每次请求的输入(messages)和输出(response)自动保存为数据样本，无需额外接口。数据按粒度分为两层：

```
业务系统调用 agent-用例生成
       ↓
灵枢引擎处理请求 → 返回结果
       ↓
自动保存为两层粒度的数据：
  ┌─ Agent数据：完整的输入输出，对应Agent整体效果
  └─ Skill数据：Agent内部每次Skill调用的输入输出，对应单个Skill效果
       ↓
进入数据集，按粒度标记，用于不同层级的评估
```

| 自动留存字段 | 说明 |
|------------|------|
| input | 用户输入的messages |
| output | Agent返回的完整结果 |
| data_type | 数据粒度：agent / skill |
| agent_name | 所属Agent名称 |
| agent_version | 调用时Agent的版本号 |
| skill_name | 所属Skill名称（Skill数据时填充） |
| skill_version | 调用时Skill的版本号（Skill数据时填充） |
| eval_score | 评估器自动打分（如已配置） |
| metadata | 调用时间、耗时、token用量等 |

**数据粒度说明**：

| 粒度 | 保存内容 | 用途 |
|-----|---------|------|
| Agent数据 | 用户输入 → Agent完整输出 | 评估Agent整体效果、端到端质量 |
| Skill数据 | Agent内部每次Skill调用 → Skill输出 | 评估单个Skill效果、定位具体Skill问题 |

**数据集用途**：

| 用途 | 说明 |
|-----|------|
| 评估测试 | 标记优质样本作为评估集，跑Agent/Skill评分 |
| 回归验证 | Skill修改后重跑，防止优化后退步 |
| 自动迭代 | 失败样本驱动AI定位问题、生成优化方案 |

---

## 三、技术实现

### 4.1 API设计（OpenAI兼容）

**核心接口**：

| 接口 | 说明 |
|-----|------|
| `POST /v1/chat/completions` | 核心聊天接口（支持多轮对话） |
| `GET /v1/models` | 列出可用Agent/Skill |

**Agent/Skill列表**：

```json
{
  "data": [
    {"id": "agent-用例生成", "object": "model", "owned_by": "platform"},
    {"id": "agent-审核", "object": "model", "owned_by": "platform"},
    {"id": "agent-客服系统", "object": "model", "owned_by": "platform"}
  ]
}
```

**请求/响应格式**：

```json
// 请求
{
  "model": "agent-用例生成",
  "messages": [{"role": "user", "content": "生成登录功能的测试用例"}],
  "temperature": 0.7,
  "max_tokens": 1000
}

// 响应（OpenAI兼容格式）
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "agent-用例生成",
  "choices": [{
    "message": {"role": "assistant", "content": "订单OR20250001状态：已发货"},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50},
  "trace_id": "trace-xxx"
}
```

### 4.2 技术选型

| 层级 | 技术选型 | 选型理由 |
|-----|---------|---------|
| 后端框架 | FastAPI (Python) | 异步高性能，自动OpenAPI文档，AI生态集成良好 |
| Web框架 | Vue 3 + TypeScript | 组合式API，响应式系统优秀 |
| UI组件库 | Element Plus | Vue生态成熟组件库 |
| 数据库 | PostgreSQL | 结构化数据存储，JSON支持强 |
| 缓存 | Redis | 会话缓存，限流计数器 |
| 向量库 | Qdrant | 轻量易部署，性能优异 |
| 对象存储 | MinIO | S3兼容，私有化部署友好 |
| 部署 | 脚本一键部署 | 快速启动，环境一致 |

### 4.3 竞品对比

| 维度 | 灵枢引擎 | 扣子罗盘 | LangSmith | Promptfoo |
|-----|-------|---------|-----------|-----------|
| 接入成本 | **极低，改一个base_url即可，零改造** | 需接入Coze生态，绑定平台 | 需接入LangChain，有框架依赖 | 需编写测试配置，有学习成本 |
| 模型支持 | **任意模型，不绑定任何生态** | 字节系为主，外部模型受限 | LangChain支持的模型 | 多模型但配置繁琐 |
| 提示词管理 | **提示词独立托管，修改即时生效，无需发版** | 平台内管理，但绑定Coze | 无独立提示词管理 | 配置文件管理 |
| 数据沉淀 | **AI生成数据自动留存，推理成本不白花** | 有限 | 有限 | 无 |
| 评估体系 | **评估标准可复用、可迭代，越用越精准** | Prompt级评估 | 轨迹级，但无标准复用 | 测试用例级，无持续优化 |
| 私有化 | ✅ 支持 | ❌ 不支持 | ❌ 不支持 | ✅ 支持 |

**核心差异化**：
- **极轻接入**：改一个base_url即可
- **模型自由**：不绑定任何模型生态
- **评估即资产**：标准越迭代越值钱
- **自动迭代**：AI基于评估结果自动优化Skill，人工只需确认

## 四、典型场景

### 场景一：测试用例生成

**痛点**：提示词写死在代码中，调整需更新代码、重新部署；生成数据随用随丢。

**灵枢引擎解决**：
1. 提示词托管在灵枢引擎，通过`agent-用例生成`调用，修改即时生效
2. 每次调用输入输出自动留痕
3. 基于评估效果优化提示词："这批用例覆盖度不够"→修改→重跑→对比

**接入方式**：

| 项目 | 说明 |
|-----|------|
| 调用方式 | `model="agent-用例生成"` |
| 入参 | 需求描述、功能说明、测试类型等文字信息 |
| 出参 | 测试用例（文字），支持JSON结构 |
| 业务侧职责 | 传入需求信息，拿到用例后存入测试管理系统 |
| 平台侧职责 | 提示词优化、模型选型、用例质量评估 |

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://灵枢引擎地址/v1",
    api_key="sk-xxxxx"
)

response = client.chat.completions.create(
    model="agent-用例生成",
    messages=[{"role": "user", "content": json.dumps({
        "requirement": "用户登录功能，支持手机号+验证码和账号密码两种方式",
        "function_desc": "登录页面包含手机号输入、验证码发送、账号密码输入、登录按钮",
        "test_type": "功能测试"
    })}]
)
# response.choices[0].message.content → 测试用例（JSON结构）
```

### 场景二：审核

**痛点**：审核规则分散；不同场景需不同规则组合；效果无法量化。

**灵枢引擎解决**：
1. 将数据库查询、文档读取等注册为HTTP API工具
2. 审核规则以Skill形式托管，每条规则是独立的`act-审核规则xxx`
3. `agent-审核系统`编排执行：数据拉取 → 依次审核 → 汇总报告

**接入方式**：

| 项目 | 说明 |
|-----|------|
| 调用方式 | `model="agent-审核"` |
| 入参 | 待审核内容、审核字段 |
| 出参 | 审核结果，支持JSON结构（可在平台配置输出格式） |
| 业务侧职责 | 传入待审核内容，拿到结果后执行业务处理 |
| 平台侧职责 | 审核规则提示词管理、多规则编排、审核效果优化 |

```python
response = client.chat.completions.create(
    model="agent-审核",
    messages=[{"role": "user", "content": json.dumps({
        "content": "测试用例文本内容...",
        "fields": ["错别字", "格式规范", "逻辑完整性"]
    })}]
)
# response.choices[0].message.content → 审核结果（JSON结构）
```

### 场景三：测试报告解析

**痛点**：解析提示词需反复调整；效果无法统一评估和对比。

**灵枢引擎解决**：
1. 解析提示词托管在灵枢引擎，支持不同报告模板配置不同变体
2. 解析结果自动留痕，可直接反馈"这条解析不对"
3. 反馈进入评估流程，形成优化闭环

### 场景四：对话式反馈优化

人在平台上使用AI生成内容后，如果效果不满意，可以直接对话补充要求；满意后，补充的信息自动提炼为Skill优化建议，进入自动迭代流程。

```
用户: 帮我生成登录功能的测试用例
AI:   [生成一版用例]
用户: 不太好，你应该加上异常场景，比如密码错误、账号锁定
AI:   [补充异常场景，重新生成]
用户: 这版可以了 ✅
      ↓
灵枢引擎自动处理：
  - 提炼优化建议：用户补充了"异常场景"维度
  - 纳入评估集：完整对话链作为评估样本
  - 触发自动迭代：AI根据建议修改Skill提示词 → 跑评估验证 → 人工确认
```

**反馈API**：

| 接口 | 说明 |
|-----|------|
| `POST /v1/chat/completions` | 对话接口（支持多轮） |

```python
# 多轮对话优化
response1 = client.chat.completions.create(
    model="agent-用例生成",
    messages=[{"role": "user", "content": "生成登录功能的测试用例"}]
)

# 不满意，补充要求继续对话
response2 = client.chat.completions.create(
    model="agent-用例生成",
    messages=[
        {"role": "user", "content": "生成登录功能的测试用例"},
        {"role": "assistant", "content": response1.choices[0].message.content},
        {"role": "user", "content": "加上异常场景，比如密码错误、账号锁定"}
    ]
)
```

**灵枢引擎内部处理**：

```
反馈提交 → 提炼优化建议（用户补充了什么、改了什么）
         → 纳入评估集（完整对话链作为评估样本）
         → 触发自动迭代（AI修改Skill → 跑评估 → 人工确认发布）
```

---

## 八、部署指南

### 8.1 目录结构

```
ling-shu/
├── backend/              # FastAPI 后端
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
├── frontend/             # Vue3 前端
│   ├── Dockerfile
│   └── src/
├── docker-compose.yml    # 一键部署编排
├── nginx.conf            # 反向代理配置
└── .env                  # 环境变量（不提交到 Git）
```

### 8.2 方式一：Docker Compose（推荐）

**前置条件**：Docker 20.10+，Docker Compose v2

**步骤**：

```bash
# 1. 克隆项目
git clone <repo-url>
cd ling-shu

# 2. 复制并修改环境变量
cp .env.example .env
# 必改项：
#   SECRET_KEY       → 随机字符串（openssl rand -hex 32）
#   PLATFORM_API_KEY → 对外暴露的 API Key

# 3. 启动全部服务
docker-compose up -d --build

# 4. 查看启动状态
docker-compose ps
docker-compose logs -f backend
```

**访问地址**：

| 地址 | 说明 |
|------|------|
| http://localhost | 管理界面（Nginx 入口） |
| http://localhost/docs | FastAPI 交互式文档 |
| http://localhost/api/v1/... | 管理 API |
| http://localhost/v1/chat/completions | OpenAI 兼容接口 |

**停止/重启**：

```bash
docker-compose down          # 停止，保留数据卷
docker-compose down -v       # 停止并删除数据（慎用）
docker-compose restart backend   # 单独重启后端
```

### 8.3 方式二：本地开发模式

无需 Docker，适合开发调试。数据库使用内置 SQLite，无需额外安装。

```bash
# ── 后端 ──────────────────────────────────────────
cd backend
pip install -r requirements.txt

# 启动（SQLite 自动建表 + 种子数据）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── 前端（新终端）────────────────────────────────
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 8.4 环境变量说明

`.env` 文件完整配置说明：

```dotenv
# 数据库（Docker 模式用 PostgreSQL，本地开发默认 SQLite 无需配置）
DATABASE_URL=postgresql+asyncpg://lingzhu:lingzhu123@postgres:5432/lingzhu
SYNC_DATABASE_URL=postgresql://lingzhu:lingzhu123@postgres:5432/lingzhu

# Redis（Docker 模式使用，本地开发可留空）
REDIS_URL=redis://redis:6379/0

# 安全密钥（生产环境必须替换为随机字符串）
SECRET_KEY=dev-secret-key-please-change-in-production

# 环境标识
APP_ENV=development   # development | production

# 允许的前端域名（多个用逗号分隔）
CORS_ORIGINS=http://localhost,http://localhost:3000,http://localhost:5173

# 外部调用 OpenAI 兼容接口所需的 API Key
PLATFORM_API_KEY=sk-platform-dev
```

> **生产环境**：`SECRET_KEY` 请使用 `openssl rand -hex 32` 生成，`PLATFORM_API_KEY` 更换为强密钥。

### 8.5 网络架构

```
用户浏览器 / 业务系统
       │
       ▼
  Nginx :80
  ├── /v1/*    → backend:8000  （OpenAI 兼容接口，需 PLATFORM_API_KEY）
  ├── /api/*   → backend:8000  （管理 API，需 JWT Token）
  ├── /docs    → backend:8000  （API 文档）
  └── /*       → frontend:80   （Vue3 前端静态文件）
       │
  backend:8000 (FastAPI)
  ├── SQLite（开发）或 PostgreSQL（生产）
  └── Redis（可选，用于缓存）
```

### 8.6 数据持久化

Docker Compose 模式下，数据通过具名卷持久化：

```yaml
volumes:
  postgres_data:   # PostgreSQL 数据
  redis_data:      # Redis 数据
```

本地开发模式下，数据存储在 `backend/lingzhu.db`（SQLite 文件）。

### 8.7 升级

```bash
# 拉取新代码
git pull

# 重新构建并重启
docker-compose up -d --build

# 查看后端日志确认启动成功
docker-compose logs -f backend
```

---

