"""
Word 自动操作插件

功能：
  1. 解压 docx 文件（docx 本质是 zip）
  2. 读取/修改内部 XML 文件（如 word/document.xml）
  3. 对 document.xml 进行文本替换（保持格式）
  4. 重新压缩为 docx，不损坏文件结构

纯 Python 标准库实现，无需额外依赖。
"""

import base64
import io
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from xml.etree import ElementTree as ET

from sdk import BasePlugin, tool


# Word 常用命名空间
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "ve": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "o": "urn:schemas-microsoft-com:office:office",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "w10": "urn:schemas-microsoft-com:office:word",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# 预先注册命名空间，确保输出时前缀保持一致
for prefix, uri in NAMESPACES.items():
    try:
        ET.register_namespace(prefix, uri)
    except ValueError:
        pass


def _collect_ns_from_tree(root: ET.Element) -> dict:
    """从已解析的树中收集所有用到的命名空间前缀，避免写回时产生 ns0 等随机前缀。"""
    collected = {}
    for elem in root.iter():
        if elem.tag.startswith("{"):
            uri = elem.tag.split("}")[0][1:]
            for p, u in NAMESPACES.items():
                if u == uri and p not in collected:
                    collected[p] = u
        for key in elem.attrib:
            if key.startswith("{"):
                uri = key.split("}")[0][1:]
                for p, u in NAMESPACES.items():
                    if u == uri and p not in collected:
                        collected[p] = u
    return collected


def _ensure_ns_registered(root: ET.Element):
    """确保根元素用到的命名空间都被注册。"""
    for p, u in _collect_ns_from_tree(root).items():
        try:
            ET.register_namespace(p, u)
        except ValueError:
            pass


