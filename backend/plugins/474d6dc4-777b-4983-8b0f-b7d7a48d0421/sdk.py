"""
灵枢平台 Plugin SDK（独立版）

此文件可独立于平台运行，插件只需将此文件放在根目录即可使用。
不需要依赖平台的 app.plugin_sdk 包。

用法：
    from sdk import BasePlugin, tool

    class MyPlugin(BasePlugin):
        name = "my_tool"
        description = "我的工具"

        @tool(name="do_something", description="...", schema={...})
        async def do_something(self, arg: str) -> str:
            return "ok"
"""

from abc import ABC
from typing import Any, Callable


def tool(name: str | None = None, description: str | None = None, schema: dict | None = None):
    """
    标记一个方法为插件暴露的工具。

    Args:
        name:        工具名称。默认使用函数名。
        description: 工具描述。默认使用函数 docstring。
        schema:      输入参数 JSON Schema。默认生成空对象 schema。
    """
    def decorator(func: Callable) -> Callable:
        func._is_tool = True  # type: ignore[attr-defined]
        func._tool_name = name or func.__name__  # type: ignore[attr-defined]
        func._tool_description = description or (func.__doc__ or "")  # type: ignore[attr-defined]
        func._tool_schema = schema or {"type": "object", "properties": {}}  # type: ignore[attr-defined]
        return func
    return decorator


class BasePlugin(ABC):
    """
    插件基类。所有灵枢平台插件必须继承此类。

    子类必须覆盖以下类属性：
        name: str          — 插件唯一标识名（英文，不含空格）
        description: str   — 插件功能描述

    可选覆盖：
        version: str       — 版本号，默认 "1.0.0"
        author: str        — 作者信息
    """

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""

    def __init__(self):
        self._tools: list[dict] = []
        self._discover_tools()

    def _discover_tools(self) -> None:
        """自动扫描实例方法上被 @tool 装饰的函数"""
        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue
            method = getattr(self, attr_name)
            if callable(method) and getattr(method, "_is_tool", False):
                self._tools.append(
                    {
                        "name": getattr(method, "_tool_name", attr_name),
                        "description": getattr(method, "_tool_description", ""),
                        "schema": getattr(method, "_tool_schema", {"type": "object", "properties": {}}),
                        "_method": method,
                    }
                )

    def get_tools(self) -> list[dict]:
        """返回该插件暴露的所有工具定义（不含内部 _method）"""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "schema": t["schema"],
            }
            for t in self._tools
        ]

    def get_tool_names(self) -> list[str]:
        """返回所有工具名"""
        return [t["name"] for t in self._tools]

    async def execute(self, tool_name: str, params: dict) -> Any:
        """
        根据工具名执行对应方法。

        Args:
            tool_name: 工具名（即 @tool 中声明的 name，或经平台 sanitize 后的名）
            params:    调用参数（dict）

        Returns:
            工具方法返回值（会被序列化为 JSON）
        """
        import re
        import asyncio

        def _sanitize(name: str) -> str:
            s = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
            if s and s[0].isdigit():
                s = "_" + s
            return s[:64] or "_tool"

        for t in self._tools:
            if t["name"] == tool_name or _sanitize(t["name"]) == tool_name:
                method = t["_method"]
                if asyncio.iscoroutinefunction(method):
                    return await method(**params)
                else:
                    return method(**params)
        raise ValueError(f"工具 '{tool_name}' 不存在于插件 '{self.name}' 中")
