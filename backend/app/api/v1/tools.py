"""Tool管理API"""
import io
import json
import uuid
import zipfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.file_storage import save_upload_file
from app.models.tool import Tool
from app.schemas.tool import ToolCreate, ToolUpdate, ToolOut, ToolTestRequest
from app.services.tool_runner import run_tool
from app.plugin_engine import install_plugin, PluginEngine

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolOut])
async def list_tools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool))
    return result.scalars().all()


@router.post("", response_model=ToolOut)
async def create_tool(body: ToolCreate, db: AsyncSession = Depends(get_db)):
    tool = Tool(**body.model_dump())
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get("/download-demo")
async def download_plugin_demo():
    """
    下载示例插件模板（包含 sdk.py + plugin.py + requirements.txt + build_plugin.py）。
    用户下载后按说明开发即可。
    """
    example_dir = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "word_parser_plugin"
    build_script = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "build_plugin.py"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        sdk_path = example_dir / "sdk.py"
        if sdk_path.exists():
            zf.write(sdk_path, "my_plugin/sdk.py")

        plugin_path = example_dir / "plugin.py"
        if plugin_path.exists():
            zf.write(plugin_path, "my_plugin/plugin.py")

        req_path = example_dir / "requirements.txt"
        if req_path.exists():
            zf.write(req_path, "my_plugin/requirements.txt")

        if build_script.exists():
            zf.write(build_script, "build_plugin.py")

        readme_content = """灵枢平台插件开发模板

目录结构：
  my_plugin/
    sdk.py           -- SDK 基类（不要修改）
    plugin.py        -- 你的插件代码（按示例修改）
    requirements.txt -- 第三方依赖声明

开发步骤：
  1. 修改 my_plugin/plugin.py，编写你的业务逻辑
  2. 在 my_plugin/requirements.txt 中声明依赖
  3. 运行打包命令：
       python build_plugin.py my_plugin
  4. 在 dist/ 目录下找到 .zip 文件，上传到灵枢平台

注意：
  - 打包机器需要有外网（用于 pip install 下载依赖）
  - 打包后的 zip 是自包含的，部署环境无需网络即可运行
  - 如果依赖包含 C 扩展，打包机器需与部署环境系统一致
"""
        zf.writestr("README.txt", readme_content)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lingzhu-plugin-demo.zip"},
    )


@router.get("/{tool_id}", response_model=ToolOut)
async def get_tool(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    return tool


@router.put("/{tool_id}", response_model=ToolOut)
async def update_tool(tool_id: uuid.UUID, body: ToolUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(tool, field, val)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.delete("/{tool_id}")
async def delete_tool(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    await db.delete(tool)
    await db.commit()
    return {"ok": True}


@router.post("/{tool_id}/test")
async def test_tool(
    tool_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    测试工具连通性。
    支持 multipart/form-data，可同时提交 JSON 参数和上传文件。
    文件会自动保存到 uploads/{tool_id}/ 目录，文件路径注入到对应参数中。
    """
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")

    # 解析 multipart 表单
    try:
        form_data = await request.form()
    except Exception as e:
        raise HTTPException(400, f"表单解析失败: {e}")

    params_raw = form_data.get("params", "{}")
    try:
        params_dict = json.loads(params_raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "params 不是有效的 JSON 字符串")

    # 处理上传的文件：form 字段名 = 参数名
    try:
        for field_name, value in form_data.multi_items():
            if field_name == "params":
                continue
            if hasattr(value, 'filename') and value.filename:
                file_path = save_upload_file(str(tool_id), value, field_name)
                params_dict[field_name] = file_path
    except Exception as e:
        raise HTTPException(400, f"文件保存失败: {e}")

    try:
        # plugin 类型工具需要指定 function_name
        fn_name = params_dict.pop("__function_name__", None)
        output = await run_tool(tool, fn_name or tool.name, params_dict, db)
        tool.call_count += 1
        await db.commit()
        return {"success": True, "output": output, "file_paths": {k: v for k, v in params_dict.items() if isinstance(v, str) and 'uploads' in v}}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 插件上传 / 管理 ──

@router.post("/{tool_id}/upload")
async def upload_plugin(
    tool_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    上传插件 zip 包并自动安装。
    如果 tool_id 对应的 Tool 不存在，会自动创建一个 plugin 类型的 Tool。
    """
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()

    if tool is None:
        # 自动创建
        tool = Tool(
            id=tool_id,
            name=f"plugin_{str(tool_id)[:8]}",
            description="待安装插件",
            tool_type="plugin",
            api_url="",
        )
        db.add(tool)
        await db.commit()
        await db.refresh(tool)

    if file.content_type not in ("application/zip", "application/x-zip-compressed", "multipart/form-data"):
        # 某些客户端上传 zip 时 content_type 可能不准确，不做强校验
        pass

    zip_bytes = await file.read()
    if not zip_bytes.startswith(b"PK"):
        raise HTTPException(400, "上传文件不是有效的 zip 格式")

    tool.tool_type = "plugin"
    install_result = await install_plugin(tool, zip_bytes)

    if install_result["success"]:
        await db.commit()
        await db.refresh(tool)
        return {
            "success": True,
            "tool": ToolOut.model_validate(tool),
            "message": install_result["message"],
            "tools": install_result["tools"],
        }
    else:
        # 安装失败也保存路径信息，方便调试
        await db.commit()
        raise HTTPException(400, detail=install_result["message"])


@router.post("/{tool_id}/reload")
async def reload_plugin(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """重新加载插件（热更新）"""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    if tool.tool_type != "plugin":
        raise HTTPException(400, "该工具不是 plugin 类型")

    PluginEngine.clear_cache(tool.id)
    try:
        instance = PluginEngine.load_plugin(tool)
        tools_def = instance.get_tools()
        tool.plugin_functions = tools_def
        tool.name = instance.name or tool.name
        tool.description = instance.description or tool.description
        await db.commit()
        await db.refresh(tool)
        return {
            "success": True,
            "tool": ToolOut.model_validate(tool),
            "tools": tools_def,
        }
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{tool_id}/plugin_tools")
async def get_plugin_tools(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取 plugin 类型工具暴露的所有函数定义"""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    if tool.tool_type != "plugin":
        raise HTTPException(400, "该工具不是 plugin 类型")

    try:
        tools_def = PluginEngine.get_plugin_tools(tool)
        return {"tools": tools_def}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{tool_id}/download")
async def download_plugin(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """下载当前插件的原始 zip 包，方便用户修改后重新上传"""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    if tool.tool_type != "plugin":
        raise HTTPException(400, "该工具不是 plugin 类型")

    zip_path = Path(tool.plugin_path or "") / "plugin.zip"
    if not zip_path.exists():
        raise HTTPException(404, "未找到插件原始包，可能该插件是旧版本上传的")

    return StreamingResponse(
        open(zip_path, "rb"),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename={tool.name or "plugin"}.zip'},
    )

