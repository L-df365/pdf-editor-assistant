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

### 前置依赖

- Git
- Docker

> 💡 **国内用户**：如果 `git clone` 很慢，可以用镜像站：
> ```bash
> git clone https://ghfast.top/https://github.com/L-df365/pdf-editor-assistant.git
> # 或
> git clone https://mirror.ghproxy.com/https://github.com/L-df365/pdf-editor-assistant.git
> ```

### 一键安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/L-df365/pdf-editor-assistant.git
cd pdf-editor-assistant

# 运行安装脚本
sudo ./install.sh
```

安装后：
- ✅ 开始菜单出现「PDF 内嵌编辑助手」
- ✅ 右键 PDF 文件 → 打开方式 → PDF 内嵌编辑助手
- ✅ 命令行运行 `pdf-editor 文件.pdf`

### 卸载

```bash
sudo ./uninstall.sh
```

### 手动运行（不安装）

```bash
./start.sh
```

### 方式三：一键安装脚本

```bash
chmod +x setup.sh
./setup.sh
```

## 使用方法

```bash
# 打开编辑器
python main.py

# 打开指定文件
python main.py document.pdf

# Docker 方式打开指定文件
./start.sh document.pdf
```

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+O` | 打开 PDF |
| `Ctrl+S` | 保存 |
| `Ctrl+Shift+S` | 另存为 |

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
| 轻量级 | ✅ <1MB | ~5MB | ~1MB | ~2MB | ~200MB |
| Docker 支持 | ✅ | ❌ | ❌ | ❌ | ❌ |

## 为什么不用福昕/WPS？

1. **隐私安全** — 文件不会离开你的电脑
2. **完全免费** — 无授权费，无订阅
3. **轻量级** — <1MB vs 200MB+
4. **可自动化** — 可集成到工作流中
5. **可定制** — 根据需求修改

## 项目结构

```
pdf-editor-assistant/
├── main.py              # 程序入口
├── start.sh             # Docker 启动脚本
├── setup.sh             # 一键安装脚本（本地版）
├── Dockerfile           # Docker 镜像（含 LibreOffice）
├── docker-compose.yml   # Docker Compose 配置
├── requirements.txt     # Python 依赖
├── core/
│   ├── converter.py     # LibreOffice 转换封装
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
| 文件转换 | LibreOffice headless |
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
- [LibreOffice](https://www.libreoffice.org/) — 文档转换引擎
