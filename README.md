# PDF Editor Assistant

[中文文档](README_CN.md)

**An open-source PDF page manager with a visual GUI** — insert Word/Excel/images into PDF at any position, auto-convert to PDF pages, with real-time preview.

> 💡 Why this exists: `pdfarranger` can reorder pages, `pdf2pdf` and `qpdf` can merge
> PDFs, but no open-source tool puts *drag-to-reorder* and *insert a Word/Excel/image
> at a given position* in the same window. That is the gap this fills.

![Workbench](docs/ui/01-工作台.png)

## Features

- 📄 **Visual Page Management** — Thumbnail rail, drag to reorder (with a drop indicator)
- 📝 **Insert Any File** — Word (.docx), Excel (.xlsx), Images (.png/.jpg) → Auto-convert to PDF → Insert at any position
  - **Batch insert**: select several files at once, choose the position (after current page / end of document / before a given page)
- 🔄 **Page Operations** — Rotate, delete, move pages
- ↩️ **Undo / Redo** — 5 steps of history, Ctrl+Z / Ctrl+Shift+Z
- 👁️ **Real-time Preview** — Fit / 50% / 100% / 200% zoom
- 🗂️ **Built-in File Panel** — Pinned places, multi-select, type badges, recent files
- 🖨️ **Print** — Print the current document: colour, duplex (long/short edge), copies, paper, scaling, N-up, page ranges
  (unsupported combinations are blocked with a reason instead of silently downgrading)
- 🗂️ **Batch printing** — Queue many files and set options per file;
  standalone entry point `pdf-print` (no page management, starts faster), the same window is reachable from the app
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
| Install Size | ~56MB | ~5MB | ~1MB | ~2MB | ~200MB |

## Why Not Just Use Foxit/WPS?

1. **Privacy** — Your documents never leave your machine
2. **Free** — No license fees, no subscriptions
3. **Lightweight** — ~1MB for the app itself (~56MB with dependencies) vs 200MB+
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
├── requirements.txt     # Python dependencies (PyMuPDF + Pillow only)
├── requirements-wps.txt # Optional: WPS backend dependency
├── core/                # UI-independent
│   ├── converter.py     # Switchable backend facade
│   ├── settings.py      # Persist the selected backend and recent files
│   ├── formats.py       # Supported file types (single source of truth)
│   ├── backends/        # Backend implementations
│   │   ├── base.py      # Common interface
│   │   ├── installer.py # On-demand WPS / LibreOffice install
│   │   ├── wps.py       # Silent WPS backend
│   │   ├── wps_worker.py# Isolated WPS conversion process
│   │   └── libreoffice.py
│   └── pdf_document.py  # PDF operations, undo stack (PyMuPDF)
├── gui/                 # UI layer (tkinter + self-drawn widgets)
│   ├── main_window.py   # Main window, top bar, menus
│   ├── theme.py         # Design tokens and ttk styles
│   ├── widgets.py       # Rounded buttons, chips, rounded cards
│   ├── draw.py          # Anti-aliased rounded-corner rendering
│   ├── menu.py          # Popover menus
│   ├── feedback.py      # Toast / confirm / error / info panels
│   ├── thumbnail_panel.py # Page rail: thumbnails, drag-drop, context menu
│   ├── preview_panel.py # Preview: stage, zoom, floating action bar
│   ├── file_sheet.py    # File panel
│   ├── insert_sheet.py  # Insert-position panel
│   ├── backend_dialog.py# Conversion backend settings
│   └── empty_state.py   # Empty state
├── docs/
│   ├── design-system.md # Design system
│   └── ui/              # Screenshots
└── tools/uitest.py      # UI self-test: synthesised real mouse events
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| GUI | tkinter |
| PDF Rendering | PyMuPDF |
| File Conversion | Local WPS Office (pywpsrpc) / LibreOffice headless (on demand) |
| Image Processing | Pillow |

## Roadmap

- [x] Batch insert multiple files (multi-select in the file panel)
- [x] Undo / redo
- [x] Print the current document (colour, duplex, copies, paper, scaling, N-up, page ranges)
- [x] Batch printing (multi-file queue, per-file overrides, pause/cancel/retry, failure isolation)
- [ ] Automatic job merge/split, print templates and history (see `docs/print-plan.md`)
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
