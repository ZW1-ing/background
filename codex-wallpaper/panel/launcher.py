#!/usr/bin/env python3
"""Start the local control panel as a detached, user-facing process."""

import argparse
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


HERE = pathlib.Path(__file__).resolve().parent
SERVER = HERE / "server.py"
SCRIPTS_ROOT = HERE.parent / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from platform_support import state_root  # noqa: E402


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
STARTUP_ATTEMPTS = 40
STARTUP_DELAY = 0.25


def panel_url(port, host=DEFAULT_HOST):
    return "http://%s:%d/" % (host, port)


def is_panel_up(port, host=DEFAULT_HOST, timeout=2):
    url = panel_url(port, host) + "api/health"
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _detached_process_options():
    if os.name == "nt":
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return {"creationflags": flags}
    return {"start_new_session": True}


def start_panel(port=DEFAULT_PORT, host=DEFAULT_HOST, open_browser=True):
    """Ensure the panel is running and optionally open it in the browser."""
    url = panel_url(port, host)
    if is_panel_up(port, host):
        if open_browser:
            webbrowser.open(url)
        return True

    panel_state = state_root()
    panel_state.mkdir(parents=True, exist_ok=True)
    log_path = panel_state / "panel.log"
    command = [
        sys.executable,
        str(SERVER),
        "--host",
        host,
        "--port",
        str(port),
        "--no-open",
    ]
    options = {
        "stdin": subprocess.DEVNULL,
        "stdout": None,
        "stderr": subprocess.STDOUT,
        "close_fds": True,
    }
    options.update(_detached_process_options())
    with open(log_path, "a", encoding="utf-8") as log:
        options["stdout"] = log
        subprocess.Popen(command, **options)

    for _attempt in range(STARTUP_ATTEMPTS):
        if is_panel_up(port, host):
            if open_browser:
                webbrowser.open(url)
            return True
        time.sleep(STARTUP_DELAY)

    print("控制面板启动失败。")
    print("请查看日志：%s" % log_path)
    return False


def parse_args():
    parser = argparse.ArgumentParser(description="Start the Codex wallpaper panel")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    return 0 if start_panel(args.port, args.host, not args.no_open) else 1


if __name__ == "__main__":
    raise SystemExit(main())
