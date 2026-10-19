# 更新日志

## v1.2.0 (2026-10-19)

### 变更

- 转换后端不再随应用安装/打包，应用只保留界面和 PDF 处理逻辑，优先调用本机 WPS / LibreOffice。
- 启动时自动检测本机后端：
  - 已安装 WPS：自动补齐 `pywpsrpc`、`xvfb` 等转换支持。
  - 已安装 LibreOffice：直接使用。
  - 两者都未安装：弹出选择框，提供「安装 WPS Office」「安装 LibreOffice」两个按钮，打开系统软件商店并复制搜索词。
- 选择本机未安装的后端时，应用仍会提示并按需安装：
  - LibreOffice：通过系统包管理器自动安装。
  - WPS：优先从系统软件源安装；软件源中没有时打开官方下载页；自动安装 `xvfb`，并尝试安装 `pywpsrpc`。
- 安装完成后可直接重启应用；所选后端会保存到用户配置，下次启动自动使用。
- 精简 Python 依赖：移除未使用的 `pypdf`、`python-docx`、`openpyxl`，减小安装体积。
- `install.sh` / `setup.sh` 不再强制安装 WPS 或 LibreOffice。
- 后端下拉框会标注“（未安装）”，避免误选。

### 说明

- WPS 不在系统软件源中时，需要从官网安装包手动安装；`pywpsrpc` 在 aarch64 上可能需要源码编译。
- 安装过程需要管理员权限，图形环境下通过 `pkexec` / `sudo` 弹出认证。

## v1.1.0 (2026-10-19)

### 新增

- 新增 WPS Office 静默转换后端（pywpsrpc），支持：
  - Word：`.doc` `.docx` `.odt` `.rtf` `.txt`
  - Excel：`.xls` `.xlsx` `.ods`
  - PowerPoint：`.ppt` `.pptx` `.odp`
- 转换后端可插拔：`auto` / `wps` / `libreoffice`，统一 `convert_to_pdf()` 接口。
- 支持 GUI「设置 → 转换后端」、工具栏下拉框、CLI `--backend` 和环境变量 `PDF_EDIT_BACKEND` 切换后端。
- `auto` 模式优先使用 WPS，不可用时自动回退 LibreOffice。

### 修复与优化

- 修复 WPS 转换时启动画面/窗口在桌面闪现：WPS 自动化进程现在固定运行在独立的 Xvfb 虚拟屏幕（实测 `DISPLAY=:99`），桌面不会出现任何 WPS 窗口。
- 修复转换超时或异常后可能残留 WPS 自动化进程：worker 记录 RPC 进程 PID，超时/结束自动清理。
- 转换输出同名 PDF 时自动追加 `_1`、`_2` 后缀，避免覆盖已有文件。
- 优化 WPS 转换的错误信息与日志输出。

### 安装

- `install.sh` 改为后端感知：
  - 检测到 WPS + pywpsrpc：只安装 `xvfb`，不再强制安装 LibreOffice。
  - 未检测到 WPS：自动安装 LibreOffice 作为后备。
- 自动创建 `/usr/local/bin/pdf-editor`、开始菜单项，并注册到 PDF 的“打开方式”。
- `setup.sh` 同步支持 WPS / LibreOffice 后端检测。
- 新增 `requirements-wps.txt`，更新中英文 README。

### 升级说明

- 已安装旧版本：重新执行 `./install.sh` 即可，配置和文件不会被删除。
- aarch64（如银河麒麟 V10）没有 pywpsrpc 官方 wheel，需要从源码编译：
  `pip3 install pywpsrpc --no-binary :all:`
- 本版本已在麒麟 V10 SP1 aarch64 + WPS Office 12.1.2 + pywpsrpc 2.3.9 上实测：
  docx / xlsx / pptx 均可正常转换，转换期间桌面无 WPS 窗口闪现，结束后无残留进程。

### 已知限制

- WPS 后端需要本机安装 WPS Office；无图形会话时依赖 `xvfb-run`。
- LibreOffice 后端需要 `soffice`。
