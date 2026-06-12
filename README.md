# 灵枢引擎

提示词托管平台。把系统提示词从代码里解耦出来，放到目录里统一管理，通过修改 `base_url` 接入，调用方式与 OpenAI SDK 完全兼容。

## 为什么需要它

提示词写在代码里有几个问题：改一个词要重新构建部署、多个服务共用同一套提示词时维护困难、版本管理混乱。灵枢引擎把提示词变成独立的配置文件，服务只负责注入和转发。

```
调用方（OpenAI SDK）
    │  model="translator"
    ▼
灵枢引擎（:5490）
    │  注入 prompt.md 作为 system 消息
    │  注入 schema.json 作为 response_format
    │  替换 model 为 config.toml 里配置的真实模型
    ▼
上游 API（OpenAI / 兼容接口）
```

## 快速开始

**1. 安装**

```bash
git clone <repo>
cd ling-shu
uv sync
```

**2. 配置**

首次启动时会自动创建 `~/.ling-shu/` 工作目录和默认 `config.toml`，直接编辑即可：

```toml
[upstream]
base_url = "https://api.deepseek.com"
api_key  = "sk-..."          # 也可以用 OPENAI_API_KEY 环境变量

[default]
model = "deepseek-v4-flash"  # 所有 agent 默认使用的底层模型

[agents.translator]          # 单独给某个 agent 指定模型（可选）
model = "deepseek-chat"
```

**3. 创建第一个 Agent**

```bash
mkdir ~/.ling-shu/agents/my-agent
```

写提示词 `~/.ling-shu/agents/my-agent/prompt.md`：

```markdown
你是一个专业的客服助手，只回答与产品相关的问题，拒绝回答其他话题。
```

**4. 启动服务**

```bash
uv run python main.py
# Agents directory: C:\Users\xxx\.ling-shu\agents
# Config file:      C:\Users\xxx\.ling-shu\config.toml (found)
# Upstream:         https://api.openai.com
```

**5. 接入调用**

把原来代码里的 `base_url` 改成灵枢引擎地址，`model` 改成 agent 名字，其他一行不动：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:5490/v1",
    api_key="any",   # 鉴权由 config.toml 的 api_key 处理，这里随便填
)

response = client.chat.completions.create(
    model="my-agent",   # ← agent 目录名
    messages=[{"role": "user", "content": "你好"}],
)
print(response.choices[0].message.content)
```

---

## Agent 目录结构

每个 agent 是 `~/.ling-shu/agents/` 下的一个目录：

```
~/.ling-shu/agents/
├── translator/
│   ├── prompt.md       # 系统提示词（必须）
│   └── schema.json     # 结构化输出约束（可选）
└── summarizer/
    └── prompt.md
```

### prompt.md

普通 Markdown 文件，内容会作为 `system` 消息注入到每次请求的最前面。

```markdown
你是一个英中互译助手。
- 检测输入语言，自动翻译成另一种语言
- 保持原文语气和风格
- 不添加任何解释
```

### schema.json

可选。格式直接对应 OpenAI `response_format.json_schema`，服务透传给上游，利用模型原生的结构化输出能力。

```json
{
  "name": "translation_result",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "translation": { "type": "string" },
      "source_language": { "type": "string" }
    },
    "required": ["translation", "source_language"],
    "additionalProperties": false
  }
}
```

---

## 使用示例

### 示例 1：多语言翻译 Agent（带结构化输出）

**`~/.ling-shu/agents/translator/prompt.md`**

```markdown
你是一个专业翻译。检测用户输入的语言，翻译成另一种语言（中文↔英文互译）。
只返回翻译结果，不加解释。
```

**`~/.ling-shu/agents/translator/schema.json`**

```json
{
  "name": "translation_result",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "translation": { "type": "string" },
      "source_language": { "type": "string" }
    },
    "required": ["translation", "source_language"],
    "additionalProperties": false
  }
}
```

**调用**

```python
response = client.chat.completions.create(
    model="translator",
    messages=[{"role": "user", "content": "人工智能正在改变世界"}],
)
# {"translation": "Artificial intelligence is changing the world", "source_language": "Chinese"}
```

---

### 示例 2：代码审查 Agent

**`~/.ling-shu/agents/code-reviewer/prompt.md`**

```markdown
你是一个严格的代码审查员，专注于以下几点：
1. 潜在的 Bug 和边界条件
2. 安全漏洞（注入、越权、敏感信息泄露）
3. 性能问题

每个问题按格式输出：【严重程度】文件:行号 - 问题描述
严重程度分为：CRITICAL / WARNING / INFO
```

**调用**

```python
with open("my_code.py") as f:
    code = f.read()

response = client.chat.completions.create(
    model="code-reviewer",
    messages=[{"role": "user", "content": f"```python\n{code}\n```"}],
)
print(response.choices[0].message.content)
# 【WARNING】app.py:42 - SQL 拼接存在注入风险，建议使用参数化查询
# 【INFO】app.py:78 - 循环内重复查询数据库，可提前批量获取
```

---

### 示例 3：信息提取 Agent（带结构化输出）

**`~/.ling-shu/agents/info-extractor/prompt.md`**

```markdown
从用户提供的文本中提取关键信息。
```

**`~/.ling-shu/agents/info-extractor/schema.json`**

```json
{
  "name": "extracted_info",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "people": {
        "type": "array",
        "items": { "type": "string" },
        "description": "文中提到的人名"
      },
      "dates": {
        "type": "array",
        "items": { "type": "string" },
        "description": "文中提到的日期"
      },
      "organizations": {
        "type": "array",
        "items": { "type": "string" },
        "description": "文中提到的机构或公司"
      }
    },
    "required": ["people", "dates", "organizations"],
    "additionalProperties": false
  }
}
```

**调用**

```python
text = "2024年3月，张伟和李娜在阿里巴巴总部签署了合作协议。"

response = client.chat.completions.create(
    model="info-extractor",
    messages=[{"role": "user", "content": text}],
)
# {"people": ["张伟", "李娜"], "dates": ["2024年3月"], "organizations": ["阿里巴巴"]}
```

---

### 示例 4：流式输出

灵枢引擎完整透传流式响应，调用方不需要任何改动：

```python
stream = client.chat.completions.create(
    model="my-agent",
    messages=[{"role": "user", "content": "写一首关于秋天的诗"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

---

## 透传模式

如果 `model` 对应的 agent 目录不存在，灵枢引擎不做任何注入，按 `config.toml` 的 `[default].model` 直接转发。可以用来把灵枢引擎当纯粹的 API 代理使用。

---

## 配置参考

| 位置 | 配置项 | 说明 |
|---|---|---|
| `config.toml` | `[upstream].base_url` | 上游 API 地址 |
| `config.toml` | `[upstream].api_key` | API Key |
| `config.toml` | `[default].model` | 默认底层模型 |
| `config.toml` | `[agents.<name>].model` | 单个 agent 的底层模型 |
| 环境变量 | `OPENAI_BASE_URL` | 同 `[upstream].base_url`，优先级低于 config.toml |
| 环境变量 | `OPENAI_API_KEY` | 同 `[upstream].api_key`，优先级低于 config.toml |
| `config.toml` | `[server].port` | 服务端口，默认 `5490` |
| 环境变量 | `PORT` | 同 `[server].port`，优先级低于 config.toml |
| 环境变量 | `LING_SHU_DIR` | 工作目录，默认 `~/.ling-shu` |

查看已加载的 agent 列表：

```bash
curl http://localhost:5490/v1/models
```
