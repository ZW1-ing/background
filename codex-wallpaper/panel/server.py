#!/usr/bin/env python3
"""Local control panel for the Codex wallpaper patcher."""

import argparse
import base64
import binascii
import dataclasses
import json
import mimetypes
import os
import pathlib
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HERE = pathlib.Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
STATIC_ROOT = HERE / "static"
PATCHER = SKILL_ROOT / "scripts" / "codex_theme_patcher.py"
DEFAULT_IMAGE = SKILL_ROOT / "assets" / "default-wallpaper.png"
STATE_ROOT = pathlib.Path.home() / ".codex-wallpaper"
STATE_FILE = STATE_ROOT / "state.json"
CONFIG_FILE = STATE_ROOT / "config.json"
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_REQUEST_BYTES = 45 * 1024 * 1024

MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}


@dataclasses.dataclass(frozen=True)
class DecodedImage:
    extension: str
    data: bytes


def decode_image_data_uri(data_uri):
    if not isinstance(data_uri, str) or not data_uri.startswith("data:"):
        raise ValueError("图片数据格式无效")
    try:
        header, encoded = data_uri.split(",", 1)
    except ValueError as exc:
        raise ValueError("图片数据不完整") from exc
    if ";base64" not in header:
        raise ValueError("图片必须使用 base64 编码")
    mime = header[5:].split(";", 1)[0].lower()
    extension = MIME_EXTENSIONS.get(mime)
    if not extension:
        raise ValueError("仅支持 PNG、JPEG、WebP、GIF 和 BMP 图片")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("图片 base64 数据无效") from exc
    if not data:
        raise ValueError("图片内容为空")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("图片不能超过 30 MB")
    return DecodedImage(extension=extension, data=data)


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)


def current_image_path():
    for extension in MIME_EXTENSIONS.values():
        path = STATE_ROOT / ("current-image" + extension)
        if path.exists():
            return path
    return None


def remove_stale_images(keep_path=None):
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    for extension in MIME_EXTENSIONS.values():
        path = STATE_ROOT / ("current-image" + extension)
        if path != keep_path and path.exists():
            path.unlink()


def run_patcher(arguments):
    command = [sys.executable, str(PATCHER), *arguments]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=300,
    )
    return result.returncode, result.stdout.strip()


def status_payload():
    return_code, output = run_patcher(["--status"])
    state = read_json(STATE_FILE, {})
    return {
        "ok": return_code == 0,
        "status": output,
        "config": state.get("config"),
        "imageName": state.get("imageName"),
        "hasImage": current_image_path() is not None,
        "defaultImageUrl": "/assets/default-wallpaper.png",
    }


def locate_app_path():
    override = os.environ.get("CODEX_APP_PATH")
    if override and os.path.exists(override):
        return override
    for candidate in ("/Applications/Codex.app", "/Applications/ChatGPT.app"):
        if os.path.exists(candidate):
            return candidate
    return None


