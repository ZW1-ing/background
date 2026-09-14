# Codex Wallpaper

给 macOS 上的 Codex / ChatGPT 桌面客户端换一张永久背景壁纸，带一个可视化控制面板：
上传图片、拖动滑块调参数、点“应用背景”，界面就换好了。

壁纸被写进 App 自身的资源包里，所以重启电脑、退出重开都还在，不依赖任何常驻插件或
DevTools 注入。

支持 macOS。只需要系统自带的 Python 3，不需要 Node、不需要联网。

## 安装

从 [Releases](../../releases) 下载 `codex-wallpaper-<版本号>.zip` 并解压，
把 `codex-wallpaper` 文件夹放进 Codex 的技能目录：

```bash
mkdir -p ~/.codex/skills
mv ~/Downloads/codex-wallpaper ~/.codex/skills/
```

也可以直接克隆：

```bash
git clone https://github.com/<你的用户名>/codex-wallpaper.git
cp -R codex-wallpaper/codex-wallpaper ~/.codex/skills/
```

## 使用

在 Finder 里双击 `open-control-panel.command`，浏览器会打开控制面板：

```
http://127.0.0.1:8765
```

在面板里上传图片、调整参数，然后点“应用背景”。默认勾选了“应用后自动重启
ChatGPT”，所以点完稍等一下就能看到新背景。

面板可调的参数：

- 背景：缩放、焦点位置、模糊、压暗
- 透明度：主面板、左侧栏、输入框、弹窗

首次运行时 macOS 可能会弹窗询问“终端”要控制 ChatGPT 的权限，需要点允许，
自动重启才能生效。

## 为什么用双击而不是后台服务

macOS 的“App 管理”保护只允许继承了相应授权的进程改写别的 App 包。终端有这个授权，
launchd 守护进程没有。所以启动脚本刻意从终端启动，再用 `nohup` 让面板脱离会话：
既保住写入权限，又能在你关掉终端窗口后继续运行。

面板固定在 `8765` 端口，不会偷偷换端口，所以书签一直有效。

## 命令行用法

不想开面板的话，直接调用补丁脚本：

```bash
SKILL=~/.codex/skills/codex-wallpaper

# 应用内置壁纸
python3 $SKILL/scripts/codex_theme_patcher.py

# 应用自己的图片，并把主面板底色调淡
python3 $SKILL/scripts/codex_theme_patcher.py -i ~/Pictures/wallpaper.png -o 0.25

# 查看当前状态
python3 $SKILL/scripts/codex_theme_patcher.py --status

# 恢复官方外观
python3 $SKILL/scripts/codex_theme_patcher.py --restore
```

## 恢复原样

在面板里点“恢复官方外观”，或者跑 `--restore`。脚本第一次运行时会把原始的
`app.asar` 备份成 `app.asar.bak`，恢复就是从这个备份还原。

## 注意事项

- ChatGPT 客户端升级后会换掉 `app.asar`，壁纸会消失，重新应用一次即可。
- 别把面板挂到登录项或 launchd 里，那样会丢掉写入权限，点“应用”会失败。
- 常见问题和排查见 [codex-wallpaper/references/pitfalls.md](codex-wallpaper/references/pitfalls.md)。

## 开发

```bash
python3 -m unittest discover -s codex-wallpaper/tests -v
```

打发布包：

```bash
./scripts/build-release.sh 1.0.0
```

产物在 `dist/`，包含 zip 和对应的 `sha256` 校验文件。

## 许可

MIT，见 [LICENSE](LICENSE)。
