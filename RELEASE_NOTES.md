# Codex Wallpaper 1.1.4

本版本修复 Windows 应用检测和失败提示，重点处理普通安装与 Microsoft Store /
WindowsApps 安装混用的情况。

## 下载哪个文件

- macOS：`codex-wallpaper-1.1.4-macos.zip`
- Windows：`codex-wallpaper-1.1.4-windows.zip`

每个平台包都有同名的 `.sha256` 校验文件。不要下载 GitHub 自动生成的
`Source code (zip)` 或 `Source code (tar.gz)`，它们不是安装包。

## Windows 使用

1. 解压 `codex-wallpaper-1.1.4-windows.zip`。
2. 安装 Python 3。
3. 双击 `codex-wallpaper/open-control-panel.bat`。
4. 允许 UAC 管理员权限。

控制面板会自动检测 ChatGPT 和 Codex。只有检测不到时才需要在面板里选择对应的
`ChatGPT.exe` 或 `Codex.exe`。

## macOS 使用

1. 解压 `codex-wallpaper-1.1.4-macos.zip`。
2. 双击 `codex-wallpaper/open-control-panel.command`。
3. 按面板提示授权。

## 主要更新

- Windows 继续自动检测 `%LOCALAPPDATA%\Programs`、注册表安装路径和运行进程路径。
- 如果保存的目标是不可修改的 Microsoft Store / WindowsApps 安装，但检测到普通桌面版，
  面板会自动改用普通桌面版。
- 普通桌面版和 Store 版同时存在时，优先选择可修改的普通桌面版。
- 只有 Store 版时，面板会明确标记“不支持”，不再进入失败的写入流程。
- 应用失败时，“运行输出”会显示补丁脚本的完整错误，不再只显示通用提示。
- 修复新增前端脚本没有由控制面板服务提供的问题。
- 新增 Windows 受保护安装和失败输出回归测试。
