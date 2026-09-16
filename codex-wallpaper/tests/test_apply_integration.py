import base64
import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "codex_theme_patcher", ROOT / "scripts" / "codex_theme_patcher.py"
)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


def build_asar(path, entries):
    header = {"files": {}}
    offset = 0
    packed = []
    for archive_path, data in entries:
        parts = archive_path.strip("/").split("/")
        node = header
        for part in parts[:-1]:
            node = node["files"].setdefault(part, {"files": {}})
        node["files"][parts[-1]] = {
            "size": len(data),
            "offset": str(offset),
        }
        packed.append(data)
        offset += len(data)

    json_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    json_len = len(json_bytes)
    pad = (-json_len) % 4
    payload_len = 4 + json_len + pad
    header_size = 4 + payload_len
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(PATCHER.ASAR_HEAD.pack(4, header_size, payload_len, json_len))
        handle.write(json_bytes)
        handle.write(b"\0" * pad)
        for data in packed:
            handle.write(data)


def read_archive_file(path, wanted_path):
    base, header = PATCHER.read_header(path)
    with open(path, "rb") as handle:
        for _offset, archive_path, node in PATCHER.packed_entries(header):
            if archive_path == wanted_path:
                handle.seek(base + int(node["offset"]))
                return handle.read(node["size"])
    raise AssertionError("missing archive path: %s" % wanted_path)


class ApplyIntegrationTests(unittest.TestCase):
    def test_apply_embeds_uploaded_image_and_exact_control_values(self):
        image_data = b"test-image-bytes"
        config = {
            "background": {
                "zoom": 1.37,
                "position_x": 0.23,
                "position_y": 0.81,
                "dim": 0.46,
                "blur": 13,
            },
            "surfaces": {
                "main": 0.12,
                "sidebar": 0.34,
                "composer": 0.56,
                "dialog": 0.78,
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            app_path = root / "ChatGPT.app"
            resources = app_path / "Contents" / "Resources"
            asar_path = resources / "app.asar"
            image_path = root / "upload.png"
            image_path.write_bytes(image_data)
            build_asar(
                asar_path,
                [
                    (
                        "/webview/index.html",
                        b"<html><head></head><body><div id=\"root\"></div></body></html>",
                    ),
                    (
                        "/webview/assets/app.css",
                        b"body { color: black; }",
                    ),
                ],
            )

            original_resign = PATCHER.resign
            PATCHER.resign = lambda _app_path: True
            try:
                PATCHER.apply_wallpaper(str(app_path), str(image_path), config)
            finally:
                PATCHER.resign = original_resign

            html = read_archive_file(asar_path, "/webview/index.html")
            css = read_archive_file(asar_path, "/webview/assets/app.css")
            encoded = base64.b64encode(image_data).decode("ascii").encode("ascii")

            self.assertIn(PATCHER.BACKGROUND_LAYER_ID, html)
            self.assertIn(encoded, html)
            self.assertIn(b"--codex-wallpaper-zoom: 1.37", css)
            self.assertIn(b"--codex-wallpaper-position-x: 23%", css)
            self.assertIn(b"--codex-wallpaper-position-y: 81%", css)
            self.assertIn(b"--codex-wallpaper-dim: 0.46", css)
            self.assertIn(b"--codex-wallpaper-blur: 13.0px", css)
            self.assertIn(b"--codex-wallpaper-main-opacity: 0.12", css)
            self.assertIn(b"--codex-wallpaper-sidebar-opacity: 0.34", css)
            self.assertIn(b"--codex-wallpaper-composer-opacity: 0.56", css)
            self.assertIn(b"--codex-wallpaper-dialog-opacity: 0.78", css)

    def test_apply_patches_marked_windows_copy_without_electron_marker(self):
        config = {
            "background": {
                "zoom": 1.0,
                "position_x": 0.5,
                "position_y": 0.5,
                "dim": 0.0,
                "blur": 0,
            },
            "surfaces": {
                "main": 0.35,
                "sidebar": 0.45,
                "composer": 0.45,
                "dialog": 0.6,
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            copy_root = root / "writable-apps"
            app_path = copy_root / "ChatGPT-copy"
            executable = app_path / "ChatGPT.exe"
            asar_path = app_path / "resources" / "app.asar"
            image_path = root / "upload.png"
            app_path.mkdir(parents=True)
            executable.write_bytes(b"MZ synthetic Windows executable")
            image_path.write_bytes(b"test-image-bytes")
            build_asar(
                asar_path,
                [
                    (
                        "/webview/index.html",
                        b"<html><head></head><body></body></html>",
                    ),
                    (
                        "/webview/assets/app.css",
                        b"body { color: black; }",
                    ),
                ],
            )

            original_is_windows = PATCHER.is_windows
            original_package_path = PATCHER.app_package_path
            PATCHER.is_windows = lambda: True
            PATCHER.app_package_path = lambda _app_path: str(asar_path)
            try:
                PATCHER.apply_wallpaper(
                    str(executable),
                    str(image_path),
                    config,
                    allow_unknown_windows=True,
                )
            finally:
                PATCHER.is_windows = original_is_windows
                PATCHER.app_package_path = original_package_path

            html = read_archive_file(asar_path, "/webview/index.html")
            self.assertIn(PATCHER.BACKGROUND_LAYER_ID, html)


if __name__ == "__main__":
    unittest.main()
