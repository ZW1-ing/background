#!/bin/zsh
# Builds a release archive for the codex-wallpaper skill.
#
#   ./scripts/build-release.sh 1.0.0
#
# Produces separate macOS and Windows archives plus matching .sha256 files.
# Each zip contains a single top-level codex-wallpaper/ folder with only the
# launcher for its target platform.
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_DIR="$REPO_ROOT/codex-wallpaper"
DIST_DIR="$REPO_ROOT/dist"

if [[ $# -lt 1 ]]; then
  print -u2 "用法: $0 <版本号>    例如: $0 1.0.0"
  exit 1
fi

VERSION="${1#v}"
if [[ ! "$VERSION" =~ '^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.]+)?$' ]]; then
  print -u2 "版本号格式无效: $VERSION (应为 1.0.0 这样的形式)"
  exit 1
fi

if [[ ! -d "$SKILL_DIR" ]]; then
  print -u2 "找不到技能目录: $SKILL_DIR"
  exit 1
fi

print "正在校验技能内容…"
python3 -m unittest discover -s "$SKILL_DIR/tests" >/dev/null
print "  测试通过"

python3 -m py_compile "$SKILL_DIR/panel/server.py" \
  "$SKILL_DIR/panel/launcher.py" \
  "$SKILL_DIR/scripts/codex_theme_patcher.py" \
  "$SKILL_DIR/scripts/platform_support.py"
print "  Python 语法检查通过"

zsh -n "$SKILL_DIR/open-control-panel.command"
print "  启动脚本语法检查通过"
[[ -f "$SKILL_DIR/open-control-panel.bat" ]] || {
  print -u2 "找不到 Windows 启动脚本: $SKILL_DIR/open-control-panel.bat"
  exit 1
}
print "  Windows 启动脚本检查通过"

# Build from clean staging copies so stray local files never leak into a release.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$DIST_DIR"

build_package() {
  local PLATFORM="$1"
  local REMOVE_LAUNCHER="$2"
  local NAME="codex-wallpaper-${VERSION}-${PLATFORM}"
  local ARCHIVE="$DIST_DIR/${NAME}.zip"
  local PACKAGE_ROOT="$STAGE/$PLATFORM"

  mkdir -p "$PACKAGE_ROOT"
  /usr/bin/rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    "$SKILL_DIR" "$PACKAGE_ROOT/"

  if [[ "$PLATFORM" == "macos" ]]; then
    chmod +x "$PACKAGE_ROOT/codex-wallpaper/open-control-panel.command"
  fi
  rm -f "$PACKAGE_ROOT/codex-wallpaper/$REMOVE_LAUNCHER"

  rm -f "$ARCHIVE" "${ARCHIVE}.sha256"
  print "正在打包 ${NAME}.zip …"
  (cd "$PACKAGE_ROOT" && zip -qr "$ARCHIVE" codex-wallpaper)
  (cd "$DIST_DIR" && shasum -a 256 "${NAME}.zip" > "${NAME}.zip.sha256")

  local SIZE="$(du -h "$ARCHIVE" | cut -f1 | tr -d ' ')"
  local DIGEST="$(cut -d' ' -f1 < "${ARCHIVE}.sha256")"

  print "  文件:   $ARCHIVE"
  print "  体积:   $SIZE"
  print "  sha256: $DIGEST"
}

build_package "macos" "open-control-panel.bat"
build_package "windows" "open-control-panel.command"

print ""
print "完成。两个平台的发布包已生成到 $DIST_DIR"
print ""
print "发布到 GitHub:"
print "  gh release create v${VERSION} \\"
print "    \"$DIST_DIR/codex-wallpaper-${VERSION}-macos.zip\" \\"
print "    \"$DIST_DIR/codex-wallpaper-${VERSION}-macos.zip.sha256\" \\"
print "    \"$DIST_DIR/codex-wallpaper-${VERSION}-windows.zip\" \\"
print "    \"$DIST_DIR/codex-wallpaper-${VERSION}-windows.zip.sha256\" \\"
print "    --title \"Codex Wallpaper ${VERSION}\" --notes-file RELEASE_NOTES.md"
