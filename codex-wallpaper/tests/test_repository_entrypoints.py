import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class RepositoryEntrypointTests(unittest.TestCase):
    def test_root_launchers_delegate_to_the_skill_launchers(self):
        mac_launcher = REPO_ROOT / "open-control-panel.command"
        windows_launcher = REPO_ROOT / "open-control-panel.bat"

        self.assertTrue(mac_launcher.is_file())
        self.assertTrue(windows_launcher.is_file())
        self.assertIn(
            "codex-wallpaper/open-control-panel.command",
            mac_launcher.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "codex-wallpaper\\open-control-panel.bat",
            windows_launcher.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
