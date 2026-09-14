#!/bin/zsh
# Opens the Codex wallpaper control panel.
#
# Double-click this file. macOS runs it in Terminal, which is what lets the
# panel rewrite the app's app.asar (that write is protected by macOS "App
# Management"). The panel is detached with nohup, so you can close the Terminal
# window and the panel keeps running at the stable address below.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="$SCRIPT_DIR/panel/server.py"
STATE_DIR="$HOME/.codex-wallpaper"
PORT="${CODEX_WALLPAPER_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"
PYTHON="$(command -v python3 2>/dev/null || true)"

mkdir -p "$STATE_DIR"

panel_is_up() {
  curl -fsS --max-time 2 "${URL}/api/state" >/dev/null 2>&1
}

if panel_is_up; then
  open "$URL" >/dev/null 2>&1 || true
  exit 0
fi

if [[ -z "$PYTHON" ]]; then
  echo "未找到 python3。请先安装 Python 3 后再运行控制面板。"
  read -r "?按回车键退出…"
  exit 1
fi

# Detach the server so it survives this Terminal window being closed. Running
# from Terminal (not launchd) is deliberate: Terminal holds the macOS "App
# Management" grant that the patcher needs to modify the app bundle.
nohup "$PYTHON" "$SERVER" --port "$PORT" --no-open \
  >>"$STATE_DIR/panel.log" 2>&1 </dev/null &
disown 2>/dev/null || true

started=0
for attempt in {1..40}; do
  if panel_is_up; then
    started=1
    break
  fi
  sleep 0.25
done

if [[ "$started" -eq 1 ]]; then
  open "$URL" >/dev/null 2>&1 || true
  exit 0
fi

echo "控制面板启动失败。日志：$STATE_DIR/panel.log"
echo "如果日志写着端口被占用，请先关闭占用 ${PORT} 端口的程序。"
open "$STATE_DIR/panel.log" >/dev/null 2>&1 || true
read -r "?按回车键退出…"
exit 1
