#!/bin/bash
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CLI_DIR="$SCRIPT_DIR/cli"
AI_CORE_DIR="$SCRIPT_DIR/ai-core"
WEB_DIR="$SCRIPT_DIR/web"

export PYTHONIOENCODING=utf-8

find_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_EXE="python3"
        return 0
    elif command -v python &> /dev/null; then
        PYTHON_EXE="python"
        return 0
    fi
    return 1
}

ensure_cli_ready() {
    if [ ! -d "$CLI_DIR/node_modules" ]; then
        echo "Installing CLI dependencies..."
        cd "$CLI_DIR"
        npm install
        if [ $? -ne 0 ]; then
            echo "ERROR: CLI npm install failed"
            echo "Fix: cd $CLI_DIR && npm install"
            return 1
        fi
        cd "$SCRIPT_DIR"
    fi

    NEED_BUILD=0
    if [ ! -f "$CLI_DIR/dist/index.js" ]; then
        NEED_BUILD=1
    else
        SRC_TIME=$(stat -c %Y "$CLI_DIR/src/index.ts" 2>/dev/null || stat -f %m "$CLI_DIR/src/index.ts" 2>/dev/null)
        DIST_TIME=$(stat -c %Y "$CLI_DIR/dist/index.js" 2>/dev/null || stat -f %m "$CLI_DIR/dist/index.js" 2>/dev/null)
        if [ -n "$SRC_TIME" ] && [ -n "$DIST_TIME" ] && [ "$SRC_TIME" -gt "$DIST_TIME" ]; then
            NEED_BUILD=1
        fi
    fi

    if [ "$NEED_BUILD" = "1" ]; then
        echo "Building CLI..."
        cd "$CLI_DIR"
        npm run build
        if [ $? -ne 0 ]; then
            echo "ERROR: CLI build failed"
            echo "Fix: cd $CLI_DIR && npm run build"
            cd "$SCRIPT_DIR"
            return 1
        fi
        cd "$SCRIPT_DIR"
    fi
    return 0
}

do_install() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║       LVV 办公助手 - 安装依赖           ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    echo "[1/6] 检查运行环境..."
    if ! find_python; then
        echo "❌ 未找到 Python！请安装 Python 3.10+"
        echo "   https://www.python.org/downloads/"
        exit 1
    fi
    $PYTHON_EXE --version
    echo "✅ Python 就绪"

    if ! command -v node &> /dev/null; then
        echo "❌ 未找到 Node.js！请安装 Node.js 18+"
        echo "   https://nodejs.org/"
        exit 1
    fi
    echo "✅ Node.js 就绪"
    echo ""

    echo "[2/6] 安装 Python 后端依赖..."
    cd "$AI_CORE_DIR"
    if [ ! -d ".venv" ]; then
        echo "   创建虚拟环境..."
        $PYTHON_EXE -m venv .venv
        if [ $? -ne 0 ]; then
            echo "   ❌ 虚拟环境创建失败！"
            echo "   Ubuntu/Debian: sudo apt install python3-venv"
            exit 1
        fi
        echo "   虚拟环境已创建"
    fi

    echo "   安装依赖包..."
    if [ -f ".venv/Scripts/python.exe" ]; then
        VENV_PYTHON=".venv/Scripts/python.exe"
    elif [ -f ".venv/bin/python3" ]; then
        VENV_PYTHON=".venv/bin/python3"
    else
        VENV_PYTHON=".venv/bin/python"
    fi
    "$VENV_PYTHON" -m pip install --upgrade pip -q 2>/dev/null || echo "   ⚠️  pip 更新跳过"
    "$VENV_PYTHON" -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "   ❌ Python 依赖安装失败，请检查网络后重试"
        exit 1
    fi
    echo "✅ Python 依赖安装完成"
    echo ""

    echo "[3/6] 验证后端依赖..."
    "$VENV_PYTHON" -c "import fastapi, openai, uvicorn; print('   核心依赖 OK')" 2>/dev/null && \
        echo "✅ 后端依赖验证通过" || echo "   ⚠️  验证跳过"
    echo ""

    echo "[3.5/6] 安装 AI Core Node.js 渲染器 (pptx, docx)..."
    cd "$AI_CORE_DIR/pptx-renderer"
    if [ ! -d "node_modules" ]; then
        echo "   安装 pptxgenjs..."
        npm install
        if [ $? -ne 0 ]; then
            echo "   ⚠️  pptx-renderer 安装失败，PPT 生成可能不可用"
        fi
    else
        echo "   pptx-renderer 已安装"
    fi
    cd "$AI_CORE_DIR/docx-renderer"
    if [ ! -d "node_modules" ]; then
        echo "   安装 docx-js..."
        npm install
        if [ $? -ne 0 ]; then
            echo "   ⚠️  docx-renderer 安装失败，DOCX 生成可能不可用"
        fi
    else
        echo "   docx-renderer 已安装"
    fi
    echo "✅ Node.js 渲染器就绪"
    echo ""

    echo "[4/6] 安装 Web 前端依赖..."
    cd "$WEB_DIR"
    if [ ! -d "node_modules" ]; then
        echo "   安装依赖包（可能需要几分钟）..."
        npm install
        if [ $? -ne 0 ]; then
            echo "   ❌ Web 前端依赖安装失败"
            exit 1
        fi
    fi
    echo "✅ Web 前端依赖就绪"
    echo ""

    echo "[5/6] 安装并编译 CLI..."
    cd "$CLI_DIR"
    if [ ! -d "node_modules" ]; then
        echo "   安装依赖包..."
        npm install
        if [ $? -ne 0 ]; then
            echo "   ❌ CLI 依赖安装失败"
            exit 1
        fi
    fi
    echo "   编译 TypeScript..."
    npm run build
    if [ $? -ne 0 ]; then
        echo "   ❌ CLI 编译失败"
        exit 1
    fi
    echo "✅ CLI 就绪"
    echo ""

    echo "[6/6] 配置环境变量..."
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        if [ -f "$SCRIPT_DIR/.env.example" ]; then
            cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
            echo "   .env 文件已从 .env.example 创建"
        else
            cat > "$SCRIPT_DIR/.env" << 'ENVEOF'
