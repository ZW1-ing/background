#!/bin/zsh
# Opens the Codex wallpaper control panel.
#
# Double-click this file. macOS runs it in Terminal, which is what lets the
# panel rewrite the app's app.asar (that write is protected by macOS "App
# Management"). The panel is detached with nohup, so you can close the Terminal
# window and the panel keeps running at the stable address below.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$SCRIPT_DIR/panel/launcher.py"
STATE_DIR="$HOME/.codex-wallpaper"
PORT="${CODEX_WALLPAPER_PORT:-8765}"
PYTHON="$(command -v python3 2>/dev/null || true)"

mkdir -p "$STATE_DIR"

if [[ -z "$PYTHON" ]]; then
  echo "未找到 python3。请先安装 Python 3 后再运行控制面板。"
  read -r "?按回车键退出…"
  exit 1
fi

if ! "$PYTHON" "$LAUNCHER" --port "$PORT"; then
  echo "控制面板启动失败。日志：$STATE_DIR/panel.log"
  open "$STATE_DIR/panel.log" >/dev/null 2>&1 || true
  read -r "?按回车键退出…"
  exit 1
fi
