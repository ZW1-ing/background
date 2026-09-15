# Codex Wallpaper 1.1.1

本版本新增 Windows 10/11 支持，并改进控制面板的后台启动方式。

## 下载哪个文件

- 最终使用包：`codex-wallpaper-1.1.1-windows-macos.zip`
- 校验文件：`codex-wallpaper-1.1.1-windows-macos.zip.sha256`

这个压缩包同时支持 Windows 和 macOS，不需要下载 GitHub 自动生成的
`Source code (zip)` 或 `Source code (tar.gz)`。

## Windows 使用

1. 解压 `codex-wallpaper-1.1.1-windows-macos.zip`。
2. 安装 Python 3。
3. 双击 `codex-wallpaper/open-control-panel.bat`。
4. 允许 UAC 管理员权限。

控制面板会自动检测 ChatGPT 和 Codex。只有检测不到时才需要在面板里选择对应的
`ChatGPT.exe` 或 `Codex.exe`。

## macOS 使用

1. 解压 `codex-wallpaper-1.1.1-windows-macos.zip`。
2. 双击 `codex-wallpaper/open-control-panel.command`。
3. 按面板提示授权。

## 主要更新

- 同一套控制面板支持 macOS 和 Windows。
- 新增跨平台后台启动器，双击启动文件即可启动或复用面板。
- 增加独立健康检查，面板服务退出后可以重新双击启动文件恢复。
- 修复 Windows 应用路径、失效目标和错误切换问题。
- 增加 Windows 受保护安装和 Electron 完整性保护检查。
