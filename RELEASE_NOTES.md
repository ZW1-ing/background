# Codex Wallpaper 1.1.5

本版本让 Windows 上只有 Microsoft Store / WindowsApps 版本的用户也能修改背景。

## 下载哪个文件

- macOS：`codex-wallpaper-1.1.5-macos.zip`
- Windows：`codex-wallpaper-1.1.5-windows.zip`

每个平台包都有同名的 `.sha256` 校验文件。不要下载 GitHub 自动生成的
`Source code (zip)` 或 `Source code (tar.gz)`，它们不是安装包。

## Windows 使用

1. 解压 `codex-wallpaper-1.1.5-windows.zip`。
2. 安装 Python 3。
3. 双击 `codex-wallpaper/open-control-panel.bat`。
4. 允许 UAC 管理员权限。

控制面板会自动检测 ChatGPT 和 Codex。如果只检测到 Microsoft Store / WindowsApps
版本，点击“应用背景”时会自动复制到
`%LOCALAPPDATA%\codex-wallpaper\writable-apps`，再修改副本。原始 Store 安装不会被修改。

## macOS 使用

1. 解压 `codex-wallpaper-1.1.5-macos.zip`。
2. 双击 `codex-wallpaper/open-control-panel.command`。
3. 按面板提示授权。

## 主要更新

- Microsoft Store / WindowsApps 版本会自动创建可写副本并修改副本。
- 原始 Store 安装不会被修改，不会关闭 Windows 安全保护，也不会绕过签名。
- 普通桌面版和 Store 版同时存在时，仍优先使用普通桌面版。
- 副本首次运行时可能需要重新登录；Store 版升级后，需要重新创建副本。
- 应用失败时，“运行输出”会显示复制或补丁脚本的完整错误。
- 新增 Store 副本准备、受保护安装和失败输出回归测试。
