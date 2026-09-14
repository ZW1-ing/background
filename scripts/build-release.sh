#!/bin/zsh
# Builds a release archive for the codex-wallpaper skill.
#
#   ./scripts/build-release.sh 1.0.0
#
# Produces dist/codex-wallpaper-<version>.zip plus a matching .sha256 file.
# The zip contains a single top-level codex-wallpaper/ folder, so users can
# unzip it straight into ~/.codex/skills/.
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

NAME="codex-wallpaper-${VERSION}"
ARCHIVE="$DIST_DIR/${NAME}.zip"

print "正在校验技能内容…"
python3 -m unittest discover -s "$SKILL_DIR/tests" >/dev/null
print "  测试通过"

python3 -m py_compile "$SKILL_DIR/panel/server.py" \
  "$SKILL_DIR/scripts/codex_theme_patcher.py"
print "  Python 语法检查通过"

zsh -n "$SKILL_DIR/open-control-panel.command"
print "  启动脚本语法检查通过"

# Build from a clean staging copy so stray local files never leak into a release.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

/usr/bin/rsync -a \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "$SKILL_DIR" "$STAGE/"

chmod +x "$STAGE/codex-wallpaper/open-control-panel.command"

mkdir -p "$DIST_DIR"
rm -f "$ARCHIVE" "${ARCHIVE}.sha256"

print "正在打包 ${NAME}.zip …"
(cd "$STAGE" && zip -qr "$ARCHIVE" codex-wallpaper)

(cd "$DIST_DIR" && shasum -a 256 "${NAME}.zip" > "${NAME}.zip.sha256")

SIZE="$(du -h "$ARCHIVE" | cut -f1 | tr -d ' ')"
DIGEST="$(cut -d' ' -f1 < "${ARCHIVE}.sha256")"

print ""
print "完成。"
print "  文件:   $ARCHIVE"
print "  体积:   $SIZE"
print "  sha256: $DIGEST"
print ""
print "发布到 GitHub:"
print "  gh release create v${VERSION} \\"
print "    \"$ARCHIVE\" \"${ARCHIVE}.sha256\" \\"
print "    --title \"v${VERSION}\" --notes-file CHANGELOG.md"
