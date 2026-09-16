# Codex Wallpaper

给 macOS 和 Windows 上的 Codex / ChatGPT 桌面客户端换一张永久背景壁纸，带一个可视化控制面板：
上传图片、拖动滑块调参数、点“应用背景”，界面就换好了。

当前发布版本：`1.1.7`

壁纸被写进 App 自身的资源包里，所以重启电脑、退出重开都还在，不依赖任何常驻插件或
DevTools 注入。

支持 macOS 和 Windows 10/11。只需要 Python 3，不需要 Node、不需要联网。

## 安装

从 [Releases](../../releases/latest) 按系统下载对应的最终使用包：

```text
macOS:   codex-wallpaper-1.1.7-macos.zip
Windows: codex-wallpaper-1.1.7-windows.zip
```

macOS 和 Windows 使用不同的独立安装包，每个包只包含当前系统的启动文件。
不要下载 GitHub 自动生成的 `Source code (zip)` 或 `Source code (tar.gz)`，那只是源码，
不是可以直接使用的发布包。

同时下载相同文件名的 `.sha256` 文件可以校验完整性。

如果只是修改背景，不需要把文件夹放进技能目录。解压后直接双击对应的启动文件：

```bash
# macOS：双击 codex-wallpaper/open-control-panel.command
# Windows：双击 codex-wallpaper\open-control-panel.bat
```

如果是直接拉取 GitHub 仓库，进入仓库根目录后即可启动：

```bash
git clone https://github.com/ZW1-ing/background.git
cd background
# macOS：双击 ./open-control-panel.command
# Windows：双击 .\open-control-panel.bat
```

仓库根目录的启动文件会自动调用 `codex-wallpaper/` 里的控制面板。不要直接双击
`panel/server.py`，也不要在浏览器里直接打开 `http://127.0.0.1:8765/`；必须先启动面板。

如果还希望在 Codex 中作为 Skill 使用，再把 `codex-wallpaper` 文件夹放进技能目录：

```bash
mkdir -p ~/.codex/skills
cp -R ~/Downloads/codex-wallpaper ~/.codex/skills/
```

Windows 会弹出 UAC 管理员授权，这是为了修改桌面客户端自己的
`resources\app.asar`。控制面板会自动检测 ChatGPT 和 Codex，不需要手动填写
`app.asar` 路径；只有特殊安装目录没有被检测到时，才需要在面板里选择对应的
`ChatGPT.exe` 或 `Codex.exe`。

## 使用

在 macOS Finder 里双击 `open-control-panel.command`，浏览器会打开控制面板：

```
http://127.0.0.1:8765
```

Windows 用户双击 `open-control-panel.bat`；macOS 用户双击
`open-control-panel.command`。启动文件会自动启动后台面板并打开浏览器，已运行时会直接
复用，不需要先运行 `server.py`。在面板里上传图片、调整参数，然后点“应用背景”。
默认勾选了“应用后自动重启目标应用”，所以点完稍等一下就能看到新背景。

如果之前保存的地址打不开，不要只刷新浏览器书签，重新双击一次对应的启动文件即可；
启动文件会自动检查并恢复控制面板服务。

面板可调的参数：

- 背景：缩放、焦点位置、模糊、压暗
- 透明度：主面板、左侧栏、输入框、弹窗

首次运行时 macOS 可能会弹窗询问“终端”要控制 ChatGPT 的权限，需要点允许，
自动重启才能生效。Windows 首次运行会弹出 UAC，需要允许控制面板以管理员身份运行。

## 为什么用双击而不是后台服务

macOS 的“App 管理”保护只允许继承了相应授权的进程改写别的 App 包。终端有这个授权，
launchd 守护进程没有。所以启动脚本刻意从终端启动，再由跨平台启动器创建独立会话：
既保住写入权限，又能在你关掉终端窗口后继续运行。

Windows 使用 `open-control-panel.bat` 请求一次 UAC 管理员权限，再由同一个启动器以独立
进程启动面板。

面板固定在 `8765` 端口，不会偷偷换端口，所以书签一直有效。

## 平台说明

macOS 默认查找 `/Applications` 和 `~/Applications` 下的 `Codex.app`、`ChatGPT.app`。
Windows 默认查找常见的用户安装目录和程序目录，同时读取注册表安装信息和正在运行的
ChatGPT/Codex 进程路径，兼容 `OpenAI\ChatGPT`、`Codex Desktop` 等目录命名。
如果同时存在普通桌面版和 Microsoft Store 版，控制面板会优先选择可修改的普通版。
如果只有 Microsoft Store / WindowsApps 版本，Windows 面板会把应用复制到
`%LOCALAPPDATA%\codex-wallpaper\writable-apps`，然后修改这个可写副本。原始系统
安装不会改动，副本首次运行时可能需要重新登录。
如果应用安装在特殊目录，面板提供“选择应用”按钮；命令行也可以设置
`CODEX_APP_PATH`。

应用必须是普通桌面安装，并且 exe 旁边存在 `resources\app.asar`。受保护目录或
Microsoft Store 版本会使用自动副本模式；如果系统仍然阻止副本启动，面板会显示具体错误，
不要通过关闭系统安全功能绕过。

## 命令行用法

不想开面板的话，直接调用补丁脚本：

```bash
SKILL=~/.codex/skills/codex-wallpaper

# macOS：应用内置壁纸
python3 $SKILL/scripts/codex_theme_patcher.py

# 应用自己的图片，并把主面板底色调淡
python3 $SKILL/scripts/codex_theme_patcher.py -i ~/Pictures/wallpaper.png -o 0.25

# 查看当前状态
python3 $SKILL/scripts/codex_theme_patcher.py --status

# 恢复官方外观
python3 $SKILL/scripts/codex_theme_patcher.py --restore
```

Windows 用户通常直接双击 `open-control-panel.bat`；如果要命令行运行：

```powershell
py -3 .\panel\launcher.py
py -3 .\scripts\codex_theme_patcher.py --app "C:\路径\ChatGPT.exe"
```

## 恢复原样

在面板里点“恢复官方外观”，或者跑 `--restore`。脚本第一次运行时会把原始的
`app.asar` 备份成 `app.asar.bak`，恢复就是从这个备份还原。

## 注意事项

- ChatGPT 客户端升级后会换掉 `app.asar`，壁纸会消失，重新应用一次即可。
- 别把面板挂到登录项或 launchd 里，那样会丢掉写入权限，点“应用”会失败。
- Windows 客户端升级后同样可能替换 `resources\app.asar`，重新应用一次即可。
- Windows 的 `open-control-panel.bat` 需要 Python 3；启动器会在缺少 Python 时直接提示。
- 常见问题和排查见 [codex-wallpaper/references/pitfalls.md](codex-wallpaper/references/pitfalls.md)。

## 开发

```bash
python3 -m unittest discover -s codex-wallpaper/tests -v
```

打发布包：

```bash
./scripts/build-release.sh 1.0.0
```

产物在 `dist/`，包含 macOS、Windows 两个 zip 和各自对应的 `sha256` 校验文件：

```text
codex-wallpaper-1.1.7-macos.zip
codex-wallpaper-1.1.7-windows.zip
```

## 许可

MIT，见 [LICENSE](LICENSE)。
