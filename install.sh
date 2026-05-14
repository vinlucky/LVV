#!/bin/bash
echo ""
echo "  正在通过 lvv.sh install 安装..."
echo ""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/lvv.sh" install