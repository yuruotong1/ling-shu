"""
灵枢平台 Plugin SDK

开发者按照以下方式编写插件：

    from app.plugin_sdk import BasePlugin, tool

    class MyPlugin(BasePlugin):
        name = "word_parser"
        description = "Word文档解析工具"
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
        async def extract_text(self, file_path: str) -> str:
            # 业务逻辑
            return "文本内容"

打包要求：
    将插件代码打包为 zip，根目录下必须包含一个入口 Python 文件（默认 plugin.py），
    且其中定义了继承自 BasePlugin 的类。
    可选包含 requirements.txt 声明第三方依赖。
"""

from .base import BasePlugin
from .decorators import tool

__all__ = ["BasePlugin", "tool"]
