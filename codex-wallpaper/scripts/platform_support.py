"""Small cross-platform helpers shared by the panel and the patcher."""

import functools
import os
import pathlib
import shutil
import subprocess
import sys


APPLICATION_NAMES = ("ChatGPT", "Codex")
WINDOWS_APP_HINTS = ("chatgpt", "codex", "openai")
WINDOWS_SEARCH_SKIP = {
    ".git",
    "__pycache__",
    "cache",
    "caches",
    "logs",
    "node_modules",
    "temp",
    "tmp",
}


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
    roots = [
        base / name,
        base / "Programs" / name,
        base / "Programs" / "OpenAI" / name,
        base / "OpenAI" / name,
        base / "Programs" / "OpenAI",
        base / "OpenAI",
        base / "Apps" / name,
    ]

    # Installers sometimes use a product directory such as "Codex Desktop"
    # or "OpenAI/ChatGPT" instead of the executable name alone.
    for parent in (
        base,
        base / "Programs",
        base / "Programs" / "OpenAI",
        base / "OpenAI",
        base / "Apps",
    ):
        try:
            children = list(parent.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            lowered = child.name.lower()
            if any(hint in lowered for hint in WINDOWS_APP_HINTS):
                roots.append(child)

    candidates = []
    seen = set()

    def add(path):
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    for root in roots:
        if not root.is_dir():
            continue
        root_depth = len(root.parts)
        try:
            walker = os.walk(root)
        except OSError:
            continue
        for current, directories, files in walker:
            current_path = pathlib.Path(current)
            depth = len(current_path.parts) - root_depth
            if depth >= 4:
                directories[:] = []
            else:
                directories[:] = [
                    item
                    for item in directories
                    if item.lower() not in WINDOWS_SEARCH_SKIP
                ]
            exact = f"{name}.exe".lower()
            for filename in files:
                if filename.lower() == exact:
                    add(current_path / filename)
    return candidates


def _windows_profile_roots(env):
    """Return local profile roots, including profiles outside the elevated user."""
    roots = []
    user_profile = _env_value(env, "USERPROFILE")
    if user_profile:
        profile = pathlib.Path(user_profile)
        roots.extend((profile / "AppData" / "Local", profile / "AppData" / "Roaming"))

    system_drive = _env_value(env, "SystemDrive") or "C:"
    users_root = pathlib.Path(f"{system_drive}/Users")
    try:
        profiles = list(users_root.iterdir())
    except OSError:
        profiles = []
    for profile in profiles:
        if not profile.is_dir() or profile.name.lower() in {
            "all users",
            "default",
            "default user",
            "public",
        }:
            continue
        roots.extend((profile / "AppData" / "Local", profile / "AppData" / "Roaming"))
    return roots


@functools.lru_cache(maxsize=1)
def _windows_registry_candidates():
    """Read installed app paths and uninstall metadata from the registry."""
    if os.name != "nt":
        return ()
    try:
        import winreg
    except ImportError:
        return ()

    candidates = []
    app_path_keys = []
    uninstall_keys = (
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
        r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for name in APPLICATION_NAMES:
            app_path_keys.append(
                (
                    hive,
                    rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{name}.exe",
                )
            )

    for hive, subkey in app_path_keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, None)
        except OSError:
            continue
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip('"'))

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for subkey in uninstall_keys:
            try:
                parent = winreg.OpenKey(hive, subkey)
            except OSError:
                continue
            with parent:
                index = 0
                while True:
                    try:
                        child_name = winreg.EnumKey(parent, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        with winreg.OpenKey(parent, child_name) as child:
                            values = {}
                            for value_name in ("InstallLocation", "DisplayIcon"):
                                try:
                                    values[value_name], _ = winreg.QueryValueEx(
                                        child, value_name
                                    )
                                except OSError:
                                    pass
                    except OSError:
                        continue
                    install_location = values.get("InstallLocation")
                    if isinstance(install_location, str) and install_location.strip():
                        base = pathlib.Path(install_location.strip('"'))
                        candidates.extend(str(base / f"{name}.exe")
                                          for name in APPLICATION_NAMES)
                    display_icon = values.get("DisplayIcon")
                    if isinstance(display_icon, str) and display_icon.strip():
                        candidates.append(display_icon.split(",", 1)[0].strip('"'))
    return tuple(candidates)


@functools.lru_cache(maxsize=1)
def _windows_process_candidates():
    """Return executable paths for running ChatGPT/Codex processes."""
    if os.name != "nt":
        return ()
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        return ()
    command = (
        "Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | "
        "ForEach-Object { $_.Path }"
    )
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if result.returncode != 0:
        return ()
    return tuple(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    )


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
    patchability_error = None
    if is_windows(platform_name):
        patchability_error = windows_installation_issue(
            str(executable), platform_name
        )
    copyable = bool(
        patchability_error
        and (
            "Microsoft Store" in patchability_error
            or "MSIX" in patchability_error
        )
    )
    return {
        "name": matched,
        "executable": str(executable if is_windows(platform_name) else path),
        "asar": str(asar),
        "canApply": patchability_error is None,
        "copyable": copyable,
        "patchabilityError": patchability_error,
    }


def detect_applications(platform_name=None, env=None):
    """Find editable ChatGPT/Codex installs in common locations."""
    if not is_windows(platform_name):
        env = os.environ if env is None else env
        candidates = []
        home = _env_value(env, "HOME")
        if home:
            candidates.extend(
                pathlib.Path(home) / "Applications" / f"{name}.app"
                for name in APPLICATION_NAMES
            )
        candidates.extend(
            pathlib.Path("/Applications") / f"{name}.app"
            for name in APPLICATION_NAMES
        )
        results = []
        seen = set()
        for path in candidates:
            key = os.path.normcase(str(path))
            if key in seen:
                continue
            seen.add(key)
            item = application_from_path(str(path), platform_name)
            if item:
                results.append(item)
        return results

    env = os.environ if env is None else env
    roots = []
    for key in (
        "LOCALAPPDATA",
        "APPDATA",
        "USERPROFILE",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "ProgramW6432",
    ):
        value = _env_value(env, key)
        if value:
            roots.append(pathlib.Path(value))
    roots.extend(_windows_profile_roots(env))

    results = []
    seen = set()
    roots_seen = set()
    unique_roots = []
    for root in roots:
        key = os.path.normcase(str(root))
        if key in roots_seen:
            continue
        roots_seen.add(key)
        unique_roots.append(root)

    for name in APPLICATION_NAMES:
        candidates = []
        for root in unique_roots:
            candidates.extend(_windows_candidate_paths(root, name))

        found = False
        for executable in candidates:
            item = application_from_path(str(executable), platform_name)
            if not item:
                continue
            key = os.path.normcase(item["executable"])
            if key not in seen:
                results.append(item)
                seen.add(key)
            found = True

        if found:
            continue
        fallback = (
            *_windows_registry_candidates(),
            *_windows_process_candidates(),
        )
        for executable in fallback:
            item = application_from_path(str(executable), platform_name)
            if not item:
                continue
            key = os.path.normcase(item["executable"])
            if key not in seen:
                results.append(item)
                seen.add(key)
    return results


def windows_installation_issue(exe_path, platform_name=None):
    """Return a protection reason for unsupported Windows installs."""
    if not is_windows(platform_name):
        return None
    path = pathlib.Path(exe_path).expanduser()
    if path.suffix.lower() != ".exe" or not path.is_file():
        return "目标必须是实际存在的 ChatGPT.exe 或 Codex.exe 文件。"

    lowered_parts = {part.lower() for part in path.parts}
    if "windowsapps" in lowered_parts:
        return "Microsoft Store / WindowsApps 安装受系统保护，当前版本不支持修改。"

    for parent in (path.parent, *path.parents):
        if (parent / "AppxManifest.xml").is_file():
            return "检测到 Microsoft Store / MSIX 安装，当前版本不支持修改。"
    return None


def ensure_windows_patchable(exe_path):
    """Reject protected or unknown Electron Windows installations.

    This deliberately refuses to modify binaries whose Electron fuse wire
    cannot be verified. It does not change the executable or disable any
    integrity feature.
    """
    path = pathlib.Path(exe_path).expanduser()
    issue = windows_installation_issue(exe_path, "win32")
    if issue:
        raise ValueError(issue)

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
