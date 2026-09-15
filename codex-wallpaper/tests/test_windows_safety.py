import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import platform_support as PLATFORM

SPEC = importlib.util.spec_from_file_location("safety_panel", ROOT / "panel/server.py")
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class WindowsSafetyTests(unittest.TestCase):
    def test_package_path_never_uses_an_unrelated_parent_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "resources").mkdir()
            (root / "resources/app.asar").write_bytes(b"another app")
            selected = root / "Other/Codex.exe"
            self.assertEqual(
                PLATFORM.app_package_path(str(selected), "win32"),
                str(root / "Other/resources/app.asar"),
            )

    def test_missing_saved_target_does_not_select_a_different_application(self):
        with mock.patch.object(SERVER, "validate_app_path", return_value=None):
            self.assertIsNone(SERVER.selected_application(
                state={"appPath": "missing.exe"},
                applications=[{"executable": "another.exe", "name": "ChatGPT"}],
            ))

    def test_status_does_not_probe_a_different_application_for_missing_saved_target(self):
        with tempfile.TemporaryDirectory() as temp:
            state_root = pathlib.Path(temp)
            (state_root / "state.json").write_text(
                '{"appPath": "missing.exe"}',
                encoding="utf-8",
            )
            detected = [
                {"name": "ChatGPT", "executable": "another.exe", "asar": "another.asar"}
            ]
            with mock.patch.object(SERVER, "STATE_ROOT", state_root), \
                    mock.patch.object(SERVER, "STATE_FILE", state_root / "state.json"), \
                    mock.patch.object(SERVER, "detect_applications", return_value=detected), \
                    mock.patch.object(SERVER, "validate_app_path", return_value=None), \
                    mock.patch.object(SERVER, "run_patcher") as run_patcher:
                state = SERVER.status_payload()

        run_patcher.assert_not_called()
        self.assertFalse(state["ok"])
        self.assertIsNone(state["selectedApp"])
        self.assertEqual(state["applications"], detected)

    def test_manual_application_is_included_in_picker_list(self):
        app = {"name": "Codex", "executable": "manual.exe", "asar": "manual.asar"}
        with mock.patch.object(SERVER, "detect_applications", return_value=[]), \
                mock.patch.object(SERVER, "selected_application", return_value=app), \
                mock.patch.object(SERVER, "run_patcher", return_value=(0, "ok")):
            state = SERVER.status_payload()
        self.assertIn(app, state["applications"])

    def test_windows_candidate_environment_names_are_case_insensitive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "Codex/resources").mkdir(parents=True)
            (root / "Codex/Codex.exe").write_bytes(b"exe")
            (root / "Codex/resources/app.asar").write_bytes(b"asar")
            apps = PLATFORM.detect_applications("win32", {"ProgramFiles": temp})
        self.assertEqual([a["name"] for a in apps], ["Codex"])

    def test_invalid_executable_extension_and_name_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "resources").mkdir()
            (root / "resources/app.asar").write_bytes(b"asar")
            for name in ("Other.exe", "Codex.cmd", "ChatGPT.exe"):
                candidate = root / name
                candidate.mkdir() if name == "ChatGPT.exe" else candidate.write_bytes(b"x")
                self.assertIsNone(PLATFORM.application_from_path(str(candidate), "win32"))

    def test_integrity_guard_rejects_protected_unknown_and_msix_before_writes(self):
        sentinel = b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX"
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            exe = root / "Codex.exe"
            for wire in (b"", sentinel + b"\x01\x06111111",
                         sentinel + b"\x02\x06111101"):
                exe.write_bytes(b"MZ" + wire)
                with self.assertRaises(ValueError):
                    PLATFORM.ensure_windows_patchable(str(exe))
            exe.write_bytes(b"MZ" + sentinel + b"\x01\x06111101")
            PLATFORM.ensure_windows_patchable(str(exe))
            (root / "AppxManifest.xml").write_text("<Package/>")
            with self.assertRaises(ValueError):
                PLATFORM.ensure_windows_patchable(str(exe))

    def test_missing_python_compression_output_is_not_accepted_as_an_image(self):
        import codex_theme_patcher as patcher
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(patcher.shutil, "which", return_value="powershell.exe"), \
                    mock.patch.object(patcher.subprocess, "run", return_value=
                                      type("Result", (), {"returncode": 0, "stderr": ""})()):
                with self.assertRaises(RuntimeError):
                    patcher.prepare_image_with_powershell(str(pathlib.Path(temp) / "x.png"), 200)


if __name__ == "__main__":
    unittest.main()
