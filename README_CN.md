# PDF 内嵌编辑助手

**唯一带可视化界面的开源 PDF 页面管理器** — 在任意位置插入 Word/Excel/图片，自动转换为 PDF 页面，实时预览。

> 💡 为什么要做这个：pdfarranger、pdf2pdf、qpdf 都能合并 PDF，但都没有**可视化界面**让你看到页面缩略图、拖拽排序、在指定位置插入外部文件。这个工具填补了这个空白。

## 功能特性

- 📄 **可视化页面管理** — 缩略图显示所有页面，拖拽排序
- 📝 **插入任意文件** — Word (.docx)、Excel (.xlsx)、图片 (.png/.jpg) → 自动转换为 PDF → 插入到任意位置
- 🔄 **页面操作** — 旋转、删除、移动页面
- 👁️ **实时预览** — 适应窗口 / 100% 缩放模式
- 💾 **保存** — 保存 / 另存为

## 快速开始

### 一键安装（推荐）

```bash
git clone https://github.com/L-df365/pdf-editor-assistant.git
cd pdf-editor-assistant
sudo ./install.sh
```

安装完成后：
- ✅ 开始菜单出现「PDF 内嵌编辑助手」
- ✅ 右键 PDF 文件 → 打开方式 → PDF 内嵌编辑助手
- ✅ 命令行运行 `pdf-editor 文件.pdf`

> WPS Office / LibreOffice 不随应用安装。首次在应用中选择未安装的后端时，
> 会弹出安装提示；安装完成后可立即重启应用生效。

### 卸载

```bash
sudo ./uninstall.sh
```

### 手动运行（不安装）

```bash
pip3 install -r requirements.txt
python3 main.py
```

## 与其他工具对比

| 功能 | **PDF 内嵌编辑助手** | pdfarranger | pdf2pdf | qpdf | 福昕 |
|------|:-------------------:|:-----------:|:-------:|:----:|:----:|
| 可视化界面 | ✅ | ✅ | ❌ | ❌ | ✅ |
| 插入 Word/Excel | ✅ 自动转换 | ❌ | ❌ | ❌ | ✅ |
| 插入图片 | ✅ | ✅ | ❌ | ❌ | ✅ |
| 拖拽排序 | ✅ | ✅ | ❌ | ❌ | ✅ |
| 旋转页面 | ✅ | ✅ | ❌ | ✅ | ✅ |
| 删除页面 | ✅ | ✅ | ❌ | ✅ | ✅ |
| 适应窗口预览 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 开源免费 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 安装体积 | ~120MB | ~5MB | ~1MB | ~2MB | ~200MB |

## 为什么不用福昕/WPS？

1. **隐私安全** — 文件不会离开你的电脑
2. **完全免费** — 无授权费，无订阅
3. **轻量级** — ~120MB vs 200MB+
4. **可自动化** — 可集成到工作流中
5. **可定制** — 根据需求修改

## 转换后端

文件转换后端可替换，统一接口：

```python
output_path = backend.convert_to_pdf(input_path)
```

可用后端（不随应用打包，优先调用本机已安装的程序）：

| 名称 | 说明 |
|------|------|
| `wps` | 调用本机 WPS Office（pywpsrpc），静默转换：`Visible = False`、`WithWindow = False`，并在独立的 Xvfb 虚拟屏幕中运行，启动画面和窗口不会出现在桌面上 |
| `libreoffice` | LibreOffice headless 转换 |

应用本身只包含界面和 PDF 处理逻辑，不包含 WPS/LibreOffice。启动时会
自动检测本机环境：

- 已安装 **WPS**：自动补齐 `pywpsrpc`、`xvfb` 等 WPS 转换支持。
- 已安装 **LibreOffice**：直接使用，无需额外组件。
- 两者都未安装：弹出选择框，提供「安装 WPS Office」和「安装 LibreOffice」
  两个按钮，点击后打开系统软件商店并复制搜索词，安装完成后重启应用即可。
- 在「设置 → 转换后端」中手动选择未安装的后端时，也会提示安装。

选择方式（优先级从高到低）：

1. 图形界面「设置 → 转换后端」
2. 命令行 `python3 main.py --backend wps file.pdf`
3. 环境变量 `PDF_EDIT_BACKEND=wps|libreoffice|auto`
4. 默认 `auto`：优先 WPS(pywpsrpc)，不可用时回退 LibreOffice

WPS 后端依赖本机 WPS Office 和 `pywpsrpc`。aarch64 平台没有官方 wheel，
源码编译可能较慢；应用会尝试自动安装，失败时给出提示和项目链接。
转换会自动使用独立的 Xvfb 虚拟屏幕，因此 WPS 的启动动画不会在桌面上闪现。

## 项目结构

```
pdf-editor-assistant/
├── main.py              # 程序入口
├── install.sh           # 一键安装脚本
├── uninstall.sh         # 卸载脚本
├── requirements.txt     # Python 依赖
├── requirements-wps.txt # 可选：WPS 后端依赖
├── core/
│   ├── converter.py     # 转换后端门面（可切换）
│   ├── settings.py      # 记住所选后端
│   ├── backends/        # 后端实现
│   │   ├── base.py      # 统一接口
│   │   ├── installer.py # 按需安装 WPS / LibreOffice
│   │   ├── wps.py       # WPS 静默后端
│   │   ├── wps_worker.py# WPS 独立转换进程
│   │   └── libreoffice.py
│   └── pdf_document.py  # PDF 操作（PyMuPDF）
└── gui/
    ├── main_window.py   # 主窗口
    ├── thumbnail_panel.py # 缩略图面板（拖拽）
    └── preview_panel.py # 预览面板（缩放）
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 界面 | tkinter |
| PDF 渲染 | PyMuPDF |
| 文件转换 | 本机 WPS Office (pywpsrpc) / LibreOffice headless（按需安装） |
| 图片处理 | Pillow |

## 路线图

- [ ] 批量插入多个文件
- [ ] 页面裁剪
- [ ] 水印/印章支持
- [ ] 页码编号
- [ ] PDF 合并/拆分
- [ ] 跨平台打包 (PyInstaller)
- [ ] 暗色模式

## 贡献

欢迎贡献代码！请提交 Pull Request。

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

## 致谢

- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF 渲染和操作
- [WPS Office / pywpsrpc](https://github.com/timxx/pywpsrpc) — 本机静默文档转换
- [LibreOffice](https://www.libreoffice.org/) — 备用文档转换引擎