def app_is_running(app_path):
    app_name = pathlib.Path(app_path).stem
    executable = os.path.join(app_path, "Contents", "MacOS", app_name)
    result = subprocess.run(
        ["/bin/ps", "-axo", "pid=,comm="],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and fields[1] == executable:
            return True
    return False


def restart_app():
    app_path = locate_app_path()
    if app_path is None:
        return False, "没有找到 Codex 或 ChatGPT 应用。"
    app_name = pathlib.Path(app_path).stem
    output = []

    if app_is_running(app_path):
        result = subprocess.run(
            ["osascript", "-e", 'tell application "%s" to quit' % app_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            return False, detail or "无法自动退出 ChatGPT。"
        output.append("ChatGPT 已关闭。")
        for _ in range(30):
            if not app_is_running(app_path):
                break
            time.sleep(0.25)
        else:
            return False, "ChatGPT 仍在运行，请手动退出后重新打开。"

    result = subprocess.run(
        ["open", app_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        return False, detail or "无法重新打开 ChatGPT。"
    output.append("ChatGPT 已重新打开。")
    return True, "\n".join(output)


class PanelHandler(BaseHTTPRequestHandler):
    server_version = "CodexWallpaperPanel/1.0"

    def log_message(self, format, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, data, content_type, cache_control="no-store"):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(data)

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length 无效") from exc
        if length <= 0:
            raise ValueError("请求内容为空")
        if length > MAX_REQUEST_BYTES:
            raise ValueError("请求内容过大")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("请求 JSON 无效") from exc
        if not isinstance(value, dict):
            raise ValueError("请求 JSON 必须是对象")
        return value

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route == "/":
            return self.serve_static(STATIC_ROOT / "index.html")
        if route == "/styles.css":
            return self.serve_static(STATIC_ROOT / "styles.css")
        if route == "/app.js":
            return self.serve_static(STATIC_ROOT / "app.js")
        if route == "/assets/default-wallpaper.png":
            return self.serve_static(DEFAULT_IMAGE, cache_control="public, max-age=3600")
        if route == "/api/current-image":
            image_path = current_image_path()
            if image_path is None:
                image_path = DEFAULT_IMAGE
            content_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
            return self.serve_static(image_path, content_type=content_type)
        if route == "/api/state":
            return self.send_json(status_payload())
        self.send_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        route = self.path.split("?", 1)[0]
        try:
            body = self.read_json_body()
            if route == "/api/apply":
                return self.apply_wallpaper(body)
            if route == "/api/restore":
                return self.restore_wallpaper()
            if route == "/api/restart":
                return self.restart_wallpaper()
        except ValueError as exc:
            return self.send_json(
                {"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST
            )
        except subprocess.TimeoutExpired:
            return self.send_json(
                {"ok": False, "error": "操作超时，请查看背景控制面板终端"},
                HTTPStatus.GATEWAY_TIMEOUT,
            )
        except OSError as exc:
            return self.send_json(
                {"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR
            )
        self.send_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def apply_wallpaper(self, body):
        image_data = body.pop("imageData", None)
        config = body.get("config")
        if not isinstance(config, dict):
            raise ValueError("缺少背景参数")

        image_path = current_image_path()
        if image_data:
            decoded = decode_image_data_uri(image_data)
            image_path = STATE_ROOT / ("current-image" + decoded.extension)
            STATE_ROOT.mkdir(parents=True, exist_ok=True)
            temp_path = image_path.with_suffix(image_path.suffix + ".tmp")
            with open(temp_path, "wb") as handle:
                handle.write(decoded.data)
            os.replace(temp_path, image_path)
            remove_stale_images(keep_path=image_path)

        write_json(CONFIG_FILE, config)
        state = {
            "config": config,
            "imageName": body.get("imageName"),
            "imagePath": str(image_path) if image_path else None,
        }
        write_json(STATE_FILE, state)

        arguments = ["--config", str(CONFIG_FILE)]
        if image_path is not None:
            arguments.extend(["--image", str(image_path)])
        return_code, output = run_patcher(arguments)
        payload = {
            "ok": return_code == 0,
            "output": output,
            "state": status_payload(),
        }
        if return_code != 0:
            payload["error"] = "应用失败，请查看下方输出"
            return self.send_json(payload, HTTPStatus.BAD_REQUEST)
        self.send_json(payload)

    def restore_wallpaper(self):
        return_code, output = run_patcher(["--restore"])
        payload = {
            "ok": return_code == 0,
            "output": output,
            "state": status_payload(),
        }
        if return_code != 0:
            payload["error"] = "恢复失败，请查看下方输出"
            return self.send_json(payload, HTTPStatus.BAD_REQUEST)
        self.send_json(payload)

    def restart_wallpaper(self):
        ok, output = restart_app()
        payload = {"ok": ok, "output": output}
        if not ok:
            payload["error"] = output
            return self.send_json(payload, HTTPStatus.BAD_REQUEST)
        self.send_json(payload)

    def serve_static(self, path, content_type=None, cache_control="no-store"):
        try:
            data = pathlib.Path(path).read_bytes()
        except OSError:
            return self.send_json(
                {"ok": False, "error": "Static file not found"},
                HTTPStatus.NOT_FOUND,
            )
        if content_type is None:
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_bytes(data, content_type, cache_control=cache_control)


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_server(host, port, open_browser):
    try:
        server = PanelServer((host, port), PanelHandler)
    except OSError:
        if port == 0:
            raise
        # A fixed port means the control panel lives at a stable URL. Silently
        # moving to a random port would break that contract, so report and stop
        # instead. Exiting cleanly also keeps launchd from restart-looping.
        print("端口 %d 已被占用，控制面板可能已经在运行。" % port)
        print("如果浏览器无法访问，请先关闭占用该端口的程序后重试。")
        return
    actual_port = server.server_address[1]
    url = "http://%s:%d" % (host, actual_port)
    print("Codex 背景控制面板: %s" % url)
    print("按 Ctrl+C 退出。")
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在退出。")
    finally:
        server.server_close()


def parse_args():
    parser = argparse.ArgumentParser(description="Codex wallpaper control panel")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    start_server(args.host, args.port, not args.no_open)


if __name__ == "__main__":
    main()