class WordAutoPlugin(BasePlugin):
    """Word 自动操作插件 —— 解压、修改 XML、重新打包"""

    name = "word_auto"
    description = "Word 文档自动操作：解压、读取/修改 XML、文本替换、重新打包为 docx"
    version = "1.1.0"
    author = "lingzhu"

    def __init__(self):
        super().__init__()
        # 用字典保存解压后的临时目录，key 为 extract_id
        self._extracts: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # 内部辅助方法
    # ------------------------------------------------------------------ #

    def _cleanup_old(self, keep: int = 20):
        """当缓存目录过多时，清理最早的几个。"""
        if len(self._extracts) <= keep:
            return
        # 按目录创建时间排序（简单的 mtime 近似）
        items = []
        for eid, path in list(self._extracts.items()):
            try:
                items.append((os.stat(path).st_ctime, eid, path))
            except OSError:
                pass
        items.sort()
        for _, eid, path in items[: len(items) - keep]:
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass
            self._extracts.pop(eid, None)

    def _get_extract_path(self, extract_id: str) -> str:
        if extract_id not in self._extracts:
            raise ValueError(f"extract_id '{extract_id}' 不存在，请先调用 unpack_docx")
        path = self._extracts[extract_id]
        if not os.path.isdir(path):
            raise ValueError(f"extract_id '{extract_id}' 对应的目录已被清理")
        return path

    def _read_xml_tree(self, extract_id: str, rel_path: str) -> ET.Element:
        """读取 XML 并解析为 ElementTree。"""
        base = self._get_extract_path(extract_id)
        filepath = os.path.join(base, rel_path)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"文件不存在: {rel_path}")
        tree = ET.parse(filepath)
        return tree.getroot()

    def _write_xml_tree(self, extract_id: str, rel_path: str, root: ET.Element):
        """将 ElementTree 写回文件，保留声明和格式。"""
        base = self._get_extract_path(extract_id)
        filepath = os.path.join(base, rel_path)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        _ensure_ns_registered(root)

        # 序列化
        data = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
        with open(filepath, "wb") as f:
            f.write(data)

    def _find_all_wt(self, root: ET.Element) -> list[ET.Element]:
        """找到所有 w:t 元素（ Word 文本运行的实际文本节点）。"""
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return root.findall(".//w:t", ns)

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #

    @tool(
        name="unpack_docx",
        description="将 base64 编码的 docx 文件解压到临时目录，返回 extract_id 和内部文件列表",
        schema={
            "type": "object",
            "properties": {
                "file_data": {
                    "type": "string",
                    "description": "docx 文件的 base64 编码字符串"
                }
            },
            "required": ["file_data"]
        }
    )
    def unpack_docx(self, file_data: str) -> dict:
        """解压 docx 文件，返回提取 ID 和文件结构。"""
        raw = base64.b64decode(file_data)
        extract_id = str(uuid.uuid4())[:8]
        tmpdir = tempfile.mkdtemp(prefix=f"docx_{extract_id}_")

        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            zf.extractall(tmpdir)

        self._extracts[extract_id] = tmpdir
        self._cleanup_old()

        # 收集文件列表
        files = []
        for root_dir, _dirs, filenames in os.walk(tmpdir):
            for f in filenames:
                full = os.path.join(root_dir, f)
                rel = os.path.relpath(full, tmpdir).replace("\\", "/")
                files.append(rel)

        files.sort()
        return {
            "extract_id": extract_id,
            "total_files": len(files),
            "files": files,
            "note": "请保存 extract_id，后续操作都需要用到它",
        }

    @tool(
        name="pack_docx",
        description="将解压后的目录重新打包为 docx，返回 base64 编码的文件数据",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {
                    "type": "string",
                    "description": "unpack_docx 返回的提取 ID"
                }
            },
            "required": ["extract_id"]
        }
    )
    def pack_docx(self, extract_id: str) -> dict:
        """重新打包为 docx。"""
        base = self._get_extract_path(extract_id)
        buf = io.BytesIO()

        # 收集文件列表，按原始 docx 常见顺序排序（[Content_Types].xml 放前面更佳）
        all_files = []
        for root_dir, _dirs, filenames in os.walk(base):
            for f in filenames:
                full = os.path.join(root_dir, f)
                rel = os.path.relpath(full, base).replace("\\", "/")
                all_files.append(rel)

        # 让 [Content_Types].xml 在最前面，避免某些严格阅读器报错
        all_files.sort(key=lambda x: (not x.startswith("[Content_Types]"), x))

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in all_files:
                full = os.path.join(base, rel)
                # 保留原始压缩信息尽量一致
                zf.write(full, rel)

        data = buf.getvalue()
        b64 = base64.b64encode(data).decode("ascii")

        # 可选：清理临时目录
        # shutil.rmtree(base, ignore_errors=True)
        # self._extracts.pop(extract_id, None)

        return {
            "file_data_base64": b64,
            "size_bytes": len(data),
            "note": "可用此 base64 数据重新生成 docx 文件",
        }

    @tool(
        name="read_xml",
        description="读取 docx 内部某个 XML 文件的文本内容",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {"type": "string", "description": "提取 ID"},
                "file_path": {
                    "type": "string",
                    "description": "XML 文件相对路径，例如 word/document.xml"
                }
            },
            "required": ["extract_id", "file_path"]
        }
    )
    def read_xml(self, extract_id: str, file_path: str) -> dict:
        """读取指定 XML 的格式化字符串。"""
        base = self._get_extract_path(extract_id)
        filepath = os.path.join(base, file_path)
        if not os.path.isfile(filepath):
            return {"error": f"文件不存在: {file_path}"}

        with open(filepath, "rb") as f:
            raw = f.read()

        # 尝试格式化输出（简单的 ElementTree 美化）
        try:
            root = ET.fromstring(raw)
            _ensure_ns_registered(root)
            pretty = ET.tostring(root, encoding="unicode")
        except ET.ParseError:
            pretty = raw.decode("utf-8", errors="replace")

        return {
            "file_path": file_path,
            "size_bytes": len(raw),
            "content": pretty,
        }

    @tool(
        name="write_xml",
        description="将 XML 字符串写回 docx 内部的指定文件",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {"type": "string", "description": "提取 ID"},
                "file_path": {
                    "type": "string",
                    "description": "目标文件相对路径，例如 word/document.xml"
                },
                "content": {
                    "type": "string",
                    "description": "完整的 XML 字符串内容"
                }
            },
            "required": ["extract_id", "file_path", "content"]
        }
    )
    def write_xml(self, extract_id: str, file_path: str, content: str) -> dict:
        """直接写回 XML 字符串。"""
        base = self._get_extract_path(extract_id)
        filepath = os.path.join(base, file_path)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # 简单校验是否为合法 XML
        try:
            ET.fromstring(content.encode("utf-8"))
        except ET.ParseError as exc:
            return {"success": False, "error": f"XML 格式错误: {exc}"}

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return {"success": True, "file_path": file_path, "note": "XML 已写回"}

    @tool(
        name="get_document_text",
        description="提取 word/document.xml 中的所有可见纯文本",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {"type": "string", "description": "提取 ID"}
            },
            "required": ["extract_id"]
        }
    )
    def get_document_text(self, extract_id: str) -> dict:
        """提取 document.xml 中所有 w:t 的文本，按段落分组。"""
        root = self._read_xml_tree(extract_id, "word/document.xml")
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        paragraphs = []
        for para in root.findall(".//w:p", ns):
            texts = []
            for t in para.findall(".//w:t", ns):
                if t.text:
                    texts.append(t.text)
            para_text = "".join(texts)
            paragraphs.append(para_text)

        full_text = "\n".join(paragraphs)
        return {
            "paragraph_count": len(paragraphs),
            "total_chars": len(full_text),
            "text": full_text,
        }

    @tool(
        name="replace_text",
        description="在 word/document.xml 中批量替换文本（保持原有格式）",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {"type": "string", "description": "提取 ID"},
                "replacements": {
                    "type": "object",
                    "description": "替换字典，key 为旧文本，value 为新文本"
                }
            },
            "required": ["extract_id", "replacements"]
        }
    )
    def replace_text(self, extract_id: str, replacements: dict) -> dict:
        """
        在 document.xml 的所有 w:t 节点内做文本替换。
        注意：Word 可能把一个词拆到多个 w:t 中，此方法在每个独立的 w:t 内部替换。
        """
        root = self._read_xml_tree(extract_id, "word/document.xml")
        wt_list = self._find_all_wt(root)

        total_replaces = 0
        for wt in wt_list:
            if not wt.text:
                continue
            original = wt.text
            new_text = original
            for old, new in replacements.items():
                if old in new_text:
                    new_text = new_text.replace(old, new)
            if new_text != original:
                wt.text = new_text
                total_replaces += 1

        self._write_xml_tree(extract_id, "word/document.xml", root)

        return {
            "success": True,
            "modified_runs": total_replaces,
            "replacements_requested": len(replacements),
        }

    @tool(
        name="smart_replace",
        description="智能替换：先合并同一 run 内被拆分的 w:t，再进行跨 run 替换（更准确）",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {"type": "string", "description": "提取 ID"},
                "old_text": {
                    "type": "string",
                    "description": "要查找的旧文本"
                },
                "new_text": {
                    "type": "string",
                    "description": "替换后的新文本"
                }
            },
            "required": ["extract_id", "old_text", "new_text"]
        }
    )
    def smart_replace(self, extract_id: str, old_text: str, new_text: str) -> dict:
        """
        智能替换策略：
        1. 在每个 <w:r> 内部合并所有 <w:t> 的文本
        2. 在合并后的文本上执行替换
        3. 如果旧文本跨越多个 <w:r>，则先尝试拼接段落全文匹配
        """
        root = self._read_xml_tree(extract_id, "word/document.xml")
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

        replaced_count = 0

        # 策略 A：在每个 w:r 内部合并 w:t 后再替换
        for wr in root.findall(".//w:r", ns):
            t_elems = wr.findall("w:t", ns)
            if not t_elems:
                continue
            combined = "".join(t.text or "" for t in t_elems)
            if old_text not in combined:
                continue

            new_combined = combined.replace(old_text, new_text)

            # 保留第一个 w:t，删除其余 w:t，将新文本写入第一个
            first_t = t_elems[0]
            first_t.text = new_combined
            # 如果有 xml:space 属性，保留它
            if "{http://www.w3.org/XML/1998/namespace}space" in first_t.attrib:
                first_t.attrib["{http://www.w3.org/XML/1998/namespace}space"] = "preserve"
            elif new_combined.endswith(" ") or new_combined.startswith(" "):
                first_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

            for extra in t_elems[1:]:
                wr.remove(extra)
            replaced_count += 1

        # 策略 B：对整个段落进行跨 run 拼接匹配（处理跨 run 的情况）
        for para in root.findall(".//w:p", ns):
            wr_list = para.findall("w:r", ns)
            if not wr_list:
                continue

            # 提取每个 run 的文本快照
            run_infos = []
            for wr in wr_list:
                t_elems = wr.findall("w:t", ns)
                text = "".join(t.text or "" for t in t_elems)
                run_infos.append({"wr": wr, "text": text, "t_elems": t_elems})

            full = "".join(r["text"] for r in run_infos)
            if old_text not in full:
                continue

            # 如果策略 A 已经处理过这个段落（即所有 old_text 都在 run 内部），则跳过
            # 否则需要跨 run 处理
            # 简单实现：如果某个 run 包含部分匹配，则尝试更激进的合并
            # 这里采用一种保守方式：如果跨 run 连续多个 run 的拼接能匹配 old_text，
            # 则将这些 run 合并为一个 run

            idx = full.find(old_text)
            if idx == -1:
                continue

            # 找到覆盖这段文本的 run 范围
            start_run = None
            end_run = None
            pos = 0
            for i, info in enumerate(run_infos):
                run_len = len(info["text"])
                if start_run is None and pos <= idx < pos + run_len:
                    start_run = i
                if start_run is not None and pos <= idx + len(old_text) <= pos + run_len:
                    end_run = i
                    break
                pos += run_len

            if start_run is None or end_run is None:
                # 跨多个 run 的情况，合并这些 run
                # 重新计算
                pos = 0
                start_run = None
                end_run = None
                for i, info in enumerate(run_infos):
                    run_len = len(info["text"])
                    if start_run is None and pos <= idx < pos + run_len:
                        start_run = i
                    if start_run is not None:
                        end_run = i
                        if pos + run_len >= idx + len(old_text):
                            break
                    pos += run_len

            if start_run is not None and end_run is not None and start_run != end_run:
                # 合并 start_run 到 end_run 的所有 run
                first_wr = run_infos[start_run]["wr"]
                # 收集合并前的完整文本
                merged_text = "".join(run_infos[i]["text"] for i in range(start_run, end_run + 1))
                new_merged = merged_text.replace(old_text, new_text, 1)

                # 保留第一个 run，删除中间的 runs
                first_t_list = first_wr.findall("w:t", ns)
                if first_t_list:
                    first_t = first_t_list[0]
                    first_t.text = new_merged
                    # 设置 preserve 空格
                    first_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                    for extra in first_t_list[1:]:
                        first_wr.remove(extra)
                else:
                    # 没有 w:t，创建一个
                    t = ET.SubElement(first_wr, f"{W}t")
                    t.text = new_merged
                    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

                # 删除其他 run
                parent = para
                for i in range(start_run + 1, end_run + 1):
                    wr_to_remove = run_infos[i]["wr"]
                    if wr_to_remove in parent:
                        parent.remove(wr_to_remove)

                replaced_count += 1

        self._write_xml_tree(extract_id, "word/document.xml", root)

        return {
            "success": True,
            "replaced_occurrences": replaced_count,
            "note": "若文本被拆到多个 run，已尝试合并后替换",
        }

    @tool(
        name="list_files",
        description="列出当前 extract_id 下的所有内部文件",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {"type": "string", "description": "提取 ID"}
            },
            "required": ["extract_id"]
        }
    )
    def list_files(self, extract_id: str) -> dict:
        """列出所有文件。"""
        base = self._get_extract_path(extract_id)
        files = []
        for root_dir, _dirs, filenames in os.walk(base):
            for f in filenames:
                full = os.path.join(root_dir, f)
                rel = os.path.relpath(full, base).replace("\\", "/")
                files.append(rel)
        files.sort()
        return {"extract_id": extract_id, "total": len(files), "files": files}

    @tool(
        name="cleanup",
        description="清理指定 extract_id 的临时目录，释放磁盘空间",
        schema={
            "type": "object",
            "properties": {
                "extract_id": {"type": "string", "description": "提取 ID"}
            },
            "required": ["extract_id"]
        }
    )
    def cleanup(self, extract_id: str) -> dict:
        """删除临时目录。"""
        if extract_id not in self._extracts:
            return {"success": False, "error": "extract_id 不存在"}
        path = self._extracts.pop(extract_id)
        shutil.rmtree(path, ignore_errors=True)
        return {"success": True, "message": f"已清理 {extract_id}"}
