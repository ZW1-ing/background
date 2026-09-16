# Codex Wallpaper 1.1.3

本版本扩展 macOS 和 Windows 的应用检测与启动方式。

## 下载哪个文件

- macOS：`codex-wallpaper-1.1.3-macos.zip`
- Windows：`codex-wallpaper-1.1.3-windows.zip`

每个平台包都有同名的 `.sha256` 校验文件。不要下载 GitHub 自动生成的
`Source code (zip)` 或 `Source code (tar.gz)`，它们不是安装包。

## Windows 使用

1. 解压 `codex-wallpaper-1.1.3-windows.zip`。
2. 安装 Python 3。
3. 双击 `codex-wallpaper/open-control-panel.bat`。
4. 允许 UAC 管理员权限。

控制面板会自动检测 ChatGPT 和 Codex。只有检测不到时才需要在面板里选择对应的
`ChatGPT.exe` 或 `Codex.exe`。

## macOS 使用

1. 解压 `codex-wallpaper-1.1.3-macos.zip`。
2. 双击 `codex-wallpaper/open-control-panel.command`。
3. 按面板提示授权。

## 主要更新

- macOS 和 Windows 改为两个独立下载包，每个包只包含对应系统的启动文件。
- 直接拉取 GitHub 仓库后，根目录也提供对应系统的启动文件。
- macOS 支持在面板中手动选择安装在自定义目录的 ChatGPT.app 或 Codex.app。
- Windows 自动检测扩展到注册表安装信息、运行进程，以及 OpenAI、Codex Desktop
  等常见安装目录。
- 新增发布流程检查，防止 macOS 包内混入 Windows 启动文件，或反之。
- 继续使用同一套控制面板和背景修改逻辑，两个平台功能保持一致。
- 新增跨平台后台启动器，双击启动文件即可启动或复用面板。
- 增加独立健康检查，面板服务退出后可以重新双击启动文件恢复。
- 修复 Windows 应用路径、失效目标和错误切换问题。
- 增加 Windows 受保护安装和 Electron 完整性保护检查。
