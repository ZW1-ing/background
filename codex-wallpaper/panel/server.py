#!/usr/bin/env python3
"""Local control panel for the Codex wallpaper patcher."""

import argparse
import base64
import binascii
import dataclasses
import hashlib
import json
import mimetypes
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HERE = pathlib.Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
STATIC_ROOT = HERE / "static"
PATCHER = SKILL_ROOT / "scripts" / "codex_theme_patcher.py"
DEFAULT_IMAGE = SKILL_ROOT / "assets" / "default-wallpaper.png"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
from platform_support import (  # noqa: E402
    app_package_path,
    application_from_path,
    default_image_path,
    detect_applications,
    is_windows,
    platform_name,
    state_root,
)

DEFAULT_IMAGE = default_image_path(SKILL_ROOT)
STATE_ROOT = state_root()
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


def application_can_apply(application):
    if not application:
        return False
    return bool(
        application.get("canApply", True)
        or application.get("copyable", False)
    )


def writable_app_copy_root():
    if is_windows():
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return (
                pathlib.Path(local_app_data)
                / "codex-wallpaper"
                / "writable-apps"
            )
    return STATE_ROOT / "writable-apps"


def writable_application_copy(application):
    """Copy a protected Windows installation into a writable user directory."""
    if not application or not application.get("copyable"):
        raise ValueError("当前安装不支持自动副本。")
    source_exe = pathlib.Path(application["executable"])
    if not source_exe.is_file():
        raise ValueError("找不到 Store 版应用文件，无法创建副本。")

    source_dir = source_exe.parent
    key = hashlib.sha256(str(source_dir).encode("utf-8")).hexdigest()[:12]
    copy_root = writable_app_copy_root()
    target_dir = copy_root / ("%s-%s" % (application["name"], key))
    target_exe = target_dir / source_exe.name
    target_asar = target_dir / "resources" / "app.asar"

    if target_exe.is_file() and target_asar.is_file():
        copied = application_from_path(str(target_exe), platform_name="win32")
        if copied:
            return copied, "Reusing writable app copy: %s" % target_dir
        raise ValueError("已有自动副本无效，请删除后重试：%s" % target_dir)

    copy_root.mkdir(parents=True, exist_ok=True)
    temp_dir = pathlib.Path(
        tempfile.mkdtemp(prefix=".copy-", dir=str(copy_root))
    )
    try:
        shutil.copytree(
            source_dir,
            temp_dir,
            dirs_exist_ok=True,
            copy_function=shutil.copyfile,
        )
        copied = application_from_path(
            str(temp_dir / source_exe.name),
            platform_name="win32",
        )
        if not copied:
            raise ValueError("复制后的应用结构不完整。")
        write_json(
            temp_dir / "codex-wallpaper-copy.json",
            {
                "sourceAppPath": application["executable"],
                "sourceAsar": application.get("asar"),
            },
        )
        if target_dir.exists():
            shutil.rmtree(target_dir)
        os.replace(temp_dir, target_dir)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    copied = application_from_path(str(target_exe), platform_name="win32")
    if not copied:
        raise ValueError("自动副本创建后无法识别。")
    return copied, "Created writable app copy: %s" % target_dir


def prepare_windows_target(application):
    if not (
        is_windows()
        and application
        and application.get("canApply", True) is False
    ):
        return application, None
    if not application.get("copyable"):
        raise ValueError(
            application.get("patchabilityError")
            or "当前安装受系统保护，无法修改应用资源。"
        )
    return writable_application_copy(application)


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
    state = read_json(STATE_FILE, {})
    applications = detect_applications()
    selected = selected_application(state=state, applications=applications)
    applications = applications_with_selected(applications, selected)
    arguments = []
    if selected:
        arguments.extend(["--app", selected["executable"]])
    arguments.append("--status")
    saved_path = state.get("appPath")
    if saved_path and selected is None:
        return_code = 1
        output = (
            "已保存的目标应用路径无效，请重新选择 ChatGPT.exe 或 Codex.exe。"
        )
    else:
        return_code, output = run_patcher(arguments)
    return {
        "ok": return_code == 0,
        "status": output,
        "config": state.get("config"),
        "imageName": state.get("imageName"),
        "hasImage": current_image_path() is not None,
        "defaultImageUrl": "/assets/default-wallpaper.jpg"
        if is_windows()
        else "/assets/default-wallpaper.png",
        "platform": platform_name(),
        "applications": applications,
        "selectedApp": selected,
        "canApply": application_can_apply(selected),
        "canChooseApp": True,
    }


