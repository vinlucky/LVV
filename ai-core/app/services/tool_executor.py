import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_CODE_OUTPUT = 5000
CODE_TIMEOUT = 15


def execute_tool(name: str, arguments: dict, mode: str = "chat", conv_id: str | None = None) -> str:
    logger.info(f"[tool_executor] Executing tool: {name} with args: {json.dumps(arguments, ensure_ascii=False)[:200]}")

    if name == "search_knowledge_base":
        return _search_knowledge_base(arguments, mode, conv_id)
    elif name == "read_file":
        return _read_file(arguments, mode, conv_id)
    elif name == "list_files":
        return _list_files(arguments, conv_id)
    elif name == "execute_code":
        return _execute_code(arguments)
    else:
        return f"错误：未知工具 '{name}'"


def _search_knowledge_base(arguments: dict, mode: str, conv_id: str | None) -> str:
    try:
        from .rag_service import search_with_rerank
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)

        results = search_with_rerank(query=query, mode=mode, conv_id=conv_id, top_k=top_k)

        if not results:
            return "未找到相关文档。"

        parts = []
        for i, r in enumerate(results):
            meta = json.loads(r.get("metadata", "{}")) if r.get("metadata") else {}
            source = meta.get("filename", "未知来源")
            content = r["content"][:500]
            parts.append(f"[{i + 1}] 来源: {source}\n{content}")

        return "\n\n".join(parts)

    except Exception as e:
        logger.error(f"[tool_executor] search_knowledge_base failed: {e}")
        return f"搜索失败: {e}"


def _resolve_file_path(file_path: str, mode: str, conv_id: str | None) -> Path | None:
    from .file_service import _get_conv_dir, FILE_DIR

    basename = Path(file_path).name

    if conv_id:
        try:
            conv_dir = _get_conv_dir(conv_id, mode)
            candidate = conv_dir / basename
            if candidate.exists():
                return candidate
            for f in conv_dir.iterdir():
                if f.is_file() and (f.name == basename or f.stem == Path(basename).stem):
                    return f
        except Exception:
            pass

    mode_dir = FILE_DIR / mode
    if mode_dir.exists():
        for f in mode_dir.rglob(basename):
            if f.is_file():
                return f

    return None


def _read_file(arguments: dict, mode: str = "chat", conv_id: str | None = None) -> str:
    try:
        from .file_service import read_text_file
        file_path = arguments.get("file_path", "")
        if not file_path:
            return "错误：未指定文件路径"

        path = Path(file_path)
        if not path.exists():
            resolved = _resolve_file_path(file_path, mode, conv_id)
            if resolved:
                logger.info(f"[tool_executor] Resolved file path: {file_path} -> {resolved}")
                file_path = str(resolved)
            else:
                return f"错误：文件不存在: {file_path}"

        content = read_text_file(file_path)
        if not content:
            return "文件为空或无法读取"

        if len(content) > 3000:
            content = content[:3000] + "\n\n... (内容过长，已截断)"

        return content

    except Exception as e:
        logger.error(f"[tool_executor] read_file failed: {e}")
        return f"读取文件失败: {e}"


def _list_files(arguments: dict, conv_id: str | None) -> str:
    try:
        from ..database import get_files_by_conv
        cid = arguments.get("conv_id") or conv_id
        if not cid:
            return "未指定会话ID"

        files = get_files_by_conv(cid)
        if not files:
            return "当前会话没有关联文件"

        parts = []
        for f in files:
            gen = "生成" if f.get("is_generated") else "上传"
            parts.append(f"- {f['filename']} ({gen}, {f.get('file_format', '')}, {f.get('file_size', 0)} bytes)")

        return "\n".join(parts)

    except Exception as e:
        logger.error(f"[tool_executor] list_files failed: {e}")
        return f"列出文件失败: {e}"


def _execute_code(arguments: dict) -> str:
    code = arguments.get("code", "")
    if not code.strip():
        return "错误：代码为空"

    blocked = ["import os", "import subprocess", "import shutil", "os.system", "os.remove",
               "os.rmdir", "shutil.rmtree", "__import__", "eval(", "exec(",
               "open(", "import sys", "sys.exit"]
    for b in blocked:
        if b in code:
            return f"错误：代码包含不允许的操作: {b}"

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            safe_code = "import json\nimport math\nimport re\nfrom collections import Counter, defaultdict\nfrom datetime import datetime\n\n"
            safe_code += "_results = []\n"
            safe_code += code + "\n"
            safe_code += "\nif _results:\n    print(json.dumps(_results, ensure_ascii=False, default=str))\n"
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=CODE_TIMEOUT,
        )

        try:
            Path(tmp_path).unlink()
        except Exception:
            pass

        output = result.stdout.strip()
        if not output and result.stderr.strip():
            output = f"错误输出: {result.stderr.strip()[:1000]}"

        if len(output) > MAX_CODE_OUTPUT:
            output = output[:MAX_CODE_OUTPUT] + "\n... (输出过长，已截断)"

        return output or "代码执行完成（无输出）"

    except subprocess.TimeoutExpired:
        return f"错误：代码执行超时（{CODE_TIMEOUT}秒）"
    except Exception as e:
        return f"代码执行失败: {e}"
