# Codex Wallpaper 1.1.7

本版本修复当前 Windows Microsoft Store 版 ChatGPT 无法通过控制面板应用背景的问题，
并增加了真实 Store 应用安装、复制、补丁和启动的 Windows 冒烟测试。

## 下载哪个文件

- macOS：`codex-wallpaper-1.1.7-macos.zip`
- Windows：`codex-wallpaper-1.1.7-windows.zip`

每个平台包都有同名的 `.sha256` 校验文件。不要下载 GitHub 自动生成的
`Source code (zip)` 或 `Source code (tar.gz)`，它们不是安装包。

## Windows 使用

1. 解压 `codex-wallpaper-1.1.7-windows.zip`。
2. 安装 Python 3。
3. 双击 `codex-wallpaper/open-control-panel.bat`。
4. 允许 UAC 管理员权限。

控制面板会自动检测 ChatGPT 和 Codex。如果只检测到 Microsoft Store / WindowsApps
版本，点击“应用背景”时会自动复制到
`%LOCALAPPDATA%\codex-wallpaper\writable-apps`，再修改副本。副本内会保存标记文件，
之后每次调整参数、重新应用和恢复都会继续使用同一个副本。原始 Store 安装不会被修改。

为了让重新打包后的可写副本能够启动，控制面板只会在这个副本中关闭 Electron 的
ASAR 完整性校验。原始 Store 安装、Windows Defender 和其他系统安全设置均不会修改。

## macOS 使用

1. 解压 `codex-wallpaper-1.1.7-macos.zip`。
2. 双击 `codex-wallpaper/open-control-panel.command`。
3. 按面板提示授权。

## 主要更新

- 识别 Store 包声明的 `app\ChatGPT Classic.exe`。
- 支持当前 Store 版本使用的 `/.vite/renderer/` ASAR 布局。
- 仅对控制面板创建的可写副本关闭 Electron ASAR 完整性校验，原始安装不改动。
- 保持副本复用、参数重新应用和恢复链路，后续修改不再重复创建副本。
- Windows CI 使用真实 Microsoft Store 应用执行完整冒烟测试。
- 普通桌面版和 Store 版同时存在时，仍优先使用普通桌面版。

## 已知限制

- 需要 Python 3。
- Microsoft Store 副本仍然依赖 Windows 允许它以独立副本方式启动；如果系统拒绝启动，
  控制面板会显示实际错误。
- 副本首次运行可能需要重新登录；Store 版升级后需要重新创建副本。
