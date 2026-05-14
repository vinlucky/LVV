import logging

logger = logging.getLogger(__name__)

TOOLS = {
    "search_knowledge_base": {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "在知识库中搜索与查询相关的文档片段。当需要查找特定信息、数据或文档内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询关键词",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定路径的文件内容。支持 txt、md、pdf、docx、xlsx、pptx 等格式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    "list_files": {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出当前会话关联的所有文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "conv_id": {
                        "type": "string",
                        "description": "会话ID",
                    },
                },
                "required": [],
            },
        },
    },
    "execute_code": {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "执行 Python 代码片段并返回输出结果。用于数据处理、计算、格式转换等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码",
                    },
                },
                "required": ["code"],
            },
        },
    },
}

MODE_TOOL_MAP = {
    "chat": ["search_knowledge_base", "read_file", "list_files", "execute_code"],
    "meeting": ["search_knowledge_base", "read_file", "list_files"],
    "literature": ["search_knowledge_base", "read_file", "list_files"],
    "polish": ["search_knowledge_base", "read_file"],
    "ppt": ["search_knowledge_base", "read_file", "list_files"],
}


def get_tools_for_mode(mode: str) -> list[dict]:
    tool_names = MODE_TOOL_MAP.get(mode, MODE_TOOL_MAP["chat"])
    tools = []
    for name in tool_names:
        if name in TOOLS:
            tools.append(TOOLS[name])
    return tools


def get_all_tools() -> list[dict]:
    return list(TOOLS.values())
