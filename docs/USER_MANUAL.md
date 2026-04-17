# wxCvAnnotator User Manual (使用者手冊)

> **最後更新：2026-04-15** — --model-path CLI parameter; OCR lazy init (no startup delay)

This document provides a guide to the new features and interface enhancements in wxCvAnnotator v2.0.

## 0. Command-Line Parameters (命令列參數)

The application can be launched with optional arguments:

```bash
wxcv-annotator [filename] [options]
# or
python main.py [filename] [options]
```

| Parameter | Description |
|---|---|
| `filename` | Image file or directory to open on startup |
| `--labels LABELS` | Comma-separated label names, or path to a label file |
| `--nodata` | Do not embed image data in JSON annotation files |
| `--embed` | Force embed image data in JSON annotation files |
| `--output DIR` | Save annotation files to a custom output directory |
| `--config PATH` | Load a custom `settings.json` instead of the default |
| `--lang LANG` | Override display language for this session only (e.g. `zh_TW`, `en_US`, `ja_JP`). Does not change the saved setting. |
| `--no-help` | Hide the **Help** menu from the menu bar and set the window title to `"Annotation Tool"`. Useful for OEM or embedded deployments. |
| `--model-path PATH` | Override the AI/OCR model weights directory for this session only. Does not change the saved setting. |

### Examples

```bash
# Open a specific image
wxcv-annotator /path/to/image.jpg

# Open a folder and use Traditional Chinese UI
wxcv-annotator /path/to/folder --lang zh_TW

# OEM mode: hide Help menu, neutral title
wxcv-annotator --no-help

# OEM mode with a pre-loaded image
wxcv-annotator --no-help /path/to/image.jpg

# Use a custom model weights directory
wxcv-annotator --model-path /mnt/nas/models

# Combine: OEM mode + custom model path + pre-loaded folder
wxcv-annotator --no-help --model-path D:\models\Annotator /path/to/images
```

> **Note:** OCR models are loaded lazily — the first time you press `Ctrl+T` (ROI transcribe) or `Ctrl+Shift+T` (full-image OCR), the selected backend will initialize. There is no startup delay.

---

## 1. Advanced Theme System & Appearance (進階主題與外觀)

The annotation tool now supports a fully customizable theme system to improve visibility and comfort during long annotation sessions.

### Features
- **Custom Themes**: You can define your own color schemes in `config/theme_settings.json`.
- **Live Preview**: Changing the theme or font size in the Settings window now immediately updates the entire application UI without requiring a restart.
- **Font Scaling**: A global `font_size` setting ensures that all UI elements, including lists, toolbar buttons, and menus, are legible on screen.
- **Persistent Settings**: Your selected theme and font size are automatically saved.

### Configuration
Edit `config/theme_settings.json`:
```json
{
    "theme": "light",        // Active theme ID
    "font_size": 14,         // Global font size (Default: 10-12)
    "custom_themes": {
        "my_theme": {
            "name": "My Custom Theme",
            "bg_main": "#2b2b2b",
            "fg_main": "#ffffff",
            "bg_list": "#333333",
            "fg_list": "#eeeeee",
            "selection": "#4a90e2",
            "font_size": 14  // Optional: Override global size
        }
    }
}
```

## 2. Resizable Interface Layout (可調整介面佈局)

The application layout is now flexible, allowing you to prioritize screen space for the image or the toolbars.

### Usage
- **Toolbar Width**: Drag the vertical separator between the left toolbar and the image area to adjust the toolbar size.
- **List Panel Width**: Drag the vertical separator between the image area and the right-side lists to adjust the width of the label/file lists.
- **Persistence**: The application remembers your preferred panel widths and restores them next time you open the app.
- **Smart Resizing**: When you resize the main window, the side panels maintain your set width, while the central image area automatically expands or contracts.

## 3. File & Annotation Management (檔案與標註管理)

### Annotation List Right-Click Menu

Right-click on any **polygon** or **mask** annotation in the **Annotation List** to access shape tools:

