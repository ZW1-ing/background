"""Small cross-platform helpers shared by the panel and the patcher."""

import os
import pathlib
import sys


APPLICATION_NAMES = ("ChatGPT", "Codex")


def is_windows(platform_name=None):
    return (platform_name or sys.platform).lower().startswith("win")


def state_root(env=None, platform_name=None):
    env = os.environ if env is None else env
    if is_windows(platform_name):
        base = env.get("APPDATA") or str(
            pathlib.Path.home() / "AppData" / "Roaming"
        )
        return pathlib.Path(base) / "codex-wallpaper"
    return pathlib.Path.home() / ".codex-wallpaper"


def app_package_path(app_path, platform_name=None):
    """Return the app.asar path associated with an app bundle or executable."""
    path = pathlib.Path(app_path)
    if not is_windows(platform_name):
        return str(path / "Contents" / "Resources" / "app.asar")

    # A Windows Electron executable owns the resources directory beside it.
    # Walking up parent directories can accidentally select another app's
    # archive when the requested installation is incomplete.
    return str(path.parent / "resources" / "app.asar")


def _env_value(env, name):
    """Read an environment variable with Windows-compatible case folding."""
    if name in env:
        return env[name]
    wanted = name.lower()
    for key, value in env.items():
        if str(key).lower() == wanted:
            return value
    return None


def _windows_candidate_paths(base, name):
    base = pathlib.Path(base)
    roots = (
        base / name,
        base / "Programs" / name,
    )
    candidates = []
    for root in roots:
        candidates.append(root / f"{name}.exe")
        candidates.extend(root.glob(f"app-*/{name}.exe"))
    return candidates


def application_from_path(app_path, platform_name=None):
    """Validate and describe a selected app path."""
    if not app_path:
        return None
    path = pathlib.Path(app_path).expanduser()
    if is_windows(platform_name):
        if path.suffix.lower() != ".exe":
            return None
        name = path.stem
        matched = next(
            (candidate for candidate in APPLICATION_NAMES
             if name.lower() == candidate.lower()),
            None,
        )
        if matched is None:
            return None
        executable = path
    else:
        if path.suffix.lower() != ".app":
            return None
        matched = next(
            (candidate for candidate in APPLICATION_NAMES
             if path.stem.lower() == candidate.lower()),
            path.stem,
        )
        executable = path / "Contents" / "MacOS" / path.stem

    asar = pathlib.Path(app_package_path(str(path), platform_name))
    if not executable.is_file() or not asar.is_file():
        return None
    return {
        "name": matched,
        "executable": str(executable if is_windows(platform_name) else path),
        "asar": str(asar),
    }


def detect_applications(platform_name=None, env=None):
    """Find editable ChatGPT/Codex installs in common locations."""
    if not is_windows(platform_name):
        candidates = []
        for name in APPLICATION_NAMES:
            path = pathlib.Path("/Applications") / f"{name}.app"
            item = application_from_path(str(path), platform_name)
            if item:
                candidates.append(item)
        return candidates

    env = os.environ if env is None else env
    roots = []
    for key in (
        "LOCALAPPDATA",
        "APPDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "ProgramW6432",
    ):
        value = _env_value(env, key)
        if value:
            roots.append(pathlib.Path(value))

    results = []
    seen = set()
    for name in APPLICATION_NAMES:
        for root in roots:
            for executable in _windows_candidate_paths(root, name):
                item = application_from_path(str(executable), platform_name)
                if not item:
                    continue
                key = os.path.normcase(item["executable"])
                if key not in seen:
                    results.append(item)
                    seen.add(key)
    return results


def ensure_windows_patchable(exe_path):
    """Reject protected or unknown Electron Windows installations.

    This deliberately refuses to modify binaries whose Electron fuse wire
    cannot be verified. It does not change the executable or disable any
    integrity feature.
    """
    path = pathlib.Path(exe_path).expanduser()
    if path.suffix.lower() != ".exe" or not path.is_file():
        raise ValueError("目标必须是实际存在的 ChatGPT.exe 或 Codex.exe 文件。")

    lowered_parts = {part.lower() for part in path.parts}
    if "windowsapps" in lowered_parts:
        raise ValueError(
            "Microsoft Store / WindowsApps 安装受系统保护，当前版本不支持修改。"
        )

    for parent in (path.parent, *path.parents):
        if (parent / "AppxManifest.xml").is_file():
            raise ValueError(
                "检测到 Microsoft Store / MSIX 安装，当前版本不支持修改。"
            )

    sentinel = b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX"
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError("无法读取目标应用程序: %s" % exc) from exc
    marker = data.find(sentinel)
    if marker < 0:
        raise ValueError(
            "无法确认这是可修改的 Electron 桌面安装，已停止保护性操作。"
        )

    fuse = marker + len(sentinel)
    if len(data) < fuse + 2:
        raise ValueError("Electron 完整性信息不完整，已停止修改。")
    version = data[fuse]
    wire_length = data[fuse + 1]
    wire_start = fuse + 2
    wire_end = wire_start + wire_length
    if version != 1 or wire_length < 5 or len(data) < wire_end:
        raise ValueError("Electron 完整性格式暂不支持，已停止修改。")

    # FuseV1Options.EnableEmbeddedAsarIntegrityValidation is wire index 4.
    if data[wire_start + 4 : wire_start + 5] != b"0":
        raise ValueError(
            "目标应用启用了 Electron ASAR 完整性校验，当前版本不会绕过它。"
        )


def default_image_path(skill_root, platform_name=None):
    """Prefer the Windows-safe bundled image when one is present."""
    root = pathlib.Path(skill_root)
    if is_windows(platform_name):
        jpeg = root / "assets" / "default-wallpaper.jpg"
        if jpeg.exists():
            return jpeg
    return root / "assets" / "default-wallpaper.png"


def platform_name(platform=None):
    return "Windows" if is_windows(platform) else "macOS"
