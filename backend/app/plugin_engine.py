"""
灵枢平台 Plugin 动态加载引擎

职责：
1. 解压插件 zip 包到 plugins/{tool_id}/ 目录
2. 通过 importlib 动态加载插件模块
3. 实例化 BasePlugin 子类
4. 执行插件方法

设计约束：
- 不依赖 pip / 网络，插件需自包含所有依赖
- 每个插件在独立目录中，避免命名冲突
- 插件自带 sdk.py，不依赖平台的 app.plugin_sdk 包
"""

import asyncio
import importlib
import importlib.util
import inspect
import json
import logging
import os
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any

from app.models.tool import Tool

logger = logging.getLogger(__name__)

# 插件存储根目录（相对工作目录）
PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugins"
# 入口文件名（zip 根目录下的主文件）
DEFAULT_ENTRY_FILE = "plugin.py"


def ensure_plugin_dir() -> Path:
    """确保插件根目录存在"""
    PLUGIN_ROOT.mkdir(parents=True, exist_ok=True)
    return PLUGIN_ROOT


def get_plugin_dir(tool_id: str | uuid.UUID) -> Path:
    """获取指定 tool_id 的插件目录"""
    return ensure_plugin_dir() / str(tool_id)


def extract_plugin_zip(tool_id: str | uuid.UUID, zip_bytes: bytes) -> Path:
    """
    将 zip 字节流解压到 plugins/{tool_id}/ 目录。

    Returns:
        解压后的目录 Path
    """
    plugin_dir = get_plugin_dir(tool_id)
    # 清理旧文件
    if plugin_dir.exists():
        import shutil
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True, exist_ok=True)

    zip_path = plugin_dir / "__upload__.zip"
    zip_path.write_bytes(zip_bytes)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(plugin_dir)

    zip_path.unlink()  # 删除 zip 本身，只保留解压内容
    logger.info(f"Plugin extracted to {plugin_dir}")
    return plugin_dir


