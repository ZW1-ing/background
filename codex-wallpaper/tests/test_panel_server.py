import base64
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import platform_support as PLATFORM

SPEC = importlib.util.spec_from_file_location(
    "panel_server", ROOT / "panel" / "server.py"
)
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class HealthEndpointTests(unittest.TestCase):
    def test_health_endpoint_is_available_without_an_installed_app(self):
        replies = []
        handler = SimpleNamespace(
            path="/api/health",
            send_json=lambda payload, status=200: replies.append((payload, status)),
        )

        SERVER.PanelHandler.do_GET(handler)

        self.assertEqual(
            replies,
            [
                (
                    {
                        "ok": True,
                        "service": "codex-wallpaper-panel",
                    },
                    200,
                )
            ],
        )

    def test_api_script_is_served_by_the_panel(self):
        replies = []
        handler = SimpleNamespace(
            path="/api.js",
            serve_static=lambda path: replies.append(path),
        )

        SERVER.PanelHandler.do_GET(handler)

        self.assertEqual(replies, [SERVER.STATIC_ROOT / "api.js"])


class DecodeDataUriTests(unittest.TestCase):
    def test_decode_png_data_uri(self):
        raw = b"fake-png"
        data_uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

        decoded = SERVER.decode_image_data_uri(data_uri)

        self.assertEqual(decoded.extension, ".png")
        self.assertEqual(decoded.data, raw)

    def test_decode_rejects_non_image_data_uri(self):
        with self.assertRaises(ValueError):
            SERVER.decode_image_data_uri("data:text/plain;base64,SGVsbG8=")


