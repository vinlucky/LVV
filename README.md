<div align="center">


<h1 align="center">LVV</h1>

<p align="center">
  <b>乐活 Love Working — AI 驱动的全能办公助手</b><br/>

</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#核心能力">核心能力</a> ·
  <a href="#系统架构">系统架构</a> · ·
  <a href="https://github.com/vinlucky/LVV/issues">报告问题</a>
</p>

<p align="center">
  <a href="README.md">简体中文</a> ·
</p>


<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/badge/node-18+-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="node">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white" alt="platform">
  <img src="https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white" alt="fastapi">
  <img src="https://img.shields.io/badge/Vue-3-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white" alt="vue">
</p>

</div>

<br/>

> [!NOTE]
> **LVV 是你的 AI 办公伙伴。**
> 它能帮你写会议纪要、生成文献摘要、润色多语言文本、创建 PPT 和文档 — 全部通过 Actor-Critic 循环确保输出质量。
> 一个命令启动，开箱即用。

> [!TIP]
> LVV 支持千问 (Qwen) 和腾讯混元 (Hunyuan) 等国产大模型，数据全部留在本地 SQLite，无需云端同步。

<br/>

---

## 目录

- [快速开始](#快速开始)
- [LVV 是什么](#lvv-是什么)
- [核心能力](#核心能力)
- [系统架构](#系统架构)
- [Skills 扩展](#skills-扩展)
- [项目结构](#项目结构)
- [开发指南](#开发指南)
- [设计哲学](#设计哲学)
- [致谢](#致谢)
- [许可证](#许可证)

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.13+ | 后端运行时 |
| Node.js | 18+ | 前端 & CLI |
| OS | **Windows**（主要）/ macOS & Linux | |

### 1. 克隆 & 安装

```bash
git clone https://github.com/Violet2314/LVV.git
cd LVV

#一键安装
lvv install
```

安装脚本会自动：
- 创建 Python 虚拟环境并安装依赖
- 安装 Node.js 前端和 CLI 依赖
- 安装 PPT/DOCX 渲染器
- 从 `.env.example` 创建 `.env` 配置文件

### 2. 配置 API Key

编辑项目根目录的 `.env` 文件，填入你的 API Key（或者在CLI初始化引导时填入）：

```bash
# 千问 (Qwen/DashScope) — 推荐
QWEN_API_KEY=sk-your-qwen-api-key-here

# 腾讯混元 (Hunyuan) — 可选
TENCENT_API_KEY=sk-your-tencent-api-key-here

# 默认 AI 提供方
DEFAULT_PROVIDER=qwen
```

> 获取千问 API Key: https://dashscope.console.aliyun.com/apiKey

### 3. 启动

```bash
# Windows
lvv.cmd

# 或 Linux/macOS
./lvv.sh
```

CLI 会自动启动后端服务，进入交互式菜单。

### 4. 使用 Web 界面

```bash
# 仅启动后端
start-backend.bat

# 在另一个终端启动前端
cd web
npm install
npm run dev
```

Web 界面访问 `http://localhost:5173`，API 文档 `http://localhost:8000/docs`。

### 命令速查

```bash
lvv                    # 启动交互式 CLI
lvv install            # 安装所有依赖
lvv backend            # 仅启动后端
lvv stop               # 停止所有服务
lvv status             # 查看服务状态
lvv chat "你好"        # 通用对话
lvv meeting            # 生成会议纪要
lvv literature ./paper.pdf  # 文献摘要
lvv polish             # 多语言润色
lvv ppt "AI发展趋势"   # 生成 PPT
lvv skill list         # 查看已安装 Skills
lvv skill import       # 导入新 Skill
```

---

## LVV 是什么

LVV (Love Working) 是一个 AI 驱动的全能办公助手，围绕 **六个核心场景**展开：

```
💬 对话 → 📝 纪要 → 📚 摘要 → ✨ 润色 → 📊 PPT → 📄 文档
   ↑                                              │
   └──────── Actor-Critic 质量闭环 ←──────────────┘
```

与普通 AI 助手不同，LVV 的每次输出都经过 **Actor-Critic 循环**：
- **Actor** 生成初稿
- **Critic** 审查质量，不通过则 Actor 重新生成
- 直到 Critic 通过，才输出最终结果

这确保了会议纪要不会遗漏要点、润色不会偏离原意、PPT 逻辑清晰完整。

---

## 核心能力

### 💬 通用对话

- 基于 ReAct 循环的多轮对话，支持工具调用
- 自动检测输入意图，建议切换到更合适的模式
- 流式输出，实时查看生成过程

### 📝 会议纪要

- 支持文本输入或上传录音文件
- 录音自动转写（Whisper 语音识别）
- 生成结构化会议纪要：议题、决议、待办、时间线
- 支持中文/英文/双语对照

### 📚 文献摘要

- 上传 PDF 文献，自动提取关键信息
- 生成详细摘要：研究背景、方法、结果、贡献
- 支持自定义查询问题
- PDF OCR 支持（PaddleOCR）

### ✨ 多语言润色

- 自动检测源语言
- 支持 12 种语言互译润色
- 5 种写作风格：学术写作、商业计划书、正式公文、教授邮件、日常交流
- 语言不匹配时自动提示翻译/仅润色选择

### 📊 PPT 生成

- 输入主题 + 参考内容，自动生成 PPT 大纲
- 大纲预览确认后，渲染为完整 PPTX 文件
- 基于 pptxgenjs 的专业渲染引擎
- 支持多种模板风格

### 📄 文档 & 表格

- DOCX 文档生成与编辑（基于 python-docx + docx-js 渲染器）
- XLSX 表格处理（基于 openpyxl）
- PDF 表单填写与提取（基于 pypdf + pdfplumber）
- 文件格式自动识别与处理

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层                                 │
│                                                              │
│   Web UI (Vue 3)  │  CLI (Node.js)  │  API Docs (Swagger)  │
└──────────────────┬──────────────────────────────────────────┘
                   │  HTTP / SSE
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI 后端 (AI Core)                     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │  LLM Service │  │  Actor-Critic│  │  Mode Detector │    │
│  │ ─ Qwen       │  │ ─ Actor      │  │ ─ auto detect  │    │
│  │ ─ Hunyuan    │  │ ─ Critic     │  │ ─ suggestion   │    │
│  │ ─ fallback   │  │ ─ ReAct loop │  │ ─ mode switch  │    │
│  └──────────────┘  └──────────────┘  └────────────────┘    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │  RAG Service │  │  File Service│  │  Tool Registry │    │
│  │ ─ chunk      │  │ ─ PDF/DOCX   │  │ ─ skills       │    │
│  │ ─ embed      │  │ ─ PPT/XLSX   │  │ ─ import/export│    │
│  │ ─ retrieve   │  │ ─ auto detect│  │ ─ execute      │    │
│  └──────────────┘  └──────────────┘  └────────────────┘    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │  Whisper ASR │  │  Renderers   │                         │
│  │ ─ transcribe │  │ ─ pptx-js    │                         │
│  │ ─ multi-lang │  │ ─ docx-js    │                         │
│  └──────────────┘  └──────────────┘                         │
│                                                              │
│   Routes: chat · meeting · literature · polish · ppt · ...   │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼
          ┌─────────────────────┐
          │  Local Storage      │
          │  ─ SQLite (lvv.db)  │
          │  ─ sqlite-vec       │
          │  ─ config/models    │
          │  ─ skills/          │
          │  ─ file/            │
          └─────────────────────┘
```
---

## 项目结构

```
LVV/
├── ai-core/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 入口，FastAPI 应用
│   │   ├── config.py           # 配置管理（API Key、模型、路径）
│   │   ├── database.py         # SQLite 数据库
│   │   ├── routes/             # API 路由
│   │   │   ├── chat.py         #   通用对话
│   │   │   ├── meeting.py      #   会议纪要
│   │   │   ├── literature.py   #   文献摘要
│   │   │   ├── polish.py       #   多语言润色
│   │   │   ├── ppt.py          #   PPT 生成
│   │   │   ├── docx.py         #   DOCX 处理
│   │   │   ├── xlsx.py         #   XLSX 处理
│   │   │   ├── files.py        #   文件管理
│   │   │   ├── skills.py       #   Skills 管理
│   │   │   └── ...
│   │   └── services/           # 业务逻辑
│   │       ├── llm_service.py  #   LLM 调用与 fallback
│   │       ├── actor_critic.py #   Actor-Critic 循环
│   │       ├── react_loop.py   #   ReAct 推理循环
│   │       ├── rag_service.py  #   RAG 检索增强
│   │       ├── chunk_service.py#   文档分块
│   │       ├── file_service.py #   文件处理
│   │       ├── mode_detector.py#   意图检测
│   │       ├── tool_registry.py#   工具注册
│   │       ├── tool_executor.py#   工具执行
│   │       └── whisper_service.py # 语音转写
│   ├── docx-renderer/          # DOCX Node.js 渲染器
│   ├── pptx-renderer/          # PPTX Node.js 渲染器
│   ├── requirements.txt        # Python 依赖
│   └── .venv/                  # 虚拟环境（安装后生成）
├── cli/                        # Node.js CLI 工具
│   ├── src/index.ts            # CLI 入口
│   └── package.json
├── web/                        # Vue 3 Web 前端
│   ├── src/
│   │   ├── views/              # 页面视图
│   │   ├── components/         # UI 组件
│   │   └── stores/             # Pinia 状态管理
│   └── package.json
├── skills/                     # 内置 Skills
│   ├── docx/
│   ├── pptx/
│   ├── xlsx/
│   ├── pdf/
│   └── doc-coauthoring/
├── config/                     # 模型配置
│   └── models.json5            # LLM 模型与 fallback 链
├── data/                       # 数据目录
│   └── lvv.db                  # SQLite 数据库
├── file/                       # 用户文件存储
├── .env.example                # 环境变量模板
├── install.bat / install.sh    # 安装脚本
├── lvv.cmd / lvv.sh            # 启动入口
└── start-backend.bat/sh        # 后端启动脚本
```

```

**技术栈**：

| 组件 | 技术 |
|---|---|
| HTTP / SSE | FastAPI + uvicorn |
| 结构化存储 | SQLite |
| 向量检索 | sqlite-vec |
| LLM 抽象 | OpenAI SDK（兼容 Qwen / Hunyuan / 任意 OpenAI-compatible 端点） |
| 语音转写 | faster-whisper |
| OCR | PaddleOCR |
| PDF 处理 | pypdf / pdfplumber / pypdfium2 |
| DOCX | python-docx + docx-js 渲染器 |
| PPTX | python-pptx + pptxgenjs 渲染器 |
| XLSX | openpyxl |

### 前端

```bash
cd web
npm install
npm run dev          # Vite 热更新
npm run build        # 生产构建
```

**技术栈**：

| 组件 | 技术 |
|---|---|
| UI 框架 | Vue 3 + TypeScript |
| 状态管理 | Pinia |
| 样式 | Tailwind CSS |
| 构建 | Vite |

---

## 设计哲学

1. **Actor-Critic 闭环** — 每次输出都经过审查，不通过就重来。质量不是概率，是保证。
2. **一键启动** — `lvv` 一个命令，安装、配置、启动全搞定。
3. **国产大模型优先** — 千问、混元开箱即用，也支持任何 OpenAI-compatible 端点。
4. **Skill 可扩展** — 通过 `SKILL.md` 插件系统，任何人都能为 LVV 添加新能力。
5. **本地优先** — 数据全部留在本地 SQLite，没有云端同步，没有遥测上报。
6. **多模态输入** — 文本、PDF、录音、图片，LVV 都能处理。

---

## 致谢

- **Qwen / DashScope** — 强大的国产大模型，LVV 的默认 AI 引擎
- **Tencent Hunyuan** — 优秀的国产大模型备选
- **FastAPI** — 高性能异步 Python Web 框架
- **Whisper** — OpenAI 开源语音识别
- **PaddleOCR** — 百度开源 OCR 引擎
- **pptxgenjs** — 专业 PPT 生成库
- **python-docx / openpyxl / pypdf** — 文档处理三件套

---

## Star History

<a href="https://www.star-history.com/?repos=vinlucky%2FLVV&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=vinlucky/LVV&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=vinlucky/LVV&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=vinlucky/LVV&type=date&legend=top-left" />
 </picture>
</a>

---

## 许可证

本项目采用 [Apache 2.0](LICENSE) 开源协议。

---

<p align="center">
  <sub>
    Made with ❤️ for everyone who wants to love working.<br/>
    如果 LVV 帮到了你，考虑给一个 Star ⭐
  </sub>
</p>
