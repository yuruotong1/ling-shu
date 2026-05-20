"""
Word 文档解析插件示例

演示如何按照灵枢 Plugin SDK 开发一个自包含插件。
本示例不依赖 python-docx（避免需要安装额外依赖），
用纯 Python 模拟 Word 解析逻辑，实际使用时可取消注释相关代码。

打包前请确保已运行 build_plugin.py 脚本安装依赖。
"""

from sdk import BasePlugin, tool


class WordParserPlugin(BasePlugin):
    """Word 文档解析工具 —— 提取文本、统计字数、提取标题"""

    name = "word_parser"
    description = "解析 Word 文档，提取文本内容、统计信息"
    version = "1.0.0"
    author = "lingzhu"

    @tool(
        name="extract_text",
        description="提取 Word 文档中的纯文本内容",
        schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "文档内容或文件路径（演示模式直接传文本）"
                }
            },
            "required": ["content"]
        }
    )
    async def extract_text(self, content: str) -> dict:
        """模拟提取 Word 纯文本"""
        # 真实场景：
        # from docx import Document
        # doc = Document(file_path)
        # text = "\n".join([p.text for p in doc.paragraphs])
        text = f"【模拟解析结果】\n{content}"
        return {
            "text": text,
            "paragraph_count": len(content.split("\n")),
            "char_count": len(content),
        }

    @tool(
        name="count_words",
        description="统计 Word 文档字数",
        schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "文档内容"
                }
            },
            "required": ["content"]
        }
    )
    async def count_words(self, content: str) -> dict:
        """统计字数信息"""
        words = content.split()
        return {
            "total_chars": len(content),
            "total_words": len(words),
            "chinese_chars": sum(1 for c in content if "\u4e00" <= c <= "\u9fff"),
        }

    @tool(
        name="extract_headings",
        description="提取 Word 文档中的所有标题",
        schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "文档内容（按行分隔，以 # 开头表示标题）"
                }
            },
            "required": ["content"]
        }
    )
    async def extract_headings(self, content: str) -> list:
        """模拟提取标题：将 # 开头的行识别为标题"""
        headings = []
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                title = stripped.lstrip("#").strip()
                headings.append({"level": level, "title": title})
        if not headings:
            lines = [l for l in content.split("\n") if l.strip()]
            if lines:
                headings.append({"level": 1, "title": lines[0].strip()})
        return headings
