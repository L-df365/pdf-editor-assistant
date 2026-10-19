# PDF Editor Assistant

[中文文档](README_CN.md)

**The only open-source PDF page manager with visual GUI** — insert Word/Excel/images into PDF at any position, auto-convert to PDF pages, with real-time preview.

> 💡 Why this exists: Tools like `pdfarranger`, `pdf2pdf`, `qpdf` can merge PDFs, but none offer a **visual GUI** where you can see page thumbnails, drag to reorder, and insert external files at specific positions. This fills that gap.

## Features

- 📄 **Visual Page Management** — See all pages as thumbnails, drag to reorder
- 📝 **Insert Any File** — Word (.docx), Excel (.xlsx), Images (.png/.jpg) → Auto-convert to PDF → Insert at any position
- 🔄 **Page Operations** — Rotate, delete, move pages
- 👁️ **Real-time Preview** — Fit-to-width / 100% zoom modes
- 💾 **Save** — Save / Save As

## Quick Start

### One-Click Install (Recommended)

```bash
git clone https://github.com/L-df365/pdf-editor-assistant.git
cd pdf-editor-assistant
sudo ./install.sh
```

After installation:
- ✅ "PDF Editor Assistant" appears in application menu
- ✅ Right-click PDF → Open with → PDF Editor Assistant
- ✅ Command line: `pdf-editor file.pdf`

> WPS Office / LibreOffice are not bundled or installed with the app.
> Selecting a missing backend explicitly prompts to install it and restart.

### Uninstall

```bash
sudo ./uninstall.sh
```

### Run Without Installing

```bash
pip3 install -r requirements.txt
python3 main.py
```

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
| Install Size | ~120MB | ~5MB | ~1MB | ~2MB | ~200MB |

## Why Not Just Use Foxit/WPS?

1. **Privacy** — Your documents never leave your machine
2. **Free** — No license fees, no subscriptions
3. **Lightweight** — ~120MB vs 200MB+
4. **Automatable** — Can be integrated into workflows via CLI
5. **Customizable** — Modify to fit your specific needs

## Conversion Backends

The conversion backend is pluggable behind a single interface:

```python
output_path = backend.convert_to_pdf(input_path)
```

Available backends (not bundled; the app calls a locally installed copy):

| Name | Description |
|------|-------------|
| `wps` | Local WPS Office via pywpsrpc. Silent conversion (`Visible = False`, `WithWindow = False`) on an isolated Xvfb display — the splash screen and windows never appear on your desktop |
| `libreoffice` | LibreOffice headless conversion |

The app itself only contains the UI and PDF logic; WPS/LibreOffice are not
packaged with it. On startup the app checks the local environment:

- **WPS installed**: automatically installs the missing `pywpsrpc` / `xvfb`
  support.
- **LibreOffice installed**: used directly, no extra components needed.
- **Neither installed**: shows two buttons, "Install WPS Office" and "Install
  LibreOffice", which open the system software store and copy the search term.
  Restart the app after installation.
- Selecting a missing backend manually under Settings → Conversion Backend also
  offers to install it.

Select the backend (highest priority first):

1. GUI: Settings → Conversion Backend
2. CLI: `python3 main.py --backend wps file.pdf`
3. Environment: `PDF_EDIT_BACKEND=wps|libreoffice|auto`
4. Default `auto`: prefer WPS (pywpsrpc), fall back to LibreOffice

The WPS backend requires a local WPS Office installation and `pywpsrpc`.
There is no official aarch64 wheel, so building from source may take a while;
the app attempts the install and shows instructions if it fails. Conversions
run on an isolated Xvfb display, so the WPS splash screen never flashes on the
desktop.

## Architecture

```
pdf-editor-assistant/
├── main.py              # Entry point
├── install.sh           # One-click installer
├── uninstall.sh         # Uninstaller
├── requirements.txt     # Python dependencies
├── requirements-wps.txt # Optional: WPS backend dependency
├── core/
│   ├── converter.py     # Switchable backend facade
│   ├── settings.py      # Persist the selected backend
│   ├── backends/        # Backend implementations
│   │   ├── base.py      # Common interface
│   │   ├── installer.py # On-demand WPS / LibreOffice install
│   │   ├── wps.py       # Silent WPS backend
│   │   ├── wps_worker.py# Isolated WPS conversion process
│   │   └── libreoffice.py
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
| File Conversion | Local WPS Office (pywpsrpc) / LibreOffice headless (on demand) |
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
- [WPS Office / pywpsrpc](https://github.com/timxx/pywpsrpc) — Silent local document conversion
- [LibreOffice](https://www.libreoffice.org/) — Fallback document conversion engine
