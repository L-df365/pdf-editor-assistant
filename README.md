# PDF Editor Assistant

[中文文档](README_CN.md)

**An open-source PDF page manager with a visual GUI** — insert Word / Excel / images
anywhere in a PDF, auto-convert them to PDF pages, and print the result with
per-file print settings.

![Workbench](docs/ui/01-工作台.png)

> 💡 Why this exists: `pdfarranger` can reorder pages, `pdf2pdf` and `qpdf` can merge
> PDFs, but no open-source tool puts *drag-to-reorder*, *insert a Word/Excel/image at a
> given position* and *print with per-file settings* in the same window.

---

## Features

### Page management

- 📄 **Visual page rail** — thumbnail list, drag to reorder (with a drop indicator),
  right-click menu with page-specific actions
- 📝 **Insert any file** — Word (.docx), Excel (.xlsx), PowerPoint (.pptx),
  images (.png/.jpg), text (.txt), PDF → converted to PDF pages → inserted anywhere
  - Select several files at once for a batch insert
  - Choose the position: after the current page / end of document / before a given page
- 🔄 **Page operations** — rotate, delete, move to start, move to end
- ↩️ **Undo / redo** — 5 steps of history, Ctrl+Z / Ctrl+Shift+Z
- 👁️ **Real-time preview** — Fit / 50% / 100% / 200% zoom
- 🗂️ **Built-in file panel** — pinned places, multi-select, type badges, recent files;
  folders are picked with the same hand-drawn panel
- 💾 **Save** — Save / Save As

### Printing

- 🖨️ **Print the current document** — colour, duplex (long / short edge), copies,
  paper, scaling, N-up, page ranges (`1-5,8,10-`)
  - Prints the **current editing state**: reorder, delete or insert first and the
    printout matches
  - Combinations the printer does not support are **blocked with a reason**, never
    silently downgraded (e.g. colour → black and white)
- 🗂️ **Batch printing** — queue many files and set options per file
  - Sort the queue (name / modified time / size / type) or reorder rows with ↑ ↓
  - Start / pause / cancel / retry failed; failed jobs stay isolated and do not
    block the rest
  - Standalone entry point `pdf-print`: no page management, starts faster

---

## Quick start

### One-Click Install (Recommended)

```bash
git clone https://github.com/L-df365/pdf-editor-assistant.git
cd pdf-editor-assistant
sudo ./install.sh
```

After installation:
- ✅ "PDF Editor Assistant" appears in the application menu
- ✅ Right-click PDF → Open with → PDF Editor Assistant
- ✅ Command line: `pdf-editor file.pdf`
- ✅ Command line: `pdf-print` (standalone batch printing)

> WPS Office / LibreOffice are not bundled or installed with the app. Selecting a
> missing backend explicitly prompts to install it and restart.
> Printing needs the system package `python3-cups` (the installer adds it).

### Standalone batch printing

```bash
pdf-print                 # opens the batch print window directly
```

It does not load the page management part, so it needs neither PyMuPDF nor the
full app — just tkinter and CUPS.

### Uninstall

```bash
sudo ./uninstall.sh
```

### Run Without Installing

```bash
pip3 install -r requirements.txt
python3 main.py                # the editor
python3 main.py --print        # batch printing
```

---

## Screenshots

| File | What it shows |
|---|---|
| [Workbench](docs/ui/01-工作台.png) | Main window: top bar, page rail, stage, floating action bar |
| [Context menu](docs/ui/02-右键菜单.png) | Right-click menu with page-specific actions |
| [Page rail](docs/ui/03-页面轨.png) | Thumbnail rail and scrollbar |
| [File panel](docs/ui/04-文件面板.png) | File panel (multi-select + selection count) |
| [Empty state](docs/ui/05-空状态.png) | Empty state before a document is opened |

Design system: [`docs/design-system.md`](docs/design-system.md) ·
Print feature plan: [`docs/print-plan.md`](docs/print-plan.md)

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` / `Ctrl+Shift+O` | Open PDF / open recent file |
| `Ctrl+S` / `Ctrl+Shift+S` | Save / Save As |
| `Ctrl+I` | Insert files after the current page |
| `Ctrl+P` | Print the current document |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Ctrl+R` / `Ctrl+Shift+R` | Rotate clockwise / counter-clockwise |
| `Ctrl+Shift+↑` / `Ctrl+Shift+↓` | Move to start / end |
| `Ctrl+0` / `1` / `2` | Fit / 100% / 200% zoom |
| `Ctrl+Shift+I` | Page info |
| `Ctrl+,` | Conversion backend settings |
| `Delete` | Delete the current page |
| `Ctrl+Q` | Quit |

---

## Comparison with existing tools

