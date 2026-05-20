# 灵枢平台 Plugin SDK 开发指南

## 概述

灵枢平台支持通过 **Python SDK** 开发插件。开发者按框架编写 Python 代码，打包为 zip 上传，平台即可动态加载并直接调用插件功能。

**核心特点：**
- **自包含**：插件自带 `sdk.py`，不依赖平台任何 Python 包
- **离线运行**：所有依赖打包进 zip，部署环境无需网络、无需 pip
- **跨平台**：纯 Python 逻辑可在 Windows / Linux / macOS 上运行
- **动态加载**：zip 上传后平台自动解压加载，与 Agent 无缝集成

---

## 快速开始

### 1. 下载示例模板

在灵枢平台**工具管理**页面，点击 **"下载示例"** 按钮，获取插件开发模板：

```
lingzhu-plugin-demo.zip
├── my_plugin/
│   ├── sdk.py           # SDK 基类（不要修改）
│   ├── plugin.py        # 你的插件代码（按示例修改）
│   └── requirements.txt # 第三方依赖声明
├── build_plugin.py      # 打包脚本
└── README.txt           # 使用说明
```

### 2. 编写插件代码

修改 `my_plugin/plugin.py`：

```python
from sdk import BasePlugin, tool

class MyPlugin(BasePlugin):
    name = "word_parser"
    description = "Word文档解析工具"
    version = "1.0.0"
    author = "your_name"

    @tool(
        name="extract_text",
        description="提取Word文档纯文本",
        schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Word文件路径"}
            },
            "required": ["file_path"]
        }
    )
    async def extract_text(self, file_path: str) -> str:
        # 你的业务逻辑
        return "提取的文本内容"
```

### 3. 打包

在**能上网的开发机器**上运行打包脚本：

```bash
cd lingzhu-plugin-demo
python build_plugin.py my_plugin
```

打包脚本会自动：
1. 验证 `plugin.py` 语法
2. 读取 `requirements.txt`，把依赖安装到 `my_plugin/deps/` 目录
3. 清理缓存文件
4. 打包为 `dist/my_plugin.zip`

### 4. 上传使用

在灵枢平台**工具管理**页面，点击 **"上传插件"**，选择 `dist/my_plugin.zip` 即可。

平台会自动解压加载，无需重启服务。

---

## 插件目录结构

一个完整的插件包（打包后的 zip）内容如下：

```
my_plugin.zip
├── sdk.py           # 【必须】SDK 基类，插件自带
├── plugin.py        # 【必须】入口文件，定义插件类
├── requirements.txt # 【可选】依赖清单（仅用于查看，实际依赖在 deps/ 中）
├── deps/            # 【可选】第三方依赖包（pip install -t 生成）
│   ├── docx/
│   ├── lxml/
│   └── ...
└── ...              # 其他资源文件
```

**关键说明**：
- `sdk.py` 必须放在根目录，插件通过 `from sdk import BasePlugin, tool` 引用
- `deps/` 目录由 `build_plugin.py` 自动生成，包含所有依赖的 Python 包
- 平台加载插件时，会把 `deps/` 加入 `sys.path`，插件内部 `import` 即可找到依赖

---

## SDK API 详解

### `BasePlugin` 基类

所有插件必须继承 `BasePlugin`（从 `sdk.py` 导入）。

**必须覆盖的类属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 插件唯一标识名（英文，不含空格） |
| `description` | `str` | 插件功能描述 |

**可选覆盖的类属性：**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `version` | `str` | `"1.0.0"` | 版本号 |
| `author` | `str` | `""` | 作者信息 |

**实例方法：**

- `get_tools() -> list[dict]` — 返回该插件暴露的所有工具定义
- `execute(tool_name: str, params: dict) -> Any` — 执行指定工具

### `@tool` 装饰器

用于标记插件类中的方法为对外暴露的工具。

```python
@tool(
    name="工具名",           # 默认使用函数名
    description="工具描述", # 默认使用函数 docstring
    schema={...}            # 输入参数 JSON Schema，默认空对象
)
async def my_method(self, arg1: str, arg2: int = 0) -> dict:
    ...
```

**参数说明：**

- `name`: LLM function calling 时使用的工具名
- `description`: 告诉 LLM 这个工具是做什么的
- `schema`: 符合 JSON Schema 规范的参数定义

**方法签名要求：**
- 第一个参数必须是 `self`
- 其他参数名和类型应与 `schema` 中的 `properties` 对应
- 支持 `async` 和同步方法
- 返回值会被序列化为 JSON 字符串

---

## 依赖管理（离线打包）

灵枢平台的部署环境**不保证有外网、不保证有 pip**。因此，所有第三方依赖必须在开发阶段通过打包脚本离线处理。

### 打包原理

`build_plugin.py` 的核心逻辑：

```bash
# 1. 把依赖安装到插件目录下的 deps/ 文件夹
pip install -r requirements.txt -t ./my_plugin/deps

# 2. 打包时把 deps/ 一起打进 zip
# 平台加载时把 deps/ 加入 sys.path，import 即可使用
```

