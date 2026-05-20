"""@tool 装饰器"""
from typing import Callable


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