class ApplyWiringTests(unittest.TestCase):
    def test_apply_writes_exact_ui_config_and_passes_it_to_patcher(self):
        config = {
            "background": {
                "zoom": 1.22,
                "position_x": 0.18,
                "position_y": 0.74,
                "dim": 0.31,
                "blur": 9,
            },
            "surfaces": {
                "main": 0.11,
                "sidebar": 0.22,
                "composer": 0.33,
                "dialog": 0.44,
            },
        }
        image_data = "data:image/png;base64," + base64.b64encode(
            b"fake-png"
        ).decode("ascii")
        calls = []
        replies = []

        def fake_run_patcher(arguments):
            calls.append(arguments)
            return 0, "ok"

        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = pathlib.Path(temp_dir)
            (state_root / "state.json").write_text(
                json.dumps(
                    {
                        "appPath": (
                            r"C:\Users\me\AppData\Local\Programs\Codex\Codex.exe"
                        )
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(SERVER, "STATE_ROOT", state_root), mock.patch.object(
                SERVER, "STATE_FILE", state_root / "state.json"
            ), mock.patch.object(
                SERVER, "CONFIG_FILE", state_root / "config.json"
            ), mock.patch.object(
                SERVER, "run_patcher", side_effect=fake_run_patcher
            ):
                handler = SimpleNamespace(
                    send_json=lambda payload, status=200: replies.append(
                        (payload, status)
                    )
                )
                SERVER.PanelHandler.apply_wallpaper(
                    handler,
                    {
                        "imageData": image_data,
                        "imageName": "custom.png",
                        "config": config,
                    },
                )

            written_config = json.loads(
                (state_root / "config.json").read_text(encoding="utf-8")
            )
            saved_image = state_root / "current-image.png"
            saved_image_bytes = saved_image.read_bytes()
            saved_state = json.loads(
                (state_root / "state.json").read_text(encoding="utf-8")
            )

        self.assertEqual(written_config, config)
        self.assertEqual(saved_image_bytes, b"fake-png")
        config_index = calls[0].index("--config")
        self.assertEqual(calls[0][config_index + 1], str(state_root / "config.json"))
        image_index = calls[0].index("--image")
        self.assertEqual(calls[0][image_index + 1], str(saved_image))
        self.assertEqual(
            saved_state["appPath"],
            r"C:\Users\me\AppData\Local\Programs\Codex\Codex.exe",
        )
        self.assertTrue(replies[0][0]["ok"])


class RestartAppTests(unittest.TestCase):
    def test_app_is_running_matches_the_bundle_executable(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout="94462 /Applications/ChatGPT.app/Contents/MacOS/ChatGPT\n",
            stderr="",
        )
        with mock.patch.object(
            SERVER.subprocess, "run", return_value=completed
        ) as run:
            running = SERVER.app_is_running("/Applications/ChatGPT.app")

        self.assertTrue(running)
        self.assertEqual(
            run.call_args.args[0],
            ["/bin/ps", "-axo", "pid=,comm="],
        )

    def test_restart_quits_then_reopens_chatgpt(self):
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.object(
            SERVER, "locate_app_path", return_value="/Applications/ChatGPT.app"
        ), mock.patch.object(
            SERVER, "app_is_running", side_effect=[True, False]
        ), mock.patch.object(
            SERVER.subprocess, "run", return_value=completed
        ) as run:
            ok, output = SERVER.restart_app()

        self.assertTrue(ok)
        self.assertIn("已重新打开", output)
        self.assertEqual(run.call_args_list[0].args[0][0], "osascript")
        self.assertEqual(
            run.call_args_list[1].args[0], ["open", "/Applications/ChatGPT.app"]
        )


class WindowsApplicationTests(unittest.TestCase):
    def test_apply_passes_selected_windows_executable_to_patcher(self):
        config = {
            "background": {},
            "surfaces": {},
        }
        calls = []

        def fake_run_patcher(arguments):
            calls.append(arguments)
            return 0, "ok"

        selected = {
            "name": "Codex",
            "executable": r"C:\Apps\Codex\Codex.exe",
            "asar": r"C:\Apps\Codex\resources\app.asar",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = pathlib.Path(temp_dir)
            with mock.patch.object(SERVER, "STATE_ROOT", state_root), mock.patch.object(
                SERVER, "STATE_FILE", state_root / "state.json"
            ), mock.patch.object(
                SERVER, "CONFIG_FILE", state_root / "config.json"
            ), mock.patch.object(
                SERVER, "is_windows", return_value=True
            ), mock.patch.object(
                SERVER, "selected_application", return_value=selected
            ), mock.patch.object(
                SERVER, "run_patcher", side_effect=fake_run_patcher
            ):
                handler = SimpleNamespace(
                    send_json=lambda payload, status=200: setattr(
                        handler, "reply", (payload, status)
                    )
                )
                SERVER.PanelHandler.apply_wallpaper(
                    handler,
                    {
                        "imageName": "custom.png",
                        "config": config,
                    },
                )

        self.assertEqual(calls[0][:2], ["--app", selected["executable"]])

    def test_apply_rejects_unsupported_windows_target_before_patcher(self):
        selected = {
            "name": "ChatGPT",
            "executable": (
                r"C:\Program Files\WindowsApps\OpenAI.ChatGPT\ChatGPT.exe"
            ),
            "asar": (
                r"C:\Program Files\WindowsApps\OpenAI.ChatGPT\resources\app.asar"
            ),
            "canApply": False,
            "patchabilityError": (
                "Microsoft Store / WindowsApps 安装受系统保护，当前版本不支持修改。"
            ),
            "copyable": False,
        }
        replies = []
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = pathlib.Path(temp_dir)
            with mock.patch.object(SERVER, "STATE_ROOT", state_root), \
                    mock.patch.object(
                        SERVER, "STATE_FILE", state_root / "state.json"
                    ), mock.patch.object(
                        SERVER, "CONFIG_FILE", state_root / "config.json"
                    ), mock.patch.object(
                        SERVER,
                        "writable_app_copy_root",
                        return_value=state_root / "writable-apps",
                    ), mock.patch.object(
                        SERVER, "is_windows", return_value=True
                    ), mock.patch.object(
                        SERVER, "selected_application", return_value=selected
                    ), mock.patch.object(SERVER, "run_patcher") as run_patcher:
                handler = SimpleNamespace(
                    send_json=lambda payload, status=200: replies.append(
                        (payload, status)
                    )
                )
                with self.assertRaises(ValueError):
                    SERVER.PanelHandler.apply_wallpaper(
                        handler,
                        {
                            "imageName": "custom.png",
                            "config": {"background": {}, "surfaces": {}},
                        },
                    )

        run_patcher.assert_not_called()

    def test_apply_store_target_prepares_writable_copy_before_patcher(self):
        config = {"background": {}, "surfaces": {}}
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            state_root = root / "state"
            source_app = (
                root
                / "WindowsApps"
                / "OpenAI.Codex_1.0.0_x64__pkg"
                / "app"
            )
            source_exe = source_app / "ChatGPT.exe"
            source_asar = source_app / "resources" / "app.asar"
            source_asar.parent.mkdir(parents=True)
            source_exe.write_bytes(b"exe")
            source_asar.write_bytes(b"asar")
            selected = {
                "name": "ChatGPT",
                "executable": str(source_exe),
                "asar": str(source_asar),
                "canApply": False,
                "copyable": True,
                "patchabilityError": (
                    "Microsoft Store / WindowsApps 安装受系统保护，"
                    "当前版本不支持修改。"
                ),
            }

            def fake_run_patcher(arguments):
                calls.append(arguments)
                return 0, "ok"

            with mock.patch.object(SERVER, "STATE_ROOT", state_root), \
                    mock.patch.object(
                        SERVER, "STATE_FILE", state_root / "state.json"
                    ), mock.patch.object(
                        SERVER, "CONFIG_FILE", state_root / "config.json"
                    ), mock.patch.object(
                        SERVER, "is_windows", return_value=True
                    ), mock.patch.object(
                        SERVER, "locate_app_path", return_value=str(source_exe)
                    ), mock.patch.object(
                        SERVER, "selected_application", return_value=selected
                    ), mock.patch.object(
                        SERVER, "run_patcher", side_effect=fake_run_patcher
                    ):
                handler = SimpleNamespace(
                    send_json=lambda payload, status=200: setattr(
                        handler, "reply", (payload, status)
                    )
                )
                SERVER.PanelHandler.apply_wallpaper(
                    handler,
                    {
                        "imageName": "custom.png",
                        "config": config,
                    },
                )

            saved_state = json.loads(
                (state_root / "state.json").read_text(encoding="utf-8")
            )
            copy_exe = pathlib.Path(saved_state["appPath"])
            self.assertTrue(copy_exe.is_file())
            self.assertTrue(
                (copy_exe.parent / "resources" / "app.asar").is_file()
            )
            self.assertEqual(calls[0][:2], ["--app", str(copy_exe)])
            self.assertEqual(
                saved_state["sourceAppPath"],
                str(source_exe),
            )

    def test_windows_app_path_points_to_resources_asar_next_to_executable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_root = pathlib.Path(temp_dir) / "ChatGPT" / "app-1.2.3"
            executable = app_root / "ChatGPT.exe"
            asar = app_root / "resources" / "app.asar"
            executable.parent.mkdir(parents=True)
            asar.parent.mkdir()
            executable.write_bytes(b"exe")
            asar.write_bytes(b"asar")

            result = SERVER.app_package_path(
                str(executable),
                platform_name="win32",
            )

        self.assertEqual(result, str(asar))

    def test_windows_detection_finds_versioned_chatgpt_and_codex_installs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local_programs = root / "AppData" / "Local" / "Programs"
            chatgpt = local_programs / "ChatGPT" / "app-1.2.3"
            codex = local_programs / "Codex" / "app-4.5.6"
            for app_dir, name in ((chatgpt, "ChatGPT"), (codex, "Codex")):
                (app_dir / "resources").mkdir(parents=True)
                (app_dir / f"{name}.exe").write_bytes(b"exe")
                (app_dir / "resources" / "app.asar").write_bytes(b"asar")

            apps = SERVER.detect_applications(
                platform_name="win32",
                env={"LOCALAPPDATA": str(root / "AppData" / "Local")},
            )

        self.assertEqual([item["name"] for item in apps], ["ChatGPT", "Codex"])
        self.assertEqual(apps[0]["executable"], str(chatgpt / "ChatGPT.exe"))
        self.assertEqual(apps[1]["asar"], str(codex / "resources" / "app.asar"))

    def test_windows_detection_finds_openai_and_desktop_named_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            local = root / "AppData" / "Local"
            chatgpt = local / "Programs" / "OpenAI" / "ChatGPT"
            codex = local / "Codex Desktop"
            for app_dir, name in ((chatgpt, "ChatGPT"), (codex, "Codex")):
                (app_dir / "resources").mkdir(parents=True)
                (app_dir / f"{name}.exe").write_bytes(b"exe")
                (app_dir / "resources" / "app.asar").write_bytes(b"asar")

            apps = SERVER.detect_applications(
                platform_name="win32",
                env={"LOCALAPPDATA": str(local)},
            )

        self.assertEqual([item["name"] for item in apps], ["ChatGPT", "Codex"])
        self.assertEqual(apps[0]["executable"], str(chatgpt / "ChatGPT.exe"))
        self.assertEqual(apps[1]["executable"], str(codex / "Codex.exe"))

    def test_windows_detection_falls_back_to_registry_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = pathlib.Path(temp_dir) / "ChatGPT"
            executable = app_dir / "ChatGPT.exe"
            (app_dir / "resources").mkdir(parents=True)
            executable.write_bytes(b"exe")
            (app_dir / "resources" / "app.asar").write_bytes(b"asar")

            with mock.patch.object(
                PLATFORM, "_windows_registry_candidates", return_value=(str(executable),)
            ), mock.patch.object(
                PLATFORM, "_windows_process_candidates", return_value=()
            ):
                apps = SERVER.detect_applications(
                    platform_name="win32",
                    env={"LOCALAPPDATA": str(pathlib.Path(temp_dir) / "missing")},
                )

        self.assertEqual([item["name"] for item in apps], ["ChatGPT"])
        self.assertEqual(apps[0]["executable"], str(executable))

    def test_windows_detection_ignores_invalid_static_copy_before_registry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            incomplete = root / "Programs" / "ChatGPT"
            incomplete.mkdir(parents=True)
            (incomplete / "ChatGPT.exe").write_bytes(b"exe")
            valid_root = root / "Registry" / "ChatGPT"
            valid_executable = valid_root / "ChatGPT.exe"
            (valid_root / "resources").mkdir(parents=True)
            valid_executable.write_bytes(b"exe")
            (valid_root / "resources" / "app.asar").write_bytes(b"asar")

            with mock.patch.object(
                PLATFORM,
                "_windows_registry_candidates",
                return_value=(str(valid_executable),),
            ), mock.patch.object(
                PLATFORM, "_windows_process_candidates", return_value=()
            ):
                apps = SERVER.detect_applications(
                    platform_name="win32",
                    env={"LOCALAPPDATA": str(root)},
                )

        self.assertEqual([item["name"] for item in apps], ["ChatGPT"])
        self.assertEqual(apps[0]["executable"], str(valid_executable))

    def test_windows_detection_falls_back_to_running_process_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = pathlib.Path(temp_dir) / "Codex"
            executable = app_dir / "Codex.exe"
            (app_dir / "resources").mkdir(parents=True)
            executable.write_bytes(b"exe")
            (app_dir / "resources" / "app.asar").write_bytes(b"asar")

            with mock.patch.object(
                PLATFORM, "_windows_registry_candidates", return_value=()
            ), mock.patch.object(
                PLATFORM, "_windows_process_candidates", return_value=(str(executable),)
            ):
                apps = SERVER.detect_applications(
                    platform_name="win32",
                    env={"LOCALAPPDATA": str(pathlib.Path(temp_dir) / "missing")},
                )

        self.assertEqual([item["name"] for item in apps], ["Codex"])
        self.assertEqual(apps[0]["executable"], str(executable))

    def test_select_app_persists_windows_target_for_future_apply(self):
        selected = r"C:\Users\me\AppData\Local\Programs\ChatGPT\ChatGPT.exe"
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = pathlib.Path(temp_dir)
            state_file = state_root / "state.json"
            handler = SimpleNamespace(
                send_json=lambda payload, status=200: setattr(
                    handler, "reply", (payload, status)
                )
            )
            with mock.patch.object(SERVER, "STATE_ROOT", state_root), mock.patch.object(
                SERVER, "STATE_FILE", state_file
            ), mock.patch.object(
                SERVER,
                "validate_app_path",
                return_value={
                    "name": "ChatGPT",
                    "executable": selected,
                    "asar": selected.replace("ChatGPT.exe", "resources\\app.asar"),
                },
            ):
                SERVER.select_app(handler, selected)

            state = json.loads(state_file.read_text(encoding="utf-8"))

        self.assertEqual(state["appPath"], selected)
        self.assertEqual(handler.reply[0]["app"]["name"], "ChatGPT")


class MacApplicationTests(unittest.TestCase):
    def test_mac_application_picker_uses_osascript(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout="/Users/me/Applications/ChatGPT.app\n",
            stderr="",
        )
        with mock.patch.object(SERVER, "is_windows", return_value=False), \
                mock.patch.object(
                    SERVER.shutil, "which", return_value="/usr/bin/osascript"
                ), mock.patch.object(
                    SERVER.subprocess, "run", return_value=completed
                ) as run:
            selected = SERVER.choose_app_path()

        self.assertEqual(selected, "/Users/me/Applications/ChatGPT.app")
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["/usr/bin/osascript", "-e"])
        self.assertIn("choose application", command[2])

    def test_mac_state_exposes_application_picker_when_detection_is_empty(self):
        with mock.patch.object(SERVER, "is_windows", return_value=False), \
                mock.patch.object(SERVER, "detect_applications", return_value=[]), \
                mock.patch.object(SERVER, "run_patcher", return_value=(1, "no app")):
            state = SERVER.status_payload()

        self.assertTrue(state["canChooseApp"])


if __name__ == "__main__":
    unittest.main()
