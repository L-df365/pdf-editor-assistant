# PDF Editor Assistant

[中文文档](README_CN.md)

**The only open-source PDF page manager with visual GUI** — insert Word/Excel/images into PDF at any position, auto-convert to PDF pages, with real-time preview.

> 💡 Why this exists: Tools like `pdfarranger`, `pdf2pdf`, `qpdf` can merge PDFs, but none offer a **visual GUI** where you can see page thumbnails, drag to reorder, and insert external files at specific positions. This fills that gap.

## Features

- 📄 **Visual Page Management** — See all pages as thumbnails, drag to reorder
- 📝 **Insert Any File** — Word (.docx), Excel (.xlsx), Images (.png/.jpg) → Auto-convert to PDF → Insert at any position
- 🔄 **Page Operations** — Rotate, delete, move pages
- 👁️ **Real-time Preview** — Fit-to-width / 100% zoom modes
- 💾 **Save** — Save / Save As with incremental support

## Quick Start

### Prerequisites

- Git
- Docker

> 💡 **China users**: If `git clone` is slow, use a mirror:
> ```bash
> git clone https://ghfast.top/https://github.com/L-df365/pdf-editor-assistant.git
> # or
> git clone https://mirror.ghproxy.com/https://github.com/L-df365/pdf-editor-assistant.git
> ```

### One-Click Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/L-df365/pdf-editor-assistant.git
cd pdf-editor-assistant

# Run installer
sudo ./install.sh
```

After installation:
- ✅ "PDF Editor Assistant" appears in application menu
- ✅ Right-click PDF → Open with → PDF Editor Assistant
- ✅ Command line: `pdf-editor file.pdf`

### Uninstall

```bash
sudo ./uninstall.sh
```

### Run Without Installing

```bash
./start.sh
```

### Option 3: One-click Setup

```bash
chmod +x setup.sh
./setup.sh
```

## Usage

```bash
# Open editor
python main.py

# Open specific file
python main.py document.pdf

# Docker with file
./start.sh document.pdf
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open PDF |
| `Ctrl+S` | Save |
| `Ctrl+Shift+S` | Save As |

## Comparison with Existing Tools

| Feature | **PDF Editor Assistant** | pdfarranger | pdf2pdf | qpdf | Foxit |
|---------|:-----------------------:|:-----------:|:-------:|:----:|:-----:|
| Visual GUI | ✅ | ✅ | ❌ | ❌ | ✅ |
| Insert Word/Excel | ✅ Auto-convert | ❌ | ❌ | ❌ | ✅ |
| Insert Images | ✅ | ✅ | ❌ | ❌ | ✅ |
| Drag to Reorder | ✅ | ✅ | ❌ | ❌ | ✅ |
| Rotate Pages | ✅ | ✅ | ❌ | ✅ | ✅ |
| Delete Pages | ✅ | ✅ | ❌ | ✅ | ✅ |
| Fit-to-width Preview | ✅ | ❌ | ❌ | ❌ | ✅ |
| Open Source | ✅ | ✅ | ✅ | ✅ | ❌ |
| Free | ✅ | ✅ | ✅ | ✅ | ❌ |
| Lightweight | ✅ <1MB | ~5MB | ~1MB | ~2MB | ~200MB |
| Docker Support | ✅ | ❌ | ❌ | ❌ | ❌ |

## Why Not Just Use Foxit/WPS?

1. **Privacy** — Your documents never leave your machine
2. **Free** — No license fees, no subscriptions
3. **Lightweight** — <1MB vs 200MB+
4. **Automatable** — Can be integrated into workflows via CLI
5. **Customizable** — Modify to fit your specific needs

## Architecture

```
pdf-editor-assistant/
├── main.py              # Entry point
├── start.sh             # Docker launcher
├── setup.sh             # One-click setup (system install)
├── Dockerfile           # Docker image with LibreOffice
├── docker-compose.yml   # Docker Compose config
├── requirements.txt     # Python dependencies
├── core/
│   ├── converter.py     # LibreOffice conversion wrapper
│   └── pdf_document.py  # PDF operations (PyMuPDF)
└── gui/
    ├── main_window.py   # Main window
    ├── thumbnail_panel.py # Thumbnail panel with drag-drop
    └── preview_panel.py # Preview panel with zoom
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| GUI | tkinter |
| PDF Rendering | PyMuPDF |
| File Conversion | LibreOffice headless |
| Image Processing | Pillow |

## Roadmap

- [ ] Batch insert multiple files
- [ ] Page cropping
- [ ] Watermark/stamp support
- [ ] Page numbering
- [ ] PDF merge/split
- [ ] Cross-platform packaging (PyInstaller)
- [ ] Dark mode

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering and manipulation
- [LibreOffice](https://www.libreoffice.org/) — Document conversion engine