def validate_app_path(app_path, platform_name=None):
    return application_from_path(app_path, platform_name=platform_name)


def selected_application(state=None, applications=None):
    state = read_json(STATE_FILE, {}) if state is None else state
    applications = (
        detect_applications() if applications is None else applications
    )
    selected_path = state.get("appPath")
    if selected_path:
        selected = validate_app_path(selected_path)
        if selected:
            if application_can_apply(selected):
                return selected
            return next(
                (
                    app
                    for app in applications
                    if application_can_apply(app)
                ),
                selected,
            )
        return None
    override = os.environ.get("CODEX_APP_PATH")
    if override:
        selected = validate_app_path(override)
        if selected:
            return selected
    return next(
        (
            app
            for app in applications
            if application_can_apply(app)
        ),
        applications[0] if applications else None,
    )


def applications_with_selected(applications, selected):
    """Keep a manually selected installation visible in the picker."""
    result = list(applications or [])
    if not selected:
        return result
    selected_key = os.path.normcase(selected["executable"])
    if not any(
        os.path.normcase(item.get("executable", "")) == selected_key
        for item in result
    ):
        result.append(selected)
    return result


def locate_app_path():
    selected = selected_application()
    return selected["executable"] if selected else None


def choose_app_path():
    if not is_windows():
        osascript = shutil.which("osascript") or "/usr/bin/osascript"
        command = (
            'POSIX path of (choose application with prompt '
            '"选择 ChatGPT.app 或 Codex.app")'
        )
        result = subprocess.run(
            [osascript, "-e", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            detail = result.stderr.strip()
            raise ValueError(detail or "没有选择应用")
        path = result.stdout.strip()
        if not path:
            raise ValueError("没有选择应用")
        return path
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise ValueError("找不到 Windows 文件选择器")
    command = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.OpenFileDialog; "
        "$dialog.Filter = 'ChatGPT 或 Codex (*.exe)|ChatGPT.exe;Codex.exe'; "
        "$dialog.Title = '选择 ChatGPT.exe 或 Codex.exe'; "
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ [Console]::Write($dialog.FileName) }"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-Command", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        detail = result.stderr.strip()
        raise ValueError(detail or "无法打开应用选择框")
    path = result.stdout.strip()
    if not path:
        raise ValueError("没有选择应用")
    return path


def select_app(handler, app_path):
    app = validate_app_path(app_path)
    if not app:
        raise ValueError(
            "应用路径无效，请选择 ChatGPT.exe 或 Codex.exe，"
            "并确认同目录存在 resources\\app.asar"
        )
    state = read_json(STATE_FILE, {})
    state["appPath"] = app["executable"]
    write_json(STATE_FILE, state)
    handler.send_json({"ok": True, "app": app, "state": status_payload()})


def app_is_running(app_path):
    if is_windows():
        executable = pathlib.Path(app_path).name
        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq %s" % executable,
                "/FO",
                "CSV",
                "/NH",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode == 0 and executable.lower() in result.stdout.lower()
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

    if is_windows():
        executable = pathlib.Path(app_path).name
        if app_is_running(app_path):
            result = subprocess.run(
                ["taskkill", "/IM", executable, "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                return False, detail or "无法自动退出目标应用。"
            output.append("%s 已关闭。" % executable)
            for _ in range(40):
                if not app_is_running(app_path):
                    break
                time.sleep(0.25)
            else:
                return False, "目标应用仍在运行，请手动退出后重新打开。"
        try:
            subprocess.Popen([app_path], cwd=str(pathlib.Path(app_path).parent))
        except OSError as exc:
            return False, str(exc)
        output.append("%s 已重新打开。" % executable)
        return True, "\n".join(output)

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
        if route == "/api/health":
            return self.send_json(
                {
                    "ok": True,
                    "service": "codex-wallpaper-panel",
                }
            )
        if route == "/styles.css":
            return self.serve_static(STATIC_ROOT / "styles.css")
        if route == "/api.js":
            return self.serve_static(STATIC_ROOT / "api.js")
        if route == "/app.js":
            return self.serve_static(STATIC_ROOT / "app.js")
        if route == "/assets/default-wallpaper.png":
            return self.serve_static(DEFAULT_IMAGE, cache_control="public, max-age=3600")
        if route == "/assets/default-wallpaper.jpg":
            return self.serve_static(DEFAULT_IMAGE, cache_control="public, max-age=3600")
        if route == "/api/current-image":
            image_path = current_image_path()
            if image_path is None:
                image_path = DEFAULT_IMAGE
            content_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
            return self.serve_static(image_path, content_type=content_type)
        if route == "/api/state":
            return self.send_json(status_payload())
        if route == "/api/apps":
            applications = detect_applications()
            selected = selected_application(applications=applications)
            return self.send_json(
                {
                    "ok": True,
                    "applications": applications_with_selected(applications, selected),
                    "selectedApp": selected,
                    "canChooseApp": True,
                }
            )
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
            if route == "/api/select-app":
                app_path = body.get("path") or choose_app_path()
                return select_app(self, app_path)
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
        target = locate_app_path()
        saved_path = read_json(STATE_FILE, {}).get("appPath")
        if is_windows() and not target:
            if saved_path:
                raise ValueError(
                    "已保存的目标应用路径无效，请重新选择 ChatGPT.exe 或 Codex.exe。"
                )
            raise ValueError(
                "没有找到可修改的 ChatGPT.exe 或 Codex.exe，请先选择应用。"
            )

        source_application = selected_application()
        selected, copy_message = prepare_windows_target(source_application)
        if selected:
            target = selected["executable"]

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
        previous_state = read_json(STATE_FILE, {})
        if target:
            state["appPath"] = target
        elif previous_state.get("appPath"):
            state["appPath"] = previous_state["appPath"]
        if (
            source_application
            and selected
            and source_application.get("executable") != selected.get("executable")
        ):
            state["sourceAppPath"] = source_application["executable"]
        elif previous_state.get("sourceAppPath"):
            state["sourceAppPath"] = previous_state["sourceAppPath"]
        write_json(STATE_FILE, state)

        arguments = ["--config", str(CONFIG_FILE)]
        if image_path is not None:
            arguments.extend(["--image", str(image_path)])
        if target:
            arguments = ["--app", target, *arguments]
        return_code, patcher_output = run_patcher(arguments)
        output_parts = [part for part in (copy_message, patcher_output) if part]
        output = "\n\n".join(output_parts)
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
        target = locate_app_path()
        saved_path = read_json(STATE_FILE, {}).get("appPath")
        if is_windows() and not target:
            if saved_path:
                raise ValueError(
                    "已保存的目标应用路径无效，请重新选择 ChatGPT.exe 或 Codex.exe。"
                )
            raise ValueError(
                "没有找到可修改的 ChatGPT.exe 或 Codex.exe，请先选择应用。"
            )

        source_application = selected_application()
        selected, copy_message = prepare_windows_target(source_application)
        if selected:
            target = selected["executable"]

        arguments = ["--restore"]
        if target:
            arguments = ["--app", target, *arguments]
        return_code, patcher_output = run_patcher(arguments)
        output_parts = [part for part in (copy_message, patcher_output) if part]
        output = "\n\n".join(output_parts)
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