#### Refine Shape…
Apply morphological operations to clean up noisy or imprecise contours.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Operation | Erosion / Dilation / Opening / Closing | Erosion shrinks; Dilation expands; Opening removes small protrusions; Closing fills small gaps |
| Kernel size | 1 – 99 px | Side length of the structuring element |
| Iterations | 1 – 20 | Number of times the operation is applied |
| Smooth (ε) | 0 – 50 px | `approxPolyDP` tolerance (polygon output only); `0` keeps every contour point |

- **Polygon** input → rasterised → morph → `approxPolyDP(ε)` → new polygon
- **Mask** input → morph → updated mask (type unchanged)
- **Preview** updates the canvas immediately without saving; **Apply** commits the change (undo-able with `Ctrl+Z`); **Cancel** / closing the window restores the original shape.

#### Convert Polygon → Mask… *(polygon only)*
Rasterises the polygon to a full-image binary mask.  Adjust **Mask alpha** (overlay transparency, 0.10 – 1.00) before applying.

#### Convert Mask → Polygon… *(mask only)*
Traces the mask boundary and converts it to a polygon.

| Parameter | Description |
|-----------|-------------|
| Smooth (ε) | `approxPolyDP` tolerance; `0` keeps all contour points |

**Hollow masks** (donut / annular shapes) are handled automatically using the *bridge technique*: each hole contour is stitched into the outer boundary via a horizontal cut, producing a single closed polygon compatible with LabelMe and even-odd fill renderers.  The dialog reports the number of detected holes before you apply.

---

### File List Right-Click Menu
Right-click on any item in the **File List** (bottom right) to access advanced options:
- **Set Status**: Mark the image as `train`, `val`, or `test`.
- **Delete Annotation File**: Permanently remove the `.json` file associated with the selected image. If you delete the annotation of the current image, the display will reset automatically.

### User Information & Metadata
In **Settings > User Settings**, you can configure:
- **Annotator Name & Quality**: Set the name and quality score to be associated with your work.
- **Enable User Information toggle**: If checked, the above metadata will be saved inside the LabelMe JSON file under `annotator_name` and `annotator_quality`. If unchecked, no user data will be stored.

## 4. AI-Assisted Annotation (AI 輔助標註)

The AI toolkit helps you label complex objects with just a few clicks using Segment Anything (SAM) models.

### Usage Flow
1. **Select Tool**: Click **AI Polygon** or **AI Mask** on the left toolbar.
2. **Choose Model**: Use the **Model** drop-down menu that appears below the tool buttons.
   - *EfficientSAM (Speed)*: Best for real-time performance.
   - *SAM (Accuracy)*: Best for complex boundaries.
3. **Interactive Prompting**:
   - **Left-click (Green dot)**: Add a **Positive** prompt to include an area.
    - **Right-click (Red dot)**: Add a **Negative** prompt to exclude an area.
    - **Backspace**: Remove the last prompt point.
4. **Finalize & Undo (Special Mouse Maneuvers)**:
   - **Left Double-Click**: Instantly finalize the current prediction and add it to the list (equivalent to pressing Enter).
   - **Right Double-Click**: Quickly undo the last prompt point (equivalent to pressing Backspace).
5. **Finalize**: Press **Enter** to convert the AI preview into a standard annotation.

### Automatic Downloading
If the selected model is not found in your local `models/` directory, the application will automatically download it upon your first click. You can monitor the progress in the status bar or a popup dialog.

## 5. Dataset Exporting (資料集導出)

wxCvAnnotator v2.0 includes a powerful export system designed for AI model training.

### Single Image Export
- Go to **Export -> Export Current Image...**
- Select your target format (YOLO, COCO, VOC, CSV).
- The file will be saved in the directory where the current image is located.

### Advanced Dataset Splitting (New)
- Go to **Export -> Export Dataset (Split)...**
- **Honor Manual Status**: If checked, images marked as `train/val/test` in the File List will be strictly moved to those folders.
- **Adjust Ratios**: For non-marked images, use the sliders/spinners to define how to randomly distribute them.
- **Copy Images**: Choose whether to only generate annotation files or to copy the actual `.jpg/.png` files to create a standalone dataset package.
- **YOLO-Seg/OBB**: Full support for polygon and rotated rectangle exports.

