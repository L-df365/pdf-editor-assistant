# PDF 内嵌编辑助手

轻量级 PDF 页面管理工具，对标福昕 PDF 编辑器的页面管理功能。支持在任意位置插入 Word/Excel/图片并自动转换为 PDF 页面。

## 功能

- **打开 PDF**：显示所有页面缩略图，支持滚动浏览
- **插入文件**：Word (.docx/.doc)、Excel (.xlsx/.xls)、图片 (.png/.jpg 等) → 自动转 PDF → 插入指定位置
- **拖拽排序**：按住缩略图拖动调整页面顺序
- **页面操作**：旋转、删除页面
- **预览**：右侧大图预览，支持「适应窗口」和「100%」两种缩放模式
- **保存**：保存/另存为 PDF

## 截图

<!-- 添加截图 -->

## 安装

### 依赖

- Python 3.6+
- PyMuPDF (`pip install PyMuPDF`)
- Pillow (`pip install Pillow`)
- pypdf (`pip install pypdf`)
- LibreOffice（用于 Word/Excel 转 PDF）

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/yourusername/pdf-editor-assistant.git
cd pdf-editor-assistant

# 安装 Python 依赖
pip install -r requirements.txt

# 启动
python main.py
```

## 使用

### 命令行启动

```bash
python main.py
```

### 打开指定文件

```bash
python main.py /path/to/file.pdf
```

### Linux 桌面快捷方式

将 `pdf-editor.desktop` 复制到 `~/.local/share/applications/`：

```bash
cp pdf-editor.desktop ~/.local/share/applications/
```

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI | tkinter |
| PDF 渲染 | PyMuPDF (fitz) |
| 文件转换 | LibreOffice headless |
| 图片处理 | Pillow |

## 目录结构

```
pdf-editor-assistant/
├── main.py                # 入口
├── requirements.txt       # Python 依赖
├── pdf-editor.desktop     # Linux 桌面快捷方式
├── core/
│   ├── __init__.py
│   ├── converter.py       # LibreOffice 转换封装
│   └── pdf_document.py    # PDF 操作封装
└── gui/
    ├── __init__.py
    ├── main_window.py     # 主窗口
    ├── thumbnail_panel.py # 缩略图面板（拖拽排序）
    └── preview_panel.py   # 预览面板
```

## 与福昕对比

| 功能 | 本工具 | 福昕 PDF 编辑器 |
|------|--------|----------------|
| 页面缩略图 | ✅ | ✅ |
| 插入 Word/Excel | ✅ 自动转 PDF | ✅ |
| 插入图片 | ✅ | ✅ |
| 拖拽排序 | ✅ | ✅ |
| 旋转/删除 | ✅ | ✅ |
| 预览 | ✅ | ✅ |
| 价格 | 免费 | 付费 |
| 体积 | <1MB | ~200MB |
| 开源 | ✅ | ❌ |

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF 渲染和操作
- [LibreOffice](https://www.libreoffice.org/) - 文档转换
