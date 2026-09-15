import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "codex_theme_patcher", ROOT / "scripts" / "codex_theme_patcher.py"
)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


class NormalizeConfigTests(unittest.TestCase):
    def test_normalize_config_returns_defaults_for_empty_input(self):
        config = PATCHER.normalize_config({})

        self.assertEqual(config["background"]["zoom"], 1.0)
        self.assertEqual(config["background"]["position_x"], 0.5)
        self.assertEqual(config["background"]["position_y"], 0.5)
        self.assertEqual(config["background"]["dim"], 0.0)
        self.assertEqual(config["background"]["blur"], 0.0)
        self.assertEqual(config["surfaces"]["main"], 0.35)

    def test_normalize_config_clamps_out_of_range_values(self):
        config = PATCHER.normalize_config(
            {
                "background": {
                    "zoom": 9,
                    "position_x": -1,
                    "position_y": 2,
                    "dim": 4,
                    "blur": 99,
                },
                "surfaces": {
                    "main": -0.5,
                    "sidebar": 2,
                    "composer": 0.25,
                    "dialog": 0.75,
                },
            }
        )

        self.assertEqual(config["background"]["zoom"], 1.5)
        self.assertEqual(config["background"]["position_x"], 0.0)
        self.assertEqual(config["background"]["position_y"], 1.0)
        self.assertEqual(config["background"]["dim"], 0.8)
        self.assertEqual(config["background"]["blur"], 30.0)
        self.assertEqual(config["surfaces"]["main"], 0.0)
        self.assertEqual(config["surfaces"]["sidebar"], 1.0)
        self.assertEqual(config["surfaces"]["composer"], 0.25)
        self.assertEqual(config["surfaces"]["dialog"], 0.75)


class CssGenerationTests(unittest.TestCase):
    def test_rules_css_contains_background_and_surface_controls(self):
        config = PATCHER.normalize_config(
            {
                "background": {
                    "zoom": 1.2,
                    "position_x": 0.3,
                    "position_y": 0.7,
                    "dim": 0.2,
                    "blur": 6,
                },
                "surfaces": {
                    "main": 0.2,
                    "sidebar": 0.3,
                    "composer": 0.4,
                    "dialog": 0.5,
                },
            }
        )

        css = PATCHER.rules_css(
            config, "var(--codex-wallpaper-image)"
        ).decode("utf-8")

        self.assertIn("--codex-wallpaper-zoom: 1.2", css)
        self.assertIn("--codex-wallpaper-position-x: 30%", css)
        self.assertIn("--codex-wallpaper-position-y: 70%", css)
        self.assertIn("--codex-wallpaper-dim: 0.2", css)
        self.assertIn("--codex-wallpaper-blur: 6.0px", css)
        self.assertIn("--codex-wallpaper-main-opacity: 0.2", css)
        self.assertIn("--codex-wallpaper-sidebar-opacity: 0.3", css)
        self.assertIn("--codex-wallpaper-composer-opacity: 0.4", css)
        self.assertIn("--codex-wallpaper-dialog-opacity: 0.5", css)
        self.assertIn("#codex-wallpaper-background", css)
        self.assertIn("z-index: 0", css)
        self.assertIn("z-index: 1", css)
        self.assertNotIn("html::before", css)
        self.assertIn('[class*="_LeftPanel_"]', css)
        self.assertIn('[class*="_ComposerLayoutRoot_"]', css)
        self.assertIn('[role="dialog"]', css)
        # The composer's inner card and the popover shell paint their own
        # surface colours, so they need explicit selectors of their own.
        self.assertIn('[class*="_expandedSurface_"]', css)
        self.assertIn('[class*="_ComposerLayoutBody_"]', css)
        self.assertIn('[class*="_Popover_"]', css)
        # Class names are hashed per release, so the design tokens they read
        # from are the durable place to force transparency.
        self.assertIn("--color-surface:", css)
        self.assertIn("--color-surface-elevated:", css)
        self.assertIn("--app-color-background-surface:", css)
        self.assertIn("--app-color-background-elevated-primary:", css)
        self.assertIn("--app-color-background-application-menu:", css)

    def test_patch_html_injects_single_background_layer(self):
        html = b"<html><body><div id=\"root\"></div></body></html>"
        block = b"<style>rules</style>"

        once = PATCHER.patch_html(html, block)
        twice = PATCHER.patch_html(once, block)

        self.assertEqual(
            twice.count(b'id="codex-wallpaper-background"'),
            1,
        )
        self.assertIn(b'<div id="codex-wallpaper-background"', twice)
        self.assertLess(
            twice.index(b'id="codex-wallpaper-background"'),
            twice.index(b'id="root"'),
        )


class ImagePreparationTests(unittest.TestCase):
    def test_small_image_is_embedded_without_reencoding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = pathlib.Path(temp_dir) / "small.png"
            image_path.write_bytes(b"small-image")

            prepared = PATCHER.prepare_image_for_embedding(str(image_path))
            try:
                self.assertEqual(prepared.data, b"small-image")
                self.assertEqual(prepared.mime, "image/png")
                self.assertIsNone(prepared.temp_path)
            finally:
                prepared.cleanup()

    @unittest.skipUnless(
        sys.platform == "darwin",
        "the bundled-image regression check requires macOS sips",
    )
    def test_large_default_image_is_compressed_below_css_limit(self):
        prepared = PATCHER.prepare_image_for_embedding(
            str(PATCHER.DEFAULT_IMAGE)
        )
        try:
            self.assertLessEqual(
                len(prepared.data), PATCHER.MAX_EMBEDDED_IMAGE_BYTES
            )
            self.assertEqual(prepared.mime, "image/jpeg")
            self.assertIsNotNone(prepared.temp_path)
        finally:
            prepared.cleanup()


class WindowsPathTests(unittest.TestCase):
    def test_patcher_resolves_windows_executable_to_resources_asar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = pathlib.Path(temp_dir) / "app-1.2.3"
            executable = app_dir / "ChatGPT.exe"
            asar = app_dir / "resources" / "app.asar"
            executable.parent.mkdir(parents=True)
            asar.parent.mkdir()
            executable.write_bytes(b"exe")
            asar.write_bytes(b"asar")

            result = PATCHER.app_package_path(
                str(executable),
                platform_name="win32",
            )

        self.assertEqual(result, str(asar))

    def test_windows_large_image_uses_powershell_when_sips_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = pathlib.Path(temp_dir) / "large.png"
            image_path.write_bytes(b"large-image-data")
            def fake_run(command, **kwargs):
                pathlib.Path(command[-3]).write_bytes(b"small-jpeg")
                return type("Result", (), {"returncode": 0, "stderr": ""})()

            with mock.patch.object(
                PATCHER, "MAX_EMBEDDED_IMAGE_BYTES", 10
            ), mock.patch.object(
                PATCHER, "is_windows", return_value=True
            ), mock.patch.object(
                PATCHER.shutil,
                "which",
                side_effect=lambda name: (
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
                    if name == "powershell.exe"
                    else None
                ),
            ), mock.patch.object(
                PATCHER.subprocess, "run", side_effect=fake_run
            ):
                prepared = PATCHER.prepare_image_for_embedding(str(image_path))

            try:
                self.assertEqual(prepared.mime, "image/jpeg")
                self.assertEqual(prepared.data, b"small-jpeg")
            finally:
                prepared.cleanup()


if __name__ == "__main__":
    unittest.main()