## 5. OCR Text Recognition (OCR 文字辨識)

wxCvAnnotator integrates an OCR engine that can recognize text from annotation regions or the full image.

### 5.1 Backend Selection

Select the OCR backend from the **OCR Backend** dropdown in the left toolbar (below the OCR section divider). Available backends:

| Backend | Type | Size | GPU Needed | Grounding |
|---------|------|------|-----------|-----------|
| **PPOCRv5-Mobile** | ONNX (no Paddle) | ~11 MB | ❌ CPU ok | ✅ bbox |
| **PPOCRv5-Server** | ONNX (no Paddle) | ~122 MB | ❌ CPU ok | ✅ bbox |
| **GOT-OCR2.0** | VLM | 1.4 GB | ✅ ~1.4 GB | ⚠️ unstable |
| **Qwen2.5-VL-3B** | VLM | 7.5 GB | ✅ ~2.5 GB (4-bit) | ✅ bbox |
| **Qwen3-VL-2B** | VLM | ~4 GB | ✅ ~1.7 GB (4-bit) | ✅ bbox |
| **Qwen3-VL-4B** | VLM | ~8.3 GB | ✅ ~3.1 GB (4-bit) | ✅ bbox |
| **InternVL3-2B** | VLM | ~4 GB | ✅ ~4.2 GB (bf16) | ❌ text only |

> **PPOCRv5 backends** use pure ONNX inference (onnxruntime) — no PaddlePaddle installation required. They support Chinese (Simplified/Traditional), English, Japanese, and Korean. They automatically fall back to CPU if CUDA is unavailable.
>
> **VLM backends** require `torch` + `transformers` and a capable GPU. Models are downloaded from HuggingFace on first use.

### 5.2 Mode 2 — ROI OCR (Ctrl+T)

Recognize text inside an existing annotation bounding box.

1. Select an annotation (click in the annotation list or on the canvas)
2. Press **Ctrl+T** (or use **Edit → OCR Transcribe**)
3. OCR runs in the background; the result is written to the annotation's **Transcription** field
4. View / edit the result in the **Attribute Panel** on the right, or press **Enter** (non-drawing mode) to open the text editor popup

> **Tip**: PPOCRv5-Mobile is the fastest option for ROI (< 100 ms). Qwen3-VL-2B gives the best quality for complex or mixed-language text (~2.5 s).

### 5.3 Mode 1 — Full-Image OCR (Ctrl+Shift+T)

Detect and recognize all text regions in the current image, then create annotation objects automatically.

1. Load an image and select an OCR backend
2. Press **Ctrl+Shift+T** (or click **📄 OCR Full Image** in the toolbar, or use **Edit → OCR Full Image**)
3. OCR runs in the background; when complete the **OCR Result Review** dialog appears
4. The dialog shows a checklist of all detected text regions (all pre-checked)
5. Uncheck any results you want to discard, then click **Create Annotations**
6. New `rectangle` annotations are created with the recognized text in their **Transcription** field
   - **With bbox backends** (PPOCRv5, Qwen family): annotations placed at detected coordinates
   - **No-bbox backends** (GOT-OCR2.0, InternVL3): a single annotation spanning the full image is created
7. A `"text"` category (`#00AAFF`) is auto-created if it does not already exist

### 5.4 How to Annotate Text Regions for OCR (Important)

This section applies when you draw **Polygon annotations manually** and then use **Ctrl+T (ROI OCR)** to recognize the text. Correct point placement is required for PPOCRv5 to produce accurate results, especially for rotated text.

#### 5.4.1 Always Use Polygon Mode (not Rectangle) for Rotated Text

- **Rectangle** annotations crop an axis-aligned bounding box — rotated text will include large empty corners, causing OCR failure.
- **Polygon** annotations allow you to tightly wrap the text with a perspective crop, removing rotation before recognition.

> For horizontal text, a Rectangle annotation also works fine. But to be consistent and safe, **always use Polygon for OCR annotations**.

#### 5.4.2 Point Order — Clockwise, Starting from Top-Left

