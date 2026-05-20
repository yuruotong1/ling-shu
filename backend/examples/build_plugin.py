#!/usr/bin/env python3
"""
灵枢平台插件打包脚本

用法：
    cd my_plugin
    python build_plugin.py

功能：
1. 读取 requirements.txt，安装依赖到 deps/ 目录
2. 验证 plugin.py 语法
3. 打包为 my_plugin.zip（含 sdk.py + plugin.py + deps/ + 其他文件）

要求：
    - 运行此脚本的机器需要有外网（用于 pip install）
    - Python 3.8+
"""

import os
import re
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """运行命令并打印输出"""
    print(f"  > {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def build(plugin_dir: Path | None = None) -> Path:
    """
    打包插件。

    Args:
        plugin_dir: 插件目录，默认为当前目录

    Returns:
        生成的 zip 文件路径
    """
    plugin_dir = plugin_dir or Path.cwd()
    plugin_dir = plugin_dir.resolve()
    name = plugin_dir.name

    print(f"\n{'='*50}")
    print(f"  [打包插件] {name}")
    print(f"  目录: {plugin_dir}")
    print(f"{'='*50}\n")

    # -- 1. 检查必需文件 --
    plugin_py = plugin_dir / "plugin.py"
    sdk_py = plugin_dir / "sdk.py"

    if not plugin_py.exists():
        print("[ERROR] 未找到 plugin.py，请确保插件目录根目录包含入口文件")
        sys.exit(1)

    # 如果没有 sdk.py，自动复制一份
    if not sdk_py.exists():
        candidates = [
            Path(__file__).parent / "word_parser_plugin" / "sdk.py",
            Path(__file__).parent.parent / "app" / "plugin_sdk_standalone.py",
        ]
        copied = False
        for src in candidates:
            if src.exists():
                shutil.copy2(src, sdk_py)
                print(f"[OK] 自动复制 sdk.py 从: {src}")
                copied = True
                break
        if not copied:
            print("[ERROR] 未找到 sdk.py，且无法自动复制。请手动放置 sdk.py")
            sys.exit(1)

    # -- 2. 验证 plugin.py 语法 --
    print("\n[步骤 1/4] 验证 plugin.py 语法...")
    result = run([sys.executable, "-m", "py_compile", str(plugin_py)])
    if result.returncode != 0:
        print(f"[ERROR] 语法错误: {result.stderr}")
        sys.exit(1)
    print("[OK] 语法检查通过")

    # -- 3. 安装依赖 --
    deps_dir = plugin_dir / "deps"
    req_file = plugin_dir / "requirements.txt"

    if req_file.exists() and req_file.read_text().strip():
        print("\n[步骤 2/4] 安装依赖到 deps/ 目录...")
        if deps_dir.exists():
            shutil.rmtree(deps_dir)
        deps_dir.mkdir(exist_ok=True)

        lines = [l.strip() for l in req_file.read_text().splitlines()]
        deps = [l for l in lines if l and not l.startswith("#")]

        if deps:
            result = run([
                sys.executable, "-m", "pip", "install",
                "-r", str(req_file),
                "-t", str(deps_dir),
                "--quiet",
            ])
            if result.returncode != 0:
                print(f"[WARN] pip install 输出: {result.stderr or result.stdout}")
            else:
                print(f"[OK] 已安装 {len(deps)} 个依赖到 deps/")
        else:
            print("[INFO] requirements.txt 为空，跳过依赖安装")
    else:
        print("\n[步骤 2/4] 无 requirements.txt，跳过依赖安装")
        if deps_dir.exists():
            shutil.rmtree(deps_dir)

    # -- 4. 清理不必要的文件 --
    print("\n[步骤 3/4] 清理不必要的文件...")
    removed = 0
    for root, dirs, files in os.walk(plugin_dir):
        if Path(root).name == "dist":
            continue
        for d in list(dirs):
            if d == "__pycache__" or d.endswith(".egg-info"):
                shutil.rmtree(Path(root) / d)
                dirs.remove(d)
                removed += 1
        for f in files:
            if f.endswith((".pyc", ".pyo", ".DS_Store")):
                (Path(root) / f).unlink()
                removed += 1
    print(f"[OK] 清理完成（移除 {removed} 项）")

    # -- 5. 打包 --
    print("\n[步骤 4/4] 打包为 zip...")
    output_dir = plugin_dir.parent / "dist"
    output_dir.mkdir(exist_ok=True)
    zip_path = output_dir / f"{name}.zip"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(plugin_dir):
            rel_root = Path(root).relative_to(plugin_dir)
            if str(rel_root).startswith("dist") or str(rel_root).startswith("build"):
                continue
            for f in files:
                file_path = Path(root) / f
                arcname = str(file_path.relative_to(plugin_dir))
                zf.write(file_path, arcname)

    size_kb = zip_path.stat().st_size / 1024
    print(f"[OK] 打包完成: {zip_path}")
    print(f"[INFO] 文件大小: {size_kb:.1f} KB")

    # -- 6. 验证 --
    print("\n[验证] 检查包内容...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        has_plugin = "plugin.py" in names
        has_sdk = "sdk.py" in names
        print(f"  plugin.py: {'OK' if has_plugin else 'MISSING'}")
        print(f"  sdk.py:    {'OK' if has_sdk else 'MISSING'}")
        if deps_dir.exists():
            dep_files = [n for n in names if n.startswith("deps/")]
            print(f"  deps/:     OK ({len(dep_files)} 个文件)")

    print(f"\n{'='*50}")
    print(f"  [SUCCESS] 插件打包成功！")
    print(f"  输出文件: {zip_path}")
    print(f"  下一步: 在灵枢平台工具管理页面上传此 zip")
    print(f"{'='*50}\n")

    return zip_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="灵枢平台插件打包工具")
    parser.add_argument("dir", nargs="?", default=".", help="插件目录（默认当前目录）")
    args = parser.parse_args()

    build(Path(args.dir))
