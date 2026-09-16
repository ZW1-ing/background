# Codex Wallpaper 1.1.6

本版本修复 Windows Microsoft Store / WindowsApps 自动副本在后续应用和恢复时
仍被 Electron 校验拦截的问题。

## 下载哪个文件

- macOS：`codex-wallpaper-1.1.6-macos.zip`
- Windows：`codex-wallpaper-1.1.6-windows.zip`

每个平台包都有同名的 `.sha256` 校验文件。不要下载 GitHub 自动生成的
`Source code (zip)` 或 `Source code (tar.gz)`，它们不是安装包。

## Windows 使用

1. 解压 `codex-wallpaper-1.1.6-windows.zip`。
2. 安装 Python 3。
3. 双击 `codex-wallpaper/open-control-panel.bat`。
4. 允许 UAC 管理员权限。

控制面板会自动检测 ChatGPT 和 Codex。如果只检测到 Microsoft Store / WindowsApps
版本，点击“应用背景”时会自动复制到
`%LOCALAPPDATA%\codex-wallpaper\writable-apps`，再修改副本。副本内会保存标记文件，
之后每次调整参数、重新应用和恢复都会继续使用同一个副本。原始 Store 安装不会被修改。

## macOS 使用

1. 解压 `codex-wallpaper-1.1.6-macos.zip`。
2. 双击 `codex-wallpaper/open-control-panel.command`。
3. 按面板提示授权。

## 主要更新

- 修复首次复制成功后，再次点击“应用背景”仍被 Electron 标记校验拦截的问题。
- 控制面板通过 `codex-wallpaper-copy.json` 持久识别自己创建的 Windows 可写副本。
- 后续应用、参数修改和恢复操作都会继续使用同一个副本。
- Windows 应用检测会消除同一安装的重复路径，避免选择列表出现重复项。
- 补丁输出统一使用 UTF-8，非中文代码页的 Windows 系统不会再因日志编码中断。
- 原始 Store 安装不会被修改，不会关闭 Windows 安全保护，也不会绕过签名。
- 普通桌面版和 Store 版同时存在时，仍优先使用普通桌面版。
- 副本首次运行时可能需要重新登录；Store 版升级后，需要重新创建副本。
- 应用失败时，“运行输出”会显示复制或补丁脚本的完整错误。
- 发布前增加 Windows CI 测试，覆盖副本创建、副本复用和恢复链路。

## 已知限制

- 需要 Python 3。
- Microsoft Store 副本仍然依赖 Windows 允许它以独立副本方式启动；如果系统拒绝启动，
  控制面板会显示实际错误，不会修改原始系统安装，也不会关闭系统安全保护。