### 完整流程

**步骤 1**：在 `requirements.txt` 中声明依赖（精确版本）

```
python-docx==1.1.2
pandas==2.0.3
```

> 强烈建议使用 `==` 精确锁定版本，避免依赖冲突。

**步骤 2**：在有外网的机器上运行打包

```bash
python build_plugin.py my_plugin
```

**步骤 3**：检查生成的 `deps/` 目录

```bash
ls my_plugin/deps/
# 应该能看到 python_docx, lxml 等包的文件夹
```

**步骤 4**：上传 `dist/my_plugin.zip` 到平台

平台不需要网络、不需要 pip，直接加载即可使用。

### 注意事项

| 场景 | 解决方案 |
|------|---------|
| 依赖是纯 Python 包 | `pip install -t deps` 即可，跨平台通用 |
| 依赖包含 C 扩展（如 numpy） | 打包机器的系统+Python版本必须与部署环境一致，否则二进制不兼容 |
| 部署环境无法安装任何包 | 本方案完全适用，因为所有依赖已打包在 zip 中 |
| 多个插件依赖同一库的不同版本 | 建议统一版本，或让平台管理员预装公共依赖到基础镜像 |

### 大型依赖优化

如果插件依赖体积很大（如 PyTorch、TensorFlow），建议：

1. **预装到平台镜像**：让平台管理员在 Dockerfile 中预装常用大依赖
2. **插件不重复打包**：`requirements.txt` 中不声明这些大依赖，假设平台已预装
3. **运行时兜底**：在 `plugin.py` 中用 try/except 检测，未安装时给出友好提示

```python
# plugin.py
try:
    import torch
except ImportError:
    raise ImportError("本插件需要 torch，请联系管理员预装到平台镜像中")
```

---

## 完整示例：Word 解析插件

```python
from sdk import BasePlugin, tool

class WordParserPlugin(BasePlugin):
    name = "word_parser"
    description = "解析Word文档，提取文本和统计信息"
    version = "1.0.0"

    @tool(
        name="extract_text",
        description="提取Word文档纯文本",
        schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Word文件路径"}
            },
            "required": ["file_path"]
        }
    )
    async def extract_text(self, file_path: str) -> dict:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return {
            "text": text,
            "paragraph_count": len(doc.paragraphs),
        }

    @tool(
        name="count_words",
        description="统计文档字数",
        schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Word文件路径"}
            },
            "required": ["file_path"]
        }
    )
    async def count_words(self, file_path: str) -> dict:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return {
            "total_chars": len(text),
            "total_words": len(text.split()),
        }
```

**requirements.txt**：

```
python-docx==1.1.2
```

**打包**：

```bash
python build_plugin.py my_plugin
# => dist/my_plugin.zip
```

---

## 平台 API

### 上传插件

```http
POST /api/v1/tools/{tool_id}/upload
Content-Type: multipart/form-data

file: <plugin.zip>
```

**响应：**

```json
{
  "success": true,
  "tool": { ... },
  "message": "插件 'word_parser' 安装成功。已包含 deps/ 依赖",
  "tools": [
    {"name": "extract_text", "description": "...", "schema": {...}},
    {"name": "count_words", "description": "...", "schema": {...}}
  ]
}
```

### 重新加载插件（热更新）

```http
POST /api/v1/tools/{tool_id}/reload
```

### 获取插件工具列表

```http
GET /api/v1/tools/{tool_id}/plugin_tools
```

### 下载示例模板

```http
GET /api/v1/tools/download-demo
```

返回一个 zip 文件，包含 `sdk.py`、`plugin.py` 示例、`build_plugin.py` 打包脚本。

---

## 常见问题

### Q: 插件类名必须是 `Plugin` 吗？
不必须。引擎会自动扫描模块中继承 `BasePlugin` 的类。如果有多个，优先选择类名为 `Plugin` 的。

### Q: 可以一个插件暴露多个工具吗？
可以。在一个 `BasePlugin` 子类中，用 `@tool` 装饰多个方法即可。

### Q: 插件方法必须是 async 吗？
不是必须的。同步方法也会正常执行。

### Q: 为什么插件要自带 sdk.py？
为了让插件**完全自包含**。平台升级 SDK 不会影响已上传的插件，插件也不依赖平台的内部包结构。

### Q: 部署环境没有 Python 环境怎么办？
灵枢平台后端本身就是 Python（FastAPI）服务，所以有 Python 运行环境。本方案只要求部署环境能运行 Python import，不需要 pip、不需要网络。

### Q: 打包后 zip 很大怎么办？
- 检查 `deps/` 中是否有不必要的依赖（如测试框架、类型检查工具）
- 大依赖（如 PyTorch）建议预装到平台镜像，不在插件中打包
- 使用 `pip install --no-deps` 手动控制只安装直接依赖

### Q: 插件之间会互相影响吗？
每个插件在独立的目录和模块命名空间中加载，理论上互不影响。但如果两个插件的 `deps/` 中有同名不同版本的包，后加载的会覆盖先加载的。建议统一公共依赖版本。
