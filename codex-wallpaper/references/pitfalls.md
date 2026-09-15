# Pitfalls and Troubleshooting

Causes below were confirmed against a real Codex install, not guessed.

## app.asar ballooned to gigabytes

**Symptom:** `Contents/Resources/app.asar` grows to several GB, and patching
gets slower every time.

**Cause:** two compounding mistakes in the naive approach.

1. The base64 payload was appended to *every* `*.css` file. This bundle has 219
   of them, so a 7 MB image became ~2 GB of duplicated text.
2. Each apply extracted the *already patched* `app.asar` and appended again,
   so payloads stacked with no way to remove the old ones.

**Fix:** the script embeds the image exactly once (in the HTML shells) and
references it from CSS through a custom property. It also always rebuilds from
the pristine `app.asar.bak`, and strips any marked block before injecting.

If you already have a bloated bundle, `--restore` (or just re-running the
patcher, which reads the backup) brings it back to a sane size. Delete
`app.asar.bak` and reinstall the app only if the backup itself is patched;
`--status` reports that.

## Background does not appear (white or blank area)

**Cause:** the CSS points at a `file://` path. The webview CSP is
`img-src 'self' app: blob: data: https:`, and inside `app.asar` a `file://`
URL does not satisfy `'self'`, so the image is blocked and nothing renders.

**Fix:** keep the base64 `data:` URI. Do not "optimize" it into a separate
image file next to the CSS.

## CSS variables load, but the wallpaper variable is empty

**Cause:** Chromium rejects an oversized CSS declaration. A 6.8 MB PNG becomes
about 9.1 MB as base64, and the browser discards the entire `:root` rule
instead of merely ignoring the image. Transparency variables in that same rule
disappear too.

**Fix:** keep the encoded image well below the roughly 3 MB browser limit. The
patcher automatically resizes images larger than 1.1 MB and converts them to
JPEG with `sips`. The bundled 6.8 MB wallpaper becomes about 1.0 MB after
base64 encoding.

## An injected `<link rel="stylesheet">` in index.html is ignored

**Cause:** the external stylesheet is subject to the same origin rules, and
the app's own startup styling is an inline `<style>` block. A `<style>` element
is allowed because `style-src` includes `'unsafe-inline'`.

**Fix:** inject an inline `<style>` tag, which is what the script does.

## Multi-window: popped-out panels lose the wallpaper

**Cause:** `webview/detached-window.html` is a separate document that never
loads the main window's markup.

**Fix:** the script patches every HTML shell under `webview/`, not just
`index.html`.

## App crashes or quits immediately after patching

**Cause:** modifying `app.asar` breaks the original signature, and files can
end up owned by root.

**Fix:** the script runs `chmod -R 755`, `xattr -cr`, and
`codesign --force --deep --sign -` on the bundle after repacking. To repair by
hand:

```bash
sudo chmod -R 755 /Applications/ChatGPT.app
sudo xattr -cr /Applications/ChatGPT.app
sudo codesign --force --deep --sign - /Applications/ChatGPT.app
```

## Gatekeeper blocks the app after patching

```bash
sudo xattr -rd com.apple.quarantine /Applications/ChatGPT.app
```

If it still refuses, right-click the app and choose Open once.

## "Cannot write to Contents/Resources"

The script checks write access before it changes anything, so this message
means the bundle is not owned by your user, for example when an admin installed
it. Re-run the same command with `sudo`.

On a normal drag-and-drop install the bundle belongs to you and `sudo` is not
needed, even though `app.asar` itself may be root-owned from an earlier root
run. Replacing a file needs write access to its folder, not to the file, and
re-signing only rewrites the app's own binaries and `_CodeSignature`, which are
yours.

## The app will not launch after patching

The signature is stale or missing. Re-sign it:

```bash
sudo codesign --force --deep --sign - /Applications/ChatGPT.app
```

Check the current state with `codesign --verify --verbose=2
/Applications/ChatGPT.app`. The script does this re-sign itself and rolls back
to the backup if signing fails, so a failure here usually means the bundle needs
root to sign.

## Shell errors on `!important`

**Cause:** zsh expands `!` inside double quotes as history expansion.

**Cause details:** writing CSS through `echo "..."` in a shell hits this.

**Fix:** the script writes CSS through Python file I/O, so this never comes up.
If you hand-edit CSS in a shell, run `set +H` first.

## Text looks grey or panels turn black

**Cause:** layering several translucent surfaces with `backdrop-filter`, or
slapping the image on `*`, stacks alpha until everything muddies.

**Fix:** keep one thin tint and free the skeleton layers. The script sets the
image once on `html, body`, makes `#root`, `#app`, `.app`, and `[id="__next"]`
transparent, and applies a single tint to `main`.

## No Node.js, no network

Not a problem. The script reads and writes `app.asar` with plain Python using
the archive's own layout rules, so it needs neither `@electron/asar` nor an
npm install. Only Python 3 is required.

Two layout details this relies on, both confirmed against a real bundle: file
contents are stored back to back with no padding, and offsets in the header are
JSON strings. Unchanged files are copied byte for byte; the rewrite of the
pristine archive is byte identical to the input, which is the check to run if
you ever touch that code.

## Wrong app patched, or app not found

Point the script at the bundle explicitly:

```bash
sudo CODEX_APP_PATH=/Applications/Some.app python3 codex_theme_patcher.py
```

## The wallpaper disappears after an app update

Expected. Updates ship a fresh `app.asar`. Re-run the script; the existing
`app.asar.bak` still refers to the previous version, so delete it first if you
want a clean backup of the new build:

```bash
sudo rm /Applications/ChatGPT.app/Contents/Resources/app.asar.bak
sudo python3 codex_theme_patcher.py -i ~/Pictures/wallpaper.png
```

## Checking the result quickly

```bash
python3 codex_theme_patcher.py --status
```

Reports the app path, whether `app.asar` carries a patch, whether the backup is
still pristine, and whether the bundled wallpaper is present.

## The control panel URL cannot be opened

**Cause:** `http://127.0.0.1:8765/` is a local page served by a process. The
address can remain in browser history after that process exits, but the browser
cannot start it by itself.

**Fix:** double-click `open-control-panel.command` on macOS or
`open-control-panel.bat` on Windows. The launcher uses `/api/health` to check
the service, reuses an existing healthy process, or starts a detached one and
then opens the browser. It writes startup errors to
`~/.codex-wallpaper/panel.log` on macOS or
`%APPDATA%\\codex-wallpaper\\panel.log` on Windows.
