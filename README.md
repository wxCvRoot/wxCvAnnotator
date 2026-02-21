[English](README.md) | [繁體中文](docs/README_zh-TW.md)

# wxCvAnnotator

**Industrial-Grade AI-Assisted Image Annotation Tool**

wxCvAnnotator is a high-performance desktop annotation tool built on **wxPython** and a **C++ OpenCV engine (wxCvModule)**. It is optimized for industrial vision workflows, offering smooth navigation of high-resolution images alongside AI-powered annotation assistance.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/wxCvRoot/wxCvAnnotator)

---

## ✨ Features

### Annotation Tools

A complete set of geometric drawing tools for various computer vision tasks:

| Tool | Description | Use Case |
|------|-------------|----------|
| **Rectangle** | Standard bounding box | Object Detection |
| **Rotated Rectangle** | Angle-aware bounding box | Industrial AOI, OBB |
| **Polygon** | Arbitrary shape contour | Instance Segmentation |
| **Circle / Annulus** | Circular and ring-shaped annotations | Geometric Feature Labeling |
| **Point** | Single keypoint | Pose Estimation |

### AI-Assisted Annotation

Integrated deep learning models to dramatically accelerate labeling:

- **Segment Anything (SAM / SAM 2 / EfficientSAM)**: Click on an object to instantly generate a precise mask and polygon contour. ONNX quantized models (40 MB–600 MB) are automatically downloaded from HuggingFace on first use.

### Data Formats & Management

- **Storage**: **LabelMe JSON** format by default (one `.json` per image), fully compatible with existing LabelMe datasets.
- **Export**: YOLO TXT, COCO JSON, Pascal VOC XML, CSV.
- **Label Management**: Three-level label loading (Project → Global → Default), custom colors, and Batch Rename.
- **Attribute Panel**: Attach `flags` (boolean), custom key-value attributes, and transcription text to each annotation.

### Interface & Experience

- **Large Image Support**: C++ rendering engine optimized for high-resolution images — smooth zoom and pan.
- **Three-Panel Layout**: Toolbar (left) → Canvas (center) → Instance List (right).
- **Resizable Panels**: Drag splitters to adjust panel widths; layout is remembered across sessions.
- **Multilingual**: UI supports **English**, **Traditional Chinese**, and **Japanese**.
- **Theme Switching**: Built-in Light / Dark themes with custom color scheme support.

---

## 📦 Installation

### Prerequisites

All platforms require **wxCvModule** (the C++ rendering engine) to be installed first:

```bash
# Install from PyPI (if a wheel is available for your platform)
pip install wxcvmodule

# Or install manually from the Releases page
pip install wxcvmodule-*.whl
```

> If wxCvModule is not installed, the application will start in **Mock mode** — some C++ rendering features will be disabled, but the Python UI remains functional.

---

### Windows

> Tested on: Windows 10/11 x64

**1. Install Python 3.10+**

