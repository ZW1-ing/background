import base64
import importlib.util
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "panel_server", ROOT / "panel" / "server.py"
)
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


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

        self.assertEqual(written_config, config)
        self.assertEqual(saved_image_bytes, b"fake-png")
        self.assertEqual(calls[0][0], "--config")
        self.assertEqual(calls[0][1], str(state_root / "config.json"))
        self.assertEqual(calls[0][2], "--image")
        self.assertEqual(calls[0][3], str(saved_image))
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


if __name__ == "__main__":
    unittest.main()
