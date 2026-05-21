"""
文件上传存储工具

提供临时文件上传、保存、路径注入功能。
文件保存在 uploads/ 目录下，按 tool_id 分目录。
"""

import os
import shutil
import uuid
from pathlib import Path
from fastapi import UploadFile

# 上传文件根目录
UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "uploads"


def ensure_upload_dir() -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


def get_tool_upload_dir(tool_id: str) -> Path:
    d = ensure_upload_dir() / str(tool_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload_file(tool_id: str, file: UploadFile, param_name: str | None = None) -> str:
    """
    保存上传的文件到 uploads/{tool_id}/ 目录。

    Args:
        tool_id: 工具 ID
        file: UploadFile 对象
        param_name: 参数名，用于生成文件名前缀

    Returns:
        文件的绝对路径
    """
    tool_dir = get_tool_upload_dir(tool_id)
    suffix = Path(file.filename or "file").suffix
    prefix = param_name or "file"
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}{suffix}"
    file_path = tool_dir / filename

    # UploadFile 的 file 指针可能在末尾，需要 seek 到开头
    if hasattr(file.file, 'seek'):
        file.file.seek(0)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return str(file_path)


def cleanup_tool_uploads(tool_id: str) -> None:
    """清理指定 tool_id 的所有上传文件"""
    tool_dir = get_tool_upload_dir(tool_id)
    if tool_dir.exists():
        shutil.rmtree(tool_dir)


def inject_file_paths(params: dict, files: list[tuple[str, UploadFile]], tool_id: str) -> dict:
    """
    将上传的文件保存，并把文件路径注入到 params 中。

    Args:
        params: 原始参数字典
        files: [(参数名, UploadFile), ...]
        tool_id: 工具 ID

    Returns:
        注入文件路径后的新 params 字典
    """
    result = dict(params)
    for param_name, file in files:
        file_path = save_upload_file(tool_id, file, param_name)
        # 如果参数名已存在且为空字符串/None，替换为文件路径
        # 否则使用参数名注入
        result[param_name] = file_path
    return result