**Every OCR polygon must have exactly 4 points**, placed in this order:

```
P0 (TL) ──────── P1 (TR)
   │                 │
   │   Text content  │
   │                 │
P3 (BL) ──────── P2 (BR)
```

| Point | Position         | Description                              |
|-------|------------------|------------------------------------------|
| P0    | Top-Left (TL)    | **First click** — reading direction start |
| P1    | Top-Right (TR)   | P0 → P1 follows the top edge of text     |
| P2    | Bottom-Right (BR)|                                          |
| P3    | Bottom-Left (BL) | Last click — closes the polygon          |

**The same rule applies to rotated text**: P0 is always the top-left corner *relative to the text reading direction*, not relative to the image.

Example — text rotated 45° counter-clockwise:

```
          P0
         /    \
       P3      P1
         \    /
          P2
```

Click P0 at the text's own top-left, then continue clockwise (P1→P2→P3).

#### 5.4.3 Why Point Order Matters (Technical)

The system uses a **perspective transform** to straighten the text before sending it to the recognition model. The four corners are mapped to a fixed destination layout (TL→TR→BR→BL). If your points are in counter-clockwise order, the warped image will be horizontally mirrored — the model will fail to recognize it.

The system automatically detects and corrects counter-clockwise winding using Green's Theorem, but **clockwise annotation is strongly recommended** to avoid edge cases.

#### 5.4.4 Vertical Text

For vertical text (taller than it is wide), apply the same clockwise rule. The system automatically rotates the crop 90° counter-clockwise before recognition when `crop_height / crop_width ≥ 1.5`.

#### 5.4.5 Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Using Rectangle for rotated text | OCR returns empty or garbled | Switch to Polygon and tightly wrap the 4 corners |
| Wrong starting corner (e.g., starting at BR) | Text appears upside-down in crop | Always start from the top-left corner of the text |
| Using more than 4 points | Perspective transform distorted | Keep exactly 4 points per annotation |
| Polygon too loose (large margin) | Noise included, lower accuracy | Tighten corners to the actual text boundaries |

### 5.5 Installing OCR Dependencies

```bash
# PPOCRv5 backends — only requires onnxruntime (already installed with wxcvannotator)
# No extra steps needed; models must be placed in wxcvannotator/models/ppocrv5/

# VLM backends — requires PyTorch + transformers
pip install torch --index-url https://download.pytorch.org/whl/cu121  # CUDA 12.1
pip install "wxcvannotator[ocr]"
```

---

## 6. Supported Annotation Tools
(See `docs/AI_ANNOTATION_SPEC.md` for AI-assisted tools)
- **Rectangle**: Standard bounding box.
- **Polygon**: Multi-point polygon.
- **Rotated Rectangle**: Oriented bounding box.
- **Circle / Annulus / Point**: Specialized annotation shapes.

## 7. Keyboard Shortcuts (鍵盤快捷鍵)

### Annotation Tools
| Key | Action |
|-----|--------|
| `S` | Select tool |
| `P` | Polygon tool |
| `R` | Rotated Rectangle tool |
| `L` | Line tool |
| `C` | Circle tool |
| `A` | Annulus tool |
| `D` | Point tool |

### Annotation Actions
| Key | Action |
|-----|--------|
| `Enter` | Confirm / Add annotation |
| `Esc` | Cancel current drawing |
| `Delete` | Delete selected annotation |
| `Backspace` | Remove last AI prompt point (AI mode) |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |

### View
| Key | Action |
|-----|--------|
| `Space` | **Toggle annotation overlay** — hide/show all annotations. Useful for inspecting annotation edges against the raw image. Overlay always resets to visible when switching to a new image. |
| `Ctrl+=` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Fit to window |

### File & OCR
| Key | Action |
|-----|--------|
| `Ctrl+O` | Open image |
| `Ctrl+Shift+O` | Open folder |
| `Ctrl+S` | Save annotations |
| `Ctrl+T` | OCR transcribe (ROI) |
| `Ctrl+Shift+T` | OCR full image |
| `Ctrl+,` | Open Settings |
| `Ctrl+Q` | Exit |
