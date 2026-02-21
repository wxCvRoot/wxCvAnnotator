# wxCvAnnotator User Manual (使用者手冊)

This document provides a guide to the new features and interface enhancements in wxCvAnnotator v2.0.

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

## 3. Supported Annotation Tools
(See `docs/AI_ANNOTATION_SPEC.md` for AI-assisted tools)
- **Rectangle**: Standard bounding box.
- **Polygon**: Multi-point polygon.
- **Rotated Rectangle**: Oriented bounding box.
- **Circle / Annulus / Point**: Specialized annotation shapes.