Download from [python.org](https://www.python.org/downloads/). Make sure to check **Add Python to PATH** during installation.

**2. Install wxCvModule**

```cmd
pip install wxcvmodule
```

**3. Install wxCvAnnotator**

```cmd
pip install wxcvannotator
```

**4. Launch**

```cmd
wxcv-annotator
```

> **Optional — NVIDIA GPU acceleration:**
> ```cmd
> pip install onnxruntime-gpu
> ```

---

### macOS

> Tested on: macOS arm64 (Apple Silicon), Python 3.12

**1. Install pyenv (recommended)**

```bash
brew install pyenv
```

Add to `~/.zshrc`:

```bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

**2. Install Python 3.12**

```bash
pyenv install 3.12.12
pyenv local 3.12.12
```

**3. Install wxCvModule**

```bash
pip install wxcvmodule
# If no macOS wheel is available on PyPI, download manually from the Releases page:
pip install wxcvmodule-*.macosx-*.whl
```

**4. Install and launch**

```bash
pip install wxcvannotator
wxcv-annotator
```

> **macOS notes:**
> - `objc[] duplicate class` warnings at startup are a known issue and **do not affect functionality** — they can be safely ignored.
> - Do not run `python -c "import wxCvModule"` directly in the shell; always launch via `wxcv-annotator`.

---

### Linux

> Tested on: Ubuntu 22.04 x64

**1. Install system dependencies**

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-pip python3-dev \
    libgtk-3-dev libgl1-mesa-glx libglib2.0-0
```

**2. Install wxCvModule**

```bash
pip install wxcvmodule
```

**3. Install and launch**

```bash
pip install wxcvannotator
wxcv-annotator
```

> **Optional — NVIDIA CUDA GPU acceleration:**
> ```bash
> pip install onnxruntime-gpu
> ```

---

### Developer Install

```bash
git clone https://github.com/wxCvRoot/wxCvAnnotator.git
cd wxCvAnnotator
pip install -e .
wxcv-annotator
```

---

### Launch Options

```bash
wxcv-annotator                       # Standard launch (after install)
wxcv-annotator /path/to/image.jpg   # Open a specific image
wxcv-annotator /path/to/folder/     # Open a folder
python -m wxcvannotator             # Module mode
python main.py                      # Dev launcher
```

---

### Verify Installation

```bash
python -c "
import wx; print(f'wxPython: {wx.version()}')
import numpy; print(f'numpy: {numpy.__version__}')
import cv2; print(f'opencv: {cv2.__version__}')
try:
    import onnxruntime; print(f'onnxruntime: {onnxruntime.__version__}')
except ImportError:
    print('onnxruntime: not installed (AI features disabled)')
import wx; import wxCvModule; print('wxCvModule: OK')
import wxcvannotator; print(f'wxcvannotator: {wxcvannotator.__version__}')
"
```

---

## 🔄 Basic Workflow

1. **Open image**: Go to `File > Open Image` or `File > Open Folder`, or drag and drop an image onto the window.
2. **Select tool**: Click an annotation tool in the left toolbar (Rectangle, Polygon, Rotated Rect, etc.).
3. **Draw**: Click or drag on the canvas to draw the shape.
4. **Add to list**: Press **Enter** or click **[➕ Add]** in the toolbar. Set the label in the dialog and confirm.
5. **Edit**: Click an annotation in the right-side list, adjust it on the canvas, then press **Enter** to update.
6. **Attributes**: With an annotation selected, use the bottom panel to edit flags, custom key-value attributes, and transcription text.
7. **Auto-save**: Annotations are automatically saved as a `.json` file (LabelMe format) alongside the image.

---

## 🤖 AI-Assisted Annotation

### Workflow

1. Select **AI Polygon** or **AI Mask** from the left toolbar.
2. Choose a model from the **Model** dropdown:
   - **EfficientSAM** — Speed-first; ideal for real-time annotation.
   - **SAM / SAM 2** — Accuracy-first; best for complex boundaries.
3. Click on the image to add prompt points:
   - **Left-click** (green dot): Positive prompt — include this area.
   - **Right-click** (red dot): Negative prompt — exclude this area.
   - **Backspace**: Remove the last prompt point.
4. A preview polygon updates in real time after each click.
5. **Finalize**:
   - Press **Enter** or **double left-click**: Confirm and add to the list.
   - **Double right-click**: Remove the last prompt point.

> **First use**: The selected model will be automatically downloaded from HuggingFace when you first click. Ensure you have an internet connection. Download progress is shown in the status bar.

---

## 📤 Dataset Export

### Single Image Export

Go to **Export > Export Current Image...**, choose the target format, and confirm. The output file is saved in the same directory as the image.

### Dataset Split Export

Go to **Export > Export Dataset (Split)...** to configure:

- **Honor manual status**: Images marked as `train/val/test` in the file list are assigned to those splits first.
- **Adjust ratios**: Set train/val/test split ratios for unmarked images using sliders.
- **Copy images**: Choose whether to copy the actual image files to produce a standalone dataset package.

**Supported formats:**

| Format | Description |
|--------|-------------|
| YOLO TXT | YOLOv5/v8/v11 — supports det / seg / obb |
| COCO JSON | Standard COCO format — supports detection and segmentation |
| Pascal VOC XML | Classic XML format for Detectron2 and similar frameworks |
| CSV | Lightweight general-purpose format |

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `S` | Switch to Select / Edit mode |
| `P` | Polygon tool |
| `R` | Rotated Rectangle tool |
| `Enter` | Add / Update annotation |
| `Esc` | Cancel current drawing |
| `Delete` | Delete selected annotation |
| Scroll wheel | Zoom image |
| Middle-click / Hold Space | Pan image |
| Double left-click (AI mode) | Confirm AI prediction |
| Double right-click (AI mode) | Remove last prompt point |

---

## 🛠️ System Requirements

| Item | Minimum |
|------|---------|
| Python | 3.10+ |
| wxPython | 4.2.0+ |
| OS | Windows 10+, macOS 12+, Ubuntu 20.04+ |
| RAM | 4 GB (8 GB+ recommended for AI features) |
| Disk | < 100 MB base; AI models add 40 MB–600 MB |

---

## 🔗 FAQ

**Q: `wxcv-annotator` command not found after install?**
> Make sure Python's `Scripts` directory is in your PATH. On Windows, try `python -m wxcvannotator`.

**Q: `ModuleNotFoundError: No module named 'wx'`?**
> ```bash
> pip install wxPython
> ```

**Q: AI annotation is unavailable?**
> Install `onnxruntime`:
> ```bash
> pip install onnxruntime      # CPU
> pip install onnxruntime-gpu  # NVIDIA GPU
> ```

**Q: Application starts in Mock mode?**
> `wxCvModule` is not correctly installed. Verify with:
> ```bash
> pip show wxcvmodule
> ```

**Q: `objc[] duplicate class` warnings on macOS?**
> This is a known issue caused by both `cv2` and `wxCvModule` bundling their own OpenCV dynamic libraries. It **does not affect functionality** and can be ignored.

---

## ⚖️ License

This project is licensed under the **Apache License 2.0**.

Copyright 2026 [wxCvRoot](https://github.com/wxCvRoot)

See the [LICENSE](LICENSE) file for full terms.

This project makes use of the following open-source components:
- [OpenCV](https://opencv.org/) — Apache 2.0
- [wxWidgets](https://www.wxwidgets.org/) — wxWindows Licence
- [Segment Anything (SAM)](https://github.com/facebookresearch/segment-anything) — Apache 2.0
- [EfficientSAM](https://github.com/yformer/EfficientSAM) — Apache 2.0

---

*Maintained by [wxCvRoot](https://github.com/wxCvRoot)*
