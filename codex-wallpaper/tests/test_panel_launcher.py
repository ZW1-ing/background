import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "panel_launcher", ROOT / "panel" / "launcher.py"
)
LAUNCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAUNCHER)


class PanelLauncherTests(unittest.TestCase):
    def test_panel_url_uses_loopback_and_selected_port(self):
        self.assertEqual(
            LAUNCHER.panel_url(8765),
            "http://127.0.0.1:8765/",
        )

    def test_start_detaches_server_and_waits_for_health_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root = pathlib.Path(temp)
            popen = mock.Mock()
            with mock.patch.object(
                LAUNCHER,
                "state_root",
                return_value=state_root,
            ), mock.patch.object(
                LAUNCHER,
                "is_panel_up",
                side_effect=[False, True],
            ), mock.patch.object(
                LAUNCHER.subprocess,
                "Popen",
                return_value=popen,
            ) as run, mock.patch.object(
                LAUNCHER.webbrowser,
                "open",
            ) as open_browser, mock.patch.object(
                LAUNCHER.time,
                "sleep",
            ), mock.patch(
                "builtins.open",
                mock.mock_open(),
            ):
                result = LAUNCHER.start_panel(8765, open_browser=True)

        self.assertTrue(result)
        command = run.call_args.args[0]
        self.assertIn(str(ROOT / "panel" / "server.py"), command)
        self.assertEqual(command[-1], "--no-open")
        if os.name == "nt":
            self.assertIn("creationflags", run.call_args.kwargs)
        else:
            self.assertTrue(run.call_args.kwargs["start_new_session"])
        open_browser.assert_called_once_with("http://127.0.0.1:8765/")

    def test_health_check_does_not_depend_on_application_detection(self):
        with mock.patch.object(LAUNCHER.urllib.request, "urlopen") as urlopen:
            response = mock.Mock(status=200)
            urlopen.return_value.__enter__.return_value = response

            self.assertTrue(LAUNCHER.is_panel_up(8765))

        urlopen.assert_called_once()
        self.assertIn("/api/health", urlopen.call_args.args[0].full_url)


if __name__ == "__main__":
    unittest.main()