| Feature | **PDF Editor Assistant** | pdfarranger | pdf2pdf | qpdf | Foxit |
|---------|:-----------------------:|:-----------:|:-------:|:----:|:-----:|
| Visual GUI | ✅ | ✅ | ❌ | ❌ | ✅ |
| Insert Word/Excel | ✅ Auto-convert | ❌ | ❌ | ❌ | ✅ |
| Insert Images | ✅ | ✅ | ❌ | ❌ | ✅ |
| Drag to Reorder | ✅ | ✅ | ❌ | ❌ | ✅ |
| Rotate Pages | ✅ | ✅ | ❌ | ✅ | ✅ |
| Delete Pages | ✅ | ✅ | ❌ | ✅ | ✅ |
| Per-file print settings | ✅ | ❌ | ❌ | ❌ | ✅ |
| Batch print queue | ✅ | ❌ | ❌ | ❌ | ✅ |
| Fit-to-window Preview | ✅ | ❌ | ❌ | ❌ | ✅ |
| Open Source | ✅ | ✅ | ✅ | ✅ | ❌ |
| Install Size | ~57MB | ~5MB | ~1MB | ~2MB | ~200MB |

> Size breakdown: 1.5MB for the app itself, 48MB PyMuPDF, 7MB Pillow.
> WPS / LibreOffice are not included (installed on demand).

---

## Conversion backends

The conversion backend is pluggable behind a single interface:

```python
output_path = backend.convert_to_pdf(input_path)
```

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

---

## How printing works

Printing goes through CUPS / IPP. Every print option is a **job-level** IPP
attribute:

| Option in the UI | CUPS attribute |
|---|---|
| Colour (colour / monochrome) | `print-color-mode` |
| Duplex (one-sided / long-edge / short-edge) | `sides` |
| Copies | `copies` |
| Paper | `media` |
| Scaling | `print-scaling` |
| N-up | `number-up` + `number-up-layout` |
| Page ranges | `page-ranges` |

So "set options per file" means splitting into several jobs; consecutive files
with identical options can be merged into one job. Before submitting, the app
checks what the printer actually supports (`sides-supported`,
`print-color-mode-supported`, `media-supported`, `number-up-supported`) and
blocks unsupported combinations with an explanation.

`core/print_core/` is the single implementation of printing — no tkinter, no
PyMuPDF. Printing the open document (`print_single`) and batch printing
(`print_batch`) share the same option mapping, conversion and error handling.

---

## Architecture

```
pdf-editor-assistant/
├── main.py              # Entry point (--print opens batch printing directly)
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
│   ├── pdf_document.py  # PDF operations, undo stack (PyMuPDF)
│   └── print_core/      # Printing core (no tkinter / PyMuPDF)
│       ├── jobs.py      #   PrintJob / PrintOptions
│       ├── ranges.py    #   Page range parsing
│       ├── convert.py   #   Turn a job into a printable PDF
│       ├── backend.py   #   CUPS: capabilities, submit, query, cancel
│       └── queue.py     #   Batch queue
├── gui/                 # UI layer (tkinter + self-drawn widgets)
│   ├── main_window.py   # Main window, top bar, menus
│   ├── theme.py         # Design tokens and ttk styles
│   ├── widgets.py       # Rounded buttons, segmented control, chips, cards
│   ├── draw.py          # Anti-aliased rounded-corner rendering
│   ├── menu.py          # Popover menus
│   ├── feedback.py      # Toast / confirm / error / info panels
│   ├── thumbnail_panel.py # Page rail: thumbnails, drag-drop, context menu
│   ├── preview_panel.py # Preview: stage, zoom, floating action bar
│   ├── file_sheet.py    # File panel (files / folders)
│   ├── insert_sheet.py  # Insert-position panel
│   ├── print_sheet.py   # Print the current document
│   ├── print_options.py # Print options form (shared)
│   ├── batch_print_window.py # Batch print window
│   ├── backend_dialog.py# Conversion backend settings
│   ├── empty_state.py   # Empty state
│   └── version.py       # Version number
├── docs/
│   ├── design-system.md # Design system
│   ├── print-plan.md    # Print feature plan
│   └── ui/              # Screenshots
└── tools/uitest.py      # UI self-test: synthesised real mouse events (88 checks)
```

---

## Tech stack

| Component | Technology |
|-----------|------------|
| GUI | tkinter (ships with Python) + PIL for anti-aliased corners and shadows |
| PDF Rendering | PyMuPDF |
| File Conversion | Local WPS Office (pywpsrpc) / LibreOffice headless (on demand) |
| Printing | CUPS / IPP (`python3-cups`) |
| Image Processing | Pillow |

No third-party GUI framework is used; the only runtime dependencies are PyMuPDF
and Pillow.

---

## Roadmap

- [x] Batch insert multiple files (multi-select in the file panel)
- [x] Undo / redo
- [x] Print the current document (colour, duplex, copies, paper, scaling, N-up, page ranges)
- [x] Batch printing (multi-file queue, per-file overrides, pause/cancel/retry, failure isolation)
- [ ] Automatic job merge/split, print templates, print history
- [ ] Page cropping
- [ ] Watermark/stamp support
- [ ] Page numbering
- [ ] PDF merge/split
- [ ] Cross-platform packaging (PyInstaller)
- [ ] Dark mode

---

## Development

```bash
xvfb-run -a python3 tools/uitest.py      # UI self-test (88 checks, no display needed)
```

The self-test drives the real code paths with synthesised mouse events
(click / drag / hover / right-click) and never touches a real printer
(the CUPS connection is faked).

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering and manipulation
- [WPS Office / pywpsrpc](https://github.com/timxx/pywpsrpc) — Silent local document conversion
- [LibreOffice](https://www.libreoffice.org/) — Fallback document conversion engine
