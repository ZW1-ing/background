#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codex / ChatGPT Desktop - Permanent Background Wallpaper Patcher (macOS)

Rewrites the app's app.asar in place: the wallpaper is embedded once in each
webview HTML shell and referenced from CSS through a custom property. No Node,
no network, no temporary unpacking of the whole archive.

Examples:
    sudo python3 codex_theme_patcher.py                  # bundled default wallpaper
    sudo python3 codex_theme_patcher.py -i ~/pic.png     # your own image
    sudo python3 codex_theme_patcher.py -o 0.25          # lighter main-panel tint
    python3 codex_theme_patcher.py --status              # show current state
    sudo python3 codex_theme_patcher.py --restore        # official appearance
"""

import argparse
import base64
import dataclasses
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGE = os.path.normpath(
    os.path.join(HERE, os.pardir, "assets", "default-wallpaper.png")
)

START = b"/* >>> CODEX-WALLPAPER START (auto-generated) >>> */"
END = b"/* <<< CODEX-WALLPAPER END <<< */"
STYLE_OPEN = b'<style id="codex-wallpaper">'
STYLE_CLOSE = b"</style>"
BACKGROUND_LAYER_ID = b'id="codex-wallpaper-background"'
BACKGROUND_LAYER = (
    b'<div id="codex-wallpaper-background" aria-hidden="true"></div>'
)

# Payload written by the older, much larger version of this skill.
LEGACY_MARKER = "纯净高清背景".encode("utf-8")

MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

MAX_EMBEDDED_IMAGE_BYTES = 1100 * 1024
IMAGE_OPTIMIZATION_STEPS = (
    (2560, 82),
    (1920, 72),
    (1600, 64),
    (1280, 58),
)

DEFAULT_CONFIG = {
    "background": {
        "zoom": 1.0,
        "position_x": 0.5,
        "position_y": 0.5,
        "dim": 0.0,
        "blur": 0.0,
    },
    "surfaces": {
        "main": 0.35,
        "sidebar": 0.45,
        "composer": 0.45,
        "dialog": 0.60,
    },
}

ASAR_HEAD = struct.Struct("<IIII")
DEFAULT_BLOCK_SIZE = 4 * 1024 * 1024
COPY_CHUNK = 8 * 1024 * 1024
SCAN_CHUNK = 8 * 1024 * 1024
SCAN_OVERLAP = 4096


@dataclasses.dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime: str
    temp_path: str = None
    original_size: int = 0

    def cleanup(self):
        if self.temp_path and os.path.exists(self.temp_path):
            os.remove(self.temp_path)


def human(n):
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "%d B" % n if unit == "B" else "%.1f %s" % (value, unit)
        value /= 1024.0


def prepare_image_for_embedding(image_path):
    with open(image_path, "rb") as handle:
        raw = handle.read()
    original_size = len(raw)
    mime = MIME_MAP.get(os.path.splitext(image_path)[1].lower(), "image/png")
    if original_size <= MAX_EMBEDDED_IMAGE_BYTES:
        return PreparedImage(raw, mime, original_size=original_size)

    sips = shutil.which("sips")
    if not sips:
        raise RuntimeError(
            "Image is too large for Chromium's CSS parser and sips is unavailable."
        )

    for max_dimension, quality in IMAGE_OPTIMIZATION_STEPS:
        fd, temp_path = tempfile.mkstemp(
            prefix=".codex-wallpaper-", suffix=".jpg"
        )
        os.close(fd)
        result = subprocess.run(
            [
                sips,
                "-Z",
                str(max_dimension),
                "-s",
                "format",
                "jpeg",
                "-s",
                "formatOptions",
                str(quality),
                image_path,
                "--out",
                temp_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            with open(temp_path, "rb") as handle:
                optimized = handle.read()
            if len(optimized) <= MAX_EMBEDDED_IMAGE_BYTES:
                return PreparedImage(
                    optimized,
                    "image/jpeg",
                    temp_path=temp_path,
                    original_size=original_size,
                )
        os.remove(temp_path)

    raise RuntimeError("Could not compress the image to a safe CSS size.")


def clamp(value, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def normalize_config(raw):
    """Return a validated wallpaper config with stable numeric keys."""
    raw = raw if isinstance(raw, dict) else {}
    raw_background = raw.get("background")
    if not isinstance(raw_background, dict):
        raw_background = {}
    raw_surfaces = raw.get("surfaces")
    if not isinstance(raw_surfaces, dict):
        raw_surfaces = {}

    return {
        "background": {
            "zoom": clamp(
                raw_background.get("zoom", DEFAULT_CONFIG["background"]["zoom"]),
                1.0,
                1.5,
            ),
            "position_x": clamp(
                raw_background.get(
                    "position_x", DEFAULT_CONFIG["background"]["position_x"]
                ),
                0.0,
                1.0,
            ),
            "position_y": clamp(
                raw_background.get(
                    "position_y", DEFAULT_CONFIG["background"]["position_y"]
                ),
                0.0,
                1.0,
            ),
            "dim": clamp(
                raw_background.get("dim", DEFAULT_CONFIG["background"]["dim"]),
                0.0,
                0.8,
            ),
            "blur": clamp(
                raw_background.get("blur", DEFAULT_CONFIG["background"]["blur"]),
                0.0,
                30.0,
            ),
        },
        "surfaces": {
            "main": clamp(
                raw_surfaces.get("main", DEFAULT_CONFIG["surfaces"]["main"]),
                0.0,
                1.0,
            ),
            "sidebar": clamp(
                raw_surfaces.get("sidebar", DEFAULT_CONFIG["surfaces"]["sidebar"]),
                0.0,
                1.0,
            ),
            "composer": clamp(
                raw_surfaces.get("composer", DEFAULT_CONFIG["surfaces"]["composer"]),
                0.0,
                1.0,
            ),
            "dialog": clamp(
                raw_surfaces.get("dialog", DEFAULT_CONFIG["surfaces"]["dialog"]),
                0.0,
                1.0,
            ),
        },
    }


def load_config(path=None):
    if not path:
        return normalize_config({})
    with open(path, "r", encoding="utf-8") as handle:
        return normalize_config(json.load(handle))


def locate_app():
    override = os.environ.get("CODEX_APP_PATH")
    if override:
        return override if os.path.exists(override) else None
    for candidate in ("/Applications/Codex.app", "/Applications/ChatGPT.app"):
        if os.path.exists(candidate):
            return candidate
    if os.path.isdir("/Applications"):
        for name in sorted(os.listdir("/Applications")):
            low = name.lower()
            if name.endswith(".app") and ("codex" in low or "chatgpt" in low):
                return os.path.join("/Applications", name)
    return None


# --------------------------------------------------------------------------
# asar reading / writing
#
# Layout: [uint32 4][uint32 headerBufLen][uint32 payloadLen][uint32 jsonLen]
#         [json][zero pad to 4]  then every packed file back to back with no
#         padding, offsets relative to the end of the header block.
# --------------------------------------------------------------------------


def read_header(asar_path):
    with open(asar_path, "rb") as f:
        raw = f.read(16)
        if len(raw) < 16:
            raise ValueError("not an asar archive: %s" % asar_path)
        _, hdr_size, _, json_len = ASAR_HEAD.unpack(raw)
        base = 8 + hdr_size
        data = f.read(json_len)
    return base, json.loads(data.decode("utf-8"))


def walk_entries(header):
    """Yield (archive_path, node) for every leaf entry, in header order."""
    out = []

    def walk(node, prefix):
        children = node.get("files")
        if children is not None:
            for name, child in children.items():
                walk(child, prefix + "/" + name)
        else:
            out.append((prefix, node))

    walk(header, "")
    return out


def packed_entries(header):
    entries = []
    for path, node in walk_entries(header):
        if node.get("unpacked") or "link" in node or "offset" not in node:
            continue
        entries.append((int(node["offset"]), path, node))
    entries.sort(key=lambda item: item[0])
    return entries


def compute_integrity(data, block_size):
    # An empty file still carries one block hash (of the empty string).
    span = max(len(data), 1)
    return {
        "algorithm": "SHA256",
        "hash": hashlib.sha256(data).hexdigest(),
        "blockSize": block_size,
        "blocks": [
            hashlib.sha256(data[i:i + block_size]).hexdigest()
            for i in range(0, span, block_size)
        ],
    }


def write_archive(src_path, dst_path, overrides):
    """Copy src_path to dst_path, replacing the given archive paths."""
    base, header = read_header(src_path)
    plan = []
    offset = 0
    for old_offset, path, node in packed_entries(header):
        data = overrides.get(path)
        size = len(data) if data is not None else node["size"]
        node["size"] = size
        node["offset"] = str(offset)
        if data is not None and "integrity" in node:
            node["integrity"] = compute_integrity(
                data, node["integrity"].get("blockSize", DEFAULT_BLOCK_SIZE)
            )
        plan.append((old_offset, node, data))
        offset += size

    json_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    json_len = len(json_bytes)
    pad = (-json_len) % 4
    payload_len = 4 + json_len + pad
    hdr_size = 4 + payload_len

    mode = os.stat(src_path).st_mode & 0o7777
    with open(src_path, "rb") as src, open(dst_path, "wb") as dst:
        dst.write(ASAR_HEAD.pack(4, hdr_size, payload_len, json_len))
        dst.write(json_bytes)
        dst.write(b"\0" * pad)
        for old_offset, node, data in plan:
            if data is not None:
                dst.write(data)
                continue
            remaining = node["size"]
            src.seek(base + old_offset)
            while remaining > 0:
                chunk = src.read(min(COPY_CHUNK, remaining))
                if not chunk:
                    raise IOError("unexpected end of archive while copying")
                dst.write(chunk)
                remaining -= len(chunk)
    os.chmod(dst_path, mode)
    return json_bytes


def count_markers(asar_path):
    """Return (own_marker_count, legacy_marker_count)."""
    needles = (START, LEGACY_MARKER)
    counts = [0, 0]
    tail = b""
    with open(asar_path, "rb") as f:
        while True:
            chunk = f.read(SCAN_CHUNK)
            if not chunk:
                break
            buf = tail + chunk
            for i, needle in enumerate(needles):
                pos = 0
                while True:
                    pos = buf.find(needle, pos)
                    if pos == -1:
                        break
                    counts[i] += 1
                    pos += len(needle)
            tail = buf[-SCAN_OVERLAP:]
    return counts[0], counts[1]


# --------------------------------------------------------------------------
# payload generation
# --------------------------------------------------------------------------


def strip_block(data):
    while True:
        start = data.find(START)
        if start == -1:
            return data
        end = data.find(END, start)
        if end == -1:
            return data[:start]
        data = data[:start] + data[end + len(END):]


def strip_style_tag(data):
    while True:
        start = data.find(STYLE_OPEN)
        if start == -1:
            return data
        # Eat the indentation of the injected line too, so re-patching is byte stable.
        line_start = data.rfind(b"\n", 0, start) + 1
        if not data[line_start:start].strip():
            start = line_start
        end = data.find(STYLE_CLOSE, start)
        if end == -1:
            return data[:start]
        end += len(STYLE_CLOSE)
        if data[end:end + 1] == b"\n":
            end += 1
        data = data[:start] + data[end:]


def strip_background_layer(data):
    while True:
        marker = data.find(BACKGROUND_LAYER_ID)
        if marker == -1:
            return data
        start = data.rfind(b"<div", 0, marker)
        if start == -1:
            return data
        end = data.find(b"</div>", marker)
        if end == -1:
            return data
        end += len(b"</div>")
        data = data[:start] + data[end:]


def rules_css(config, image_value):
    config = normalize_config(config)
    background = config["background"]
    surfaces = config["surfaces"]
    return (
        ":root {\n"
        "  --codex-wallpaper-zoom: %.2f;\n"
        "  --codex-wallpaper-position-x: %.0f%%;\n"
        "  --codex-wallpaper-position-y: %.0f%%;\n"
        "  --codex-wallpaper-dim: %.2f;\n"
        "  --codex-wallpaper-blur: %.1fpx;\n"
        "  --codex-wallpaper-main-opacity: %.2f;\n"
        "  --codex-wallpaper-sidebar-opacity: %.2f;\n"
        "  --codex-wallpaper-composer-opacity: %.2f;\n"
        "  --codex-wallpaper-dialog-opacity: %.2f;\n"
        "}\n"
        "html {\n"
        "  background-color: transparent !important;\n"
        "}\n"
        "body {\n"
        "  isolation: isolate;\n"
        "  background-color: transparent !important;\n"
        "}\n"
        "#codex-wallpaper-background {\n"
        "  position: fixed;\n"
        "  inset: 0;\n"
        "  z-index: 0;\n"
        "  overflow: hidden;\n"
        "  pointer-events: none;\n"
        "}\n"
        "#codex-wallpaper-background::before {\n"
        "  content: \"\";\n"
        "  position: absolute;\n"
        "  inset: calc(var(--codex-wallpaper-blur) * -2);\n"
        "  z-index: 0;\n"
        "  pointer-events: none;\n"
        "  background-image: %s !important;\n"
        "  background-size: cover !important;\n"
        "  background-position: var(--codex-wallpaper-position-x) "
        "var(--codex-wallpaper-position-y) !important;\n"
        "  background-repeat: no-repeat !important;\n"
        "  background-attachment: fixed !important;\n"
        "  filter: blur(var(--codex-wallpaper-blur)) !important;\n"
        "  transform: scale(var(--codex-wallpaper-zoom)) !important;\n"
        "  transform-origin: var(--codex-wallpaper-position-x) "
        "var(--codex-wallpaper-position-y);\n"
        "}\n"
        "#codex-wallpaper-background::after {\n"
        "  content: \"\";\n"
        "  position: absolute;\n"
        "  inset: 0;\n"
        "  z-index: 1;\n"
        "  pointer-events: none;\n"
        "  background: rgba(5, 8, 14, var(--codex-wallpaper-dim));\n"
        "}\n"
        "#root, #app, .app, [id=\"__next\"] {\n"
        "  position: relative !important;\n"
        "  z-index: 2 !important;\n"
        "  background-color: transparent !important;\n"
        "}\n"
        "main, [class*=\"_MainContentSurface_\"], "
        "[class*=\"_MainContentViewport_\"] {\n"
        "  background-color: rgba(15, 17, 26, "
        "var(--codex-wallpaper-main-opacity)) !important;\n"
        "}\n"
        "[class*=\"_LeftPanel_\"], [class*=\"_ResponsiveLeftPanel_\"] {\n"
        "  background-color: rgba(15, 17, 26, "
        "var(--codex-wallpaper-sidebar-opacity)) !important;\n"
        "}\n"
        "[class*=\"_ComposerLayoutRoot_\"] {\n"
        "  --composer-layout-surface-background: rgba(15, 17, 26, "
        "var(--codex-wallpaper-composer-opacity)) !important;\n"
        "  --composer-layout-surface-backdrop-filter: none !important;\n"
        "  background-color: rgba(15, 17, 26, "
        "var(--codex-wallpaper-composer-opacity)) !important;\n"
        "}\n"
        "[role=\"dialog\"], [role=\"menu\"], [role=\"listbox\"] {\n"
        "  background-color: rgba(15, 17, 26, "
        "var(--codex-wallpaper-dialog-opacity)) !important;\n"
        "  backdrop-filter: blur(18px) !important;\n"
        "}\n"
        % (
            background["zoom"],
            background["position_x"] * 100.0,
            background["position_y"] * 100.0,
            background["dim"],
            background["blur"],
            surfaces["main"],
            surfaces["sidebar"],
            surfaces["composer"],
            surfaces["dialog"],
            image_value,
        )
    ).encode("utf-8")


def shell_style(data_uri, config):
    """Inline <style> for an HTML shell: the image once plus the rules."""
    body = (
        ":root {\n  --codex-wallpaper-image: url('%s');\n}\n" % data_uri
    ).encode("utf-8")
    body += rules_css(config, "var(--codex-wallpaper-image)")
    return STYLE_OPEN + b"\n" + START + b"\n" + body + END + b"\n" + STYLE_CLOSE + b"\n"


def css_payload(config):
    return (
        START
        + b"\n"
        + rules_css(config, "var(--codex-wallpaper-image)")
        + END
        + b"\n"
    )


def patch_html(data, block):
    html = strip_background_layer(strip_style_tag(data))
    if b"<body" in html:
        body_end = html.find(b">", html.find(b"<body")) + 1
        html = html[:body_end] + BACKGROUND_LAYER + html[body_end:]
    else:
        html = BACKGROUND_LAYER + html
    if b"</head>" in html:
        return html.replace(b"</head>", block + b"  </head>", 1)
    return block + html


def patch_css(data, block):
    return strip_block(data).rstrip(b"\n") + b"\n\n" + block


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def ensure_backup(asar_path, bak_path):
    if os.path.exists(bak_path):
        return
    own, legacy = count_markers(asar_path)
    if own or legacy:
        print("WARNING: app.asar already carries a wallpaper patch.")
        print("         The backup will inherit it, so the archive stays large.")
        print("         Reinstall the app first if you want a clean baseline.")
    print("Creating pristine backup: %s" % os.path.basename(bak_path))
    shutil.copy2(asar_path, bak_path)


def preflight_write_access(app_path):
    """Return a description of the first unwritable spot, or None if we are fine."""
    res_dir = os.path.join(app_path, "Contents", "Resources")
    probes = (
        (res_dir, "Contents/Resources"),
        (os.path.join(app_path, "Contents"), "Contents"),
        (os.path.join(app_path, "Contents", "MacOS"), "Contents/MacOS"),
        (os.path.join(app_path, "Contents", "_CodeSignature"), "Contents/_CodeSignature"),
    )
    for path, label in probes:
        if os.path.exists(path) and not os.access(path, os.W_OK | os.X_OK):
            return label
    probe = os.path.join(res_dir, ".codex-wallpaper-write-probe")
    try:
        with open(probe, "w") as handle:
            handle.write("probe")
        os.remove(probe)
    except OSError:
        return "Contents/Resources (file creation)"
    return None


def resign(app_path):
    """Re-seal the bundle. chmod/xattr are best effort, signing must succeed."""
    print("Fixing permissions and re-signing (ad-hoc)...")
    for label, cmd in (
        ("chmod", "chmod -R 755 '%s'" % app_path),
        ("xattr", "xattr -cr '%s'" % app_path),
    ):
        res = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode != 0:
            detail = (res.stderr.strip().splitlines() or ["unknown error"])[0]
            print("  note: %s reported errors, continuing (%s)" % (label, detail))
    res = subprocess.run(
        "codesign --force --deep --sign - '%s'" % app_path,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if res.returncode != 0:
        print("codesign failed:")
        print(res.stderr.strip())
        return False
    return True


def update_plist_integrity(app_path, header_bytes):
    """Keep ElectronAsarIntegrity in step with the header we just wrote."""
    plist = os.path.join(app_path, "Contents", "Info.plist")
    if not os.path.exists(plist):
        return
    probe = subprocess.run(
        ["plutil", "-extract", "ElectronAsarIntegrity", "json", "-o", "-", plist],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if probe.returncode != 0:
        return
    try:
        entries = json.loads(probe.stdout)
    except ValueError:
        return
    targets = [k for k in entries if k.endswith("app.asar")]
    if not targets:
        return
    digest = hashlib.sha256(header_bytes).hexdigest()
    # plutil splits key paths on ".", so dots inside the key need escaping.
    key = "ElectronAsarIntegrity." + targets[0].replace(".", "\\.") + ".hash"
    res = subprocess.run(
        ["plutil", "-replace", key, "-string", digest, plist],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if res.returncode == 0:
        check = subprocess.run(
            ["plutil", "-extract", key, "raw", "-o", "-", plist],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if check.stdout.strip() == digest:
            print("Updated ElectronAsarIntegrity hash in Info.plist.")
        else:
            print("Note: ElectronAsarIntegrity write did not verify (not fatal).")
    else:
        print("Note: could not update ElectronAsarIntegrity (not fatal).")


def apply_wallpaper(app_path, image_path, config):
    res_dir = os.path.join(app_path, "Contents", "Resources")
    asar_path = os.path.join(res_dir, "app.asar")
    bak_path = asar_path + ".bak"

    if not os.path.exists(asar_path):
        print("Core package not found: %s" % asar_path)
        sys.exit(1)

    print("App:   %s" % app_path)
    print("Image: %s" % image_path)

    blocker = preflight_write_access(app_path)
    if blocker:
        print("Cannot write to %s." % blocker)
        print("Re-run with sudo, or fix ownership of the app bundle.")
        sys.exit(1)

    ensure_backup(asar_path, bak_path)

    # Always rebuild from the pristine backup, so re-running never stacks patches.
    source = bak_path if os.path.exists(bak_path) else asar_path
    print(
        "Source archive: %s (%s)"
        % (os.path.basename(source), human(os.path.getsize(source)))
    )

    prepared = prepare_image_for_embedding(image_path)
    try:
        if prepared.temp_path:
            print(
                "Optimized image: %s -> %s"
                % (human(prepared.original_size), human(len(prepared.data)))
            )
        data_uri = "data:%s;base64,%s" % (
            prepared.mime,
            base64.b64encode(prepared.data).decode("ascii"),
        )
        print(
            "Encoded image: %s -> %s"
            % (human(len(prepared.data)), human(len(data_uri)))
        )
    finally:
        prepared.cleanup()

    _base, header = read_header(source)
    entries = packed_entries(header)
    by_path = {path: node for _off, path, node in entries}

    with open(source, "rb") as f:
        def raw_file(path):
            node = by_path[path]
            f.seek(_base + int(node["offset"]))
            return f.read(node["size"])

        overrides = {}

        shells = sorted(
            p for p in by_path
            if p.startswith("/webview/") and p.endswith(".html")
        )
        if not shells:
            print("No webview HTML shell found in the archive.")
            sys.exit(1)
        config = normalize_config(config)
        block = shell_style(data_uri, config)
        for path in shells:
            overrides[path] = patch_html(raw_file(path), block)

        css_files = sorted(
            p for p in by_path
            if p.startswith("/webview/") and p.endswith(".css")
        )
        if not css_files:
            print("No webview CSS files found in the archive.")
            sys.exit(1)
        css_block = css_payload(config)
        for path in css_files:
            overrides[path] = patch_css(raw_file(path), css_block)

    print(
        "Embedded image in %d shell(s): %s"
        % (len(shells), ", ".join(p.lstrip("/") for p in shells))
    )
    print("Appended CSS rule to %d stylesheet(s)." % len(css_files))

    fd, tmp_path = tempfile.mkstemp(
        prefix=".app.asar.new-", dir=os.path.dirname(asar_path)
    )
    os.close(fd)
    try:
        print("Rewriting archive (streaming, nothing is unpacked to disk)...")
        header_bytes = write_archive(source, tmp_path, overrides)
        shutil.move(tmp_path, asar_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    update_plist_integrity(app_path, header_bytes)
    if not resign(app_path):
        print("")
        print("Re-signing failed, so the app would be left with a broken signature.")
        print("Rolling back to the pristine backup...")
        shutil.copy2(bak_path, asar_path)
        resign(app_path)
        sys.exit(1)

    print("")
    print("Done. app.asar is now %s." % human(os.path.getsize(asar_path)))
    print("Quit the app completely and reopen it to see the wallpaper.")


def restore(app_path):
    asar_path = os.path.join(app_path, "Contents", "Resources", "app.asar")
    bak_path = asar_path + ".bak"
    if not os.path.exists(bak_path):
        print("No backup found at %s - nothing to restore." % bak_path)
        print("Reinstall the official app to get back to a clean state.")
        return False
    blocker = preflight_write_access(app_path)
    if blocker:
        print("Cannot write to %s." % blocker)
        print("Re-run with sudo, or fix ownership of the app bundle.")
        return False
    print("Restoring official app.asar from backup...")
    shutil.copy2(bak_path, asar_path)
    resign(app_path)
    print("Restored. Quit and reopen the app.")
    return True


def status(app_path):
    res_dir = os.path.join(app_path, "Contents", "Resources")
    asar_path = os.path.join(res_dir, "app.asar")
    bak_path = asar_path + ".bak"
    print("App:  %s" % app_path)
    if os.path.exists(asar_path):
        own, legacy = count_markers(asar_path)
        state = "patched" if own else ("legacy patch" if legacy else "clean")
        print("asar: %s (%s)" % (human(os.path.getsize(asar_path)), state))
        if own:
            print("      %d injected block(s) detected" % own)
    else:
        print("asar: missing")
    if os.path.exists(bak_path):
        own, legacy = count_markers(bak_path)
        state = "clean" if not (own or legacy) else "already patched"
        print("bak:  %s (%s)" % (human(os.path.getsize(bak_path)), state))
    else:
        print("bak:  none (no pristine backup yet)")
    if os.path.exists(DEFAULT_IMAGE):
        print("Bundled wallpaper: %s (%s)" % (DEFAULT_IMAGE, human(os.path.getsize(DEFAULT_IMAGE))))
    else:
        print("Bundled wallpaper: missing")


def main():
    parser = argparse.ArgumentParser(
        description="Codex / ChatGPT Desktop - permanent background wallpaper patcher."
    )
    parser.add_argument(
        "-i", "--image", help="background image (defaults to the bundled wallpaper)"
    )
    parser.add_argument(
        "-o", "--opacity", type=float,
        help="main panel tint, 0.0-1.0 (default 0.35)",
    )
    parser.add_argument("--config", help="JSON config generated by the control panel")
    parser.add_argument("--restore", action="store_true", help="restore the official appearance")
    parser.add_argument("--status", action="store_true", help="show patch state and exit")
    args = parser.parse_args()

    app_path = locate_app()
    if not app_path:
        print("No Codex.app or ChatGPT.app found in /Applications.")
        print("Set CODEX_APP_PATH to point at your install.")
        sys.exit(1)

    if args.status:
        status(app_path)
        return

    if args.restore:
        restore(app_path)
        return

    if args.opacity is not None and not 0.0 <= args.opacity <= 1.0:
        print("Opacity must be between 0.0 and 1.0.")
        sys.exit(1)

    image_path = os.path.expanduser(args.image) if args.image else DEFAULT_IMAGE
    if not os.path.exists(image_path):
        print("Image not found: %s" % image_path)
        sys.exit(1)

    try:
        config = load_config(args.config)
    except (OSError, ValueError) as exc:
        print("Could not read config: %s" % exc)
        sys.exit(1)
    if args.opacity is not None:
        config["surfaces"]["main"] = args.opacity

    apply_wallpaper(app_path, image_path, config)


if __name__ == "__main__":
    main()