class PluginEngine:
    """插件加载与执行引擎"""

    # 缓存：tool_id -> (module, instance)
    _cache: dict[str, tuple[Any, Any]] = {}

    @classmethod
    def clear_cache(cls, tool_id: str | uuid.UUID | None = None) -> None:
        """清除插件缓存，用于热更新"""
        tid = str(tool_id)
        if tool_id is None:
            cls._cache.clear()
        elif tid in cls._cache:
            del cls._cache[tid]

    @classmethod
    def _setup_plugin_path(cls, plugin_dir: Path) -> None:
        """
        配置插件的运行时路径：
        1. 将插件目录加入 sys.path
        2. 如果存在 deps/ 目录，也加入 sys.path（优先级更高）
        """
        # deps/ 目录优先，这样用户打包的依赖会覆盖系统已有版本
        deps_dir = plugin_dir / "deps"
        if deps_dir.exists() and str(deps_dir) not in sys.path:
            sys.path.insert(0, str(deps_dir))
            logger.debug(f"Added deps to sys.path: {deps_dir}")

        if str(plugin_dir) not in sys.path:
            sys.path.insert(0, str(plugin_dir))
            logger.debug(f"Added plugin dir to sys.path: {plugin_dir}")

    @classmethod
    def _load_module_from_path(cls, module_name: str, file_path: Path) -> Any:
        """从文件路径加载 Python 模块"""
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载模块: {file_path}")
        module = importlib.util.module_from_spec(spec)
        cls._setup_plugin_path(file_path.parent)
        spec.loader.exec_module(module)
        return module

    @classmethod
    def _find_plugin_class(cls, module: Any) -> type:
        """在模块中查找继承自 BasePlugin 的类"""
        # 先尝试从模块导入 BasePlugin（插件自带 sdk.py）
        base_class = None
        if hasattr(module, "BasePlugin"):
            base_class = module.BasePlugin
        else:
            # 兜底：从平台 SDK 导入
            from app.plugin_sdk.base import BasePlugin as PlatformBasePlugin
            base_class = PlatformBasePlugin

        candidates = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, base_class) and obj is not base_class:
                candidates.append(obj)
        if not candidates:
            raise ValueError(
                f"模块 {getattr(module, '__file__', '?')} 中未找到继承自 BasePlugin 的类"
            )
        # 如果有多个，优先选择名为 Plugin 的，否则取第一个
        for c in candidates:
            if c.__name__.lower() == "plugin":
                return c
        return candidates[0]

    @classmethod
    def load_plugin(cls, tool: Tool) -> Any:
        """
        加载并实例化插件。

        优先使用缓存，若 plugin_path / plugin_entry 变更则重新加载。
        """
        tid = str(tool.id)

        # 检查缓存
        if tid in cls._cache:
            cached_path = getattr(cls._cache[tid][0], "__plugin_path__", None)
            current_path = tool.plugin_path
            if cached_path == current_path:
                return cls._cache[tid][1]

        plugin_path = tool.plugin_path or ""
        entry_file = tool.plugin_entry or DEFAULT_ENTRY_FILE

        if not plugin_path:
            raise ValueError(f"Tool {tid} 未配置 plugin_path")

        plugin_dir = Path(plugin_path)
        if not plugin_dir.exists():
            raise FileNotFoundError(f"插件目录不存在: {plugin_dir}")

        entry_path = plugin_dir / entry_file
        if not entry_path.exists():
            # 尝试在子目录中查找（兼容 zip 根目录含有一层文件夹的情况）
            for sub in plugin_dir.iterdir():
                if sub.is_dir():
                    candidate = sub / entry_file
                    if candidate.exists():
                        entry_path = candidate
                        plugin_dir = sub
                        break
            if not entry_path.exists():
                raise FileNotFoundError(f"插件入口文件不存在: {entry_path}")

        module_name = f"__lingzhu_plugin__{tid.replace('-', '_')}__"
        module = cls._load_module_from_path(module_name, entry_path)
        module.__plugin_path__ = str(plugin_dir)  # type: ignore[attr-defined]

        plugin_cls = cls._find_plugin_class(module)
        instance = plugin_cls()
        cls._cache[tid] = (module, instance)
        logger.info(f"Plugin loaded: {instance.name} v{instance.version} for tool {tid}")
        return instance

    @classmethod
    def get_plugin_tools(cls, tool: Tool) -> list[dict]:
        """获取插件暴露的所有工具定义"""
        instance = cls.load_plugin(tool)
        return instance.get_tools()

    @classmethod
    async def execute(cls, tool: Tool, function_name: str, params: dict) -> Any:
        """执行插件的指定工具方法"""
        instance = cls.load_plugin(tool)
        result = await instance.execute(function_name, params)
        return result


async def install_plugin(tool: Tool, zip_bytes: bytes) -> dict[str, Any]:
    """
    插件安装流程：解压 → 加载验证 → 更新 tool 记录

    注意：本方法不执行 pip install，插件必须是自包含的
    （依赖已通过 build_plugin.py 打包到 deps/ 目录中）。

    Returns:
        {"success": bool, "message": str, "tools": list[dict]}
    """
    try:
        # 1. 解压
        plugin_dir = extract_plugin_zip(tool.id, zip_bytes)

        # 2. 检查是否有 deps/ 目录
        deps_dir = plugin_dir / "deps"
        has_deps = deps_dir.exists() and any(deps_dir.iterdir())

        # 3. 检查是否有 sdk.py（自包含校验）
        has_sdk = (plugin_dir / "sdk.py").exists()

        # 4. 加载验证
        tool.plugin_path = str(plugin_dir)
        tool.plugin_entry = tool.plugin_entry or DEFAULT_ENTRY_FILE
        PluginEngine.clear_cache(tool.id)
        instance = PluginEngine.load_plugin(tool)
        tools_def = instance.get_tools()

        # 5. 缓存工具定义到 tool.plugin_functions
        tool.plugin_functions = tools_def
        tool.name = instance.name or tool.name
        tool.description = instance.description or tool.description

        msg_parts = [f"插件 '{instance.name}' 安装成功"]
        if has_deps:
            msg_parts.append("已包含 deps/ 依赖")
        if not has_sdk:
            msg_parts.append("⚠️ 未找到 sdk.py（建议将 SDK 打包进插件）")

        return {
            "success": True,
            "message": "。".join(msg_parts),
            "tools": tools_def,
        }
    except Exception as e:
        logger.exception("Plugin install failed")
        return {"success": False, "message": str(e), "tools": []}