QWEN_API_KEY=sk-your-qwen-api-key-here
TENCENT_API_KEY=sk-your-tencent-api-key-here
DEFAULT_PROVIDER=qwen
AI_CORE_HOST=127.0.0.1
AI_CORE_PORT=8000
ENVEOF
            echo "   .env 文件已创建"
        fi
        echo "   ⚠️  请编辑 .env 填入 API Key: $SCRIPT_DIR/.env"
    else
        echo "   .env 已存在"
    fi
    echo "✅ 环境配置完成"
    echo ""

    echo "╔══════════════════════════════════════════╗"
    echo "║  ✅ 全部安装完成！                      ║"
    echo "║                                         ║"
    echo "║  🚀 启动: ./lvv.sh                     ║"
    echo "║  🔑 务必编辑 .env 填入 QWEN_API_KEY     ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""
}

do_backend() {
    echo ""
    echo "启动 AI Core 后端 (端口 8000)..."
    cd "$AI_CORE_DIR"
    if [ ! -d ".venv" ]; then
        echo "❌ 虚拟环境不存在！请先运行: ./lvv.sh install"
        exit 1
    fi
    if [ -f ".venv/Scripts/python.exe" ]; then
        VENV_PYTHON=".venv/Scripts/python.exe"
    elif [ -f ".venv/bin/python3" ]; then
        VENV_PYTHON=".venv/bin/python3"
    else
        VENV_PYTHON=".venv/bin/python"
    fi
    "$VENV_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
    BACKEND_PID=$!
    echo "PID: $BACKEND_PID"
    echo "✅ 后端已启动"
    echo "📖 API 文档: http://localhost:8000/docs"
    echo ""
    trap "kill $BACKEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
    wait
}

do_stop() {
    echo ""
    echo "正在停止所有服务..."
    kill $(lsof -t -i:8000) 2>/dev/null || true
    kill $(lsof -t -i:5173) 2>/dev/null || true
    echo "✅ 所有服务已停止"
    echo ""
}

do_status() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║       服务状态                          ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""
    if lsof -i:8000 &>/dev/null 2>&1; then
        echo "✅ AI Core   运行中 (端口 8000)"
    else
        echo "❌ AI Core   未运行"
    fi
    if lsof -i:5173 &>/dev/null 2>&1; then
        echo "✅ Web 前端  运行中 (端口 5173)"
    else
        echo "❌ Web 前端  未运行"
    fi
    echo ""
    echo "🌐 http://localhost:5173"
    echo "📖 http://localhost:8000/docs"
    echo ""
}

do_help() {
    echo ""
    echo "LVV 办公助手 - 命令参考"
    echo "================================"
    echo ""
    echo "  ./lvv.sh                 启动 CLI（自动编译+运行）"
    echo "  ./lvv.sh install         安装全部依赖"
    echo "  ./lvv.sh backend         仅启动后端"
    echo "  ./lvv.sh stop            停止所有服务"
    echo "  ./lvv.sh status          查看服务状态"
    echo "  ./lvv.sh help            显示此帮助"
    echo "  ./lvv.sh [任意CLI命令]    透传给 CLI 执行"
    echo ""
    echo "  ⚡ 首次使用请先: ./lvv.sh install"
    echo "  ⚡ 配置 API Key 请编辑 .env 文件"
    echo ""
}

command="${1:-}"
case "$command" in
    install)
        do_install
        ;;
    backend)
        do_backend
        ;;
    stop)
        do_stop
        ;;
    status)
        do_status
        ;;
    help|--help|-h)
        do_help
        ;;
    *)
        ensure_cli_ready || exit 1
        if [ $# -eq 0 ]; then
            node "$CLI_DIR/dist/index.js" start
        else
            node "$CLI_DIR/dist/index.js" "$@"
        fi
        if [ $? -ne 0 ]; then
            echo ""
            echo "ERROR: CLI runtime error"
        fi
        ;;
esac