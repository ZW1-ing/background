# 更新日志

## 1.1.3

改进 Windows 应用检测和仓库直接运行体验。

- Windows 应用检测支持 OpenAI、Codex Desktop 等目录，并增加注册表 App Paths、
  安装信息和运行进程路径兜底。
- UAC 提权后如果当前用户目录发生变化，会继续检查其他本地用户的应用目录。
- 仓库根目录新增 macOS 和 Windows 启动代理，直接拉取仓库即可打开面板。
- macOS 面板增加应用选择器，并检测 `~/Applications` 下的桌面应用。

## 1.1.2

拆分 macOS 和 Windows 发布包。

- 不再发布同时包含两个系统启动文件的混合 ZIP。
- 新增 `codex-wallpaper-1.1.2-macos.zip`，只包含
  `open-control-panel.command`。
- 新增 `codex-wallpaper-1.1.2-windows.zip`，只包含
  `open-control-panel.bat`。
- 两个平台包分别生成 `.sha256` 校验文件。
- 发布流程增加压缩包内容检查，防止平台启动文件混入错误的包。

## 1.1.1

改进控制面板的分发和启动体验。

- 新增跨平台后台启动器，双击启动文件即可启动或复用控制面板。
- 使用独立的 `/api/health` 健康检查，不再依赖是否检测到 ChatGPT/Codex 来判断面板是否启动。
- 修复控制面板进程退出后 `127.0.0.1:8765` 书签无法访问时的恢复流程。
- 下载后不需要填写 `app.asar` 路径；只有特殊安装目录才需要手动选择应用。
- 发布包文件名包含版本号和平台范围，例如
  `codex-wallpaper-1.1.1-windows-macos.zip`，避免和源码包混淆。

## 1.1.0

增加 Windows 10/11 支持。

### Windows

- 同一套控制面板同时支持 ChatGPT 和 Codex。
- 自动扫描常见安装目录，也可以在面板里选择 `ChatGPT.exe` 或 `Codex.exe`。
- `open-control-panel.bat` 自动请求 UAC 管理员权限，固定打开
  `http://127.0.0.1:8765`。
- Windows 使用 exe 旁边的 `resources\app.asar`，备份、恢复、重复应用和失败回滚
  与 macOS 保持一致。
- 大图使用浏览器预压缩，并提供 PowerShell/.NET 压缩回退，不依赖 Node。

### 限制

- 需要 Python 3。
- 应用必须是普通桌面安装，并且存在可写的 `resources\app.asar`；受保护安装目录或
  Microsoft Store 版本可能拒绝修改。
- Windows 客户端升级后可能替换 `resources\app.asar`，需要重新应用背景。

## 1.0.0

首个公开版本。

### 功能

- 可视化控制面板：上传图片、实时预览、点击应用，固定在 `http://127.0.0.1:8765`。
- 背景参数：缩放、焦点位置、模糊、压暗。
- 透明度参数：主面板、左侧栏、输入框、弹窗。
- 应用成功后可自动重启 ChatGPT，默认开启。
- 一键恢复官方外观，从首次运行时创建的 `app.asar.bak` 还原。
- 纯 Python 3 标准库实现，无需 Node、无需联网。

### 稳定性

- 面板从终端启动后用 `nohup` 脱离会话：关掉终端窗口不影响运行，同时保留 macOS
  “App 管理”授权，否则改写 App 包会失败。
- 端口被占用时明确报错，不再静默切换到随机端口，书签地址保持稳定。
- 超过 1.1 MB 的图片会先用 `sips` 压缩再嵌入，避免 Chromium 丢弃整条 CSS 规则
  导致背景和透明度参数一起失效。
- 每次应用都从干净备份重建，注入内容带标记并在重注入前剥离，重复应用不会让
  `app.asar` 越来越大。
- 重新签名失败时自动回滚到备份，不会留下签名损坏的 App。
- 透明度改为覆盖设计令牌（`--color-surface`、`--color-surface-elevated`、
  `--app-color-background-*` 等），而不是逐个追组件类名。类名带哈希后缀、
  每次发版都会变，而这些面板的底色最终都收敛到同一组令牌上，覆盖令牌能一次
  盖住整个表面层，也不会因为版本更新而失效。
- 同时保留弹窗浮层（`_Popover_`、`_Material_`）和输入框内层卡片
  （`_expandedSurface_`、`_ComposerLayoutBody_`）的类名规则作为兜底：这些组件
  不带 `role` 属性，只匹配 `[role="dialog"]` 的旧规则命中不到，会留下白块。
