MODE_KEYWORDS = {
    "meeting": {
        "keywords": ["会议", "纪要", "开会", "讨论", "决议", "参会", "议程", "记录", "minutes", "meeting", "录音", "转写"],
        "name": "🎙️ 会议纪要",
    },
    "literature": {
        "keywords": ["文献", "论文", "摘要", "学术", "研究", "期刊", "综述", "引用", "参考文献", "literature", "paper", "abstract", "doi", "期刊", "SCI"],
        "name": "📚 文献摘要",
    },
    "polish": {
        "keywords": ["润色", "翻译", "语法", "修正", "英文邮件", "教授邮件", "日文", "韩文", "法文", "德文", "西语", "俄语", "polish", "translate", "grammar", "proofread", "翻译成", "润色成", "润色这段"],
        "name": "✍️ 多语言润色",
    },
    "ppt": {
        "keywords": ["ppt", "PPT", "幻灯片", "演示", "简报", "presentation", "slides", "大纲", "演示文稿", "演讲稿"],
        "name": "📊 PPT生成",
    },
    "xlsx": {
        "keywords": ["excel", "Excel", "表格", "电子表格", "xlsx", "报表", "数据表", "spreadsheet", "工作表", "汇总表", "统计表"],
        "name": "📊 Excel生成",
    },
    "docx": {
        "keywords": ["word", "Word", "文档", "docx", "报告", "方案", "说明书", "document", "文档生成", "技术文档", "需求文档"],
        "name": "📃 文档生成",
    },
}

MODE_DISPLAY_NAMES = {
    "chat": "💬 通用对话",
    "meeting": "🎙️ 会议纪要",
    "literature": "📚 文献摘要",
    "polish": "✍️ 多语言润色",
    "ppt": "📊 PPT生成",
    "xlsx": "📊 Excel生成",
    "docx": "📃 文档生成",
}


def detect_mode_suggestion(user_message: str, current_mode: str) -> dict | None:
    if current_mode == "chat":
        message_lower = user_message.lower()
        scores = {}
        for mode, config in MODE_KEYWORDS.items():
            if mode in ("xlsx", "docx"):
                continue
            score = 0
            for kw in config["keywords"]:
                if kw.lower() in message_lower:
                    score += 1
                if kw in user_message:
                    score += 2
            if score >= 2:
                scores[mode] = score

        if scores:
            best_mode = max(scores, key=scores.get)
            if best_mode != current_mode:
                reason_map = {
                    "meeting": "检测到会议记录、纪要相关字词，建议使用会议纪要模式以获得更好的生成效果",
                    "literature": "检测到文献、论文等相关字词，建议使用文献摘要模式以获得结构化分析",
                    "polish": "检测到润色、翻译等字词，建议使用多语言润色模式进行专业文本处理",
                    "ppt": "检测到PPT、演示相关字词，建议使用PPT生成模式直接生成可下载的演示文稿",
                }
                return {
                    "type": "mode_suggestion",
                    "suggested_mode": best_mode,
                    "current_mode": current_mode,
                    "reason": reason_map.get(best_mode, f"建议使用{MODE_KEYWORDS[best_mode]['name']}模式"),
                    "mode_name": MODE_KEYWORDS[best_mode]["name"],
                }

    non_chat_suggestions = {
        "meeting": ("chat", "检测到文字输入但不涉及会议内容，建议使用通用对话模式"),
        "literature": ("chat", "检测到非文献内容，建议使用通用对话模式"),
        "polish": ("chat", "检测到非润色/翻译需求，建议使用通用对话模式"),
        "ppt": ("chat", "检测到非PPT生成需求，建议使用通用对话模式"),
        "xlsx": ("chat", "检测到非Excel生成需求，建议使用通用对话模式"),
        "docx": ("chat", "检测到非文档生成需求，建议使用通用对话模式"),
    }

    if current_mode in non_chat_suggestions:
        message_lower = user_message.lower()
        mode_config = MODE_KEYWORDS.get(current_mode, {})
        match_score = 0
        for kw in mode_config.get("keywords", []):
            if kw.lower() in message_lower:
                match_score += 1

        if match_score == 0:
            suggested, reason = non_chat_suggestions[current_mode]
            if suggested == "chat":
                return None


def detect_auto_file_type(user_message: str) -> str | None:
    message_lower = user_message.lower()
    for mode in ("xlsx", "docx"):
        config = MODE_KEYWORDS.get(mode, {})
        score = 0
        for kw in config.get("keywords", []):
            if kw.lower() in message_lower:
                score += 1
            if kw in user_message:
                score += 2
        if score >= 2:
            return mode
    return None


REACT_KEYWORDS = [
    "搜索", "查找", "查找一下", "帮我找", "找一下", "查一下",
    "检索", "查询", "搜索一下", "搜一下",
    "分析数据", "计算", "统计", "数据处理",
    "读取文件", "看看文件", "文件内容",
    "知识库", "文档中",
]


def detect_react_intent(user_message: str) -> bool:
    message_lower = user_message.lower()
    for kw in REACT_KEYWORDS:
        if kw in message_lower or kw in user_message:
            return True
    return False