[English](README.md) | [繁體中文](README_zh-TW.md)

# wxCvAnnotator

**High-Performance AI-Assisted Image Annotation Tool**

wxCvAnnotator is a desktop application built with Python and OpenCV, designed specifically for image annotation workflows. It combines traditional manual annotation tools with modern AI models (SAM, YOLO) to deliver a smooth and precise annotation experience.

## 🎯 Key Features

### 1. Annotation Tools (ROI Tools)
Core geometric drawing tools for various computer vision tasks:
*   **Rectangle**: Standard bounding box annotation.
*   **Rotated Rectangle**: Supports oriented object annotation, ideal for industrial inspection (AOI) and OBB tasks.
*   **Polygon**: Arbitrary shape segmentation mask annotation.
*   **Circle & Annulus**: Specialized geometric feature annotation.

### 2. AI-Assisted
Integrated deep learning models to accelerate the annotation process:
*   **Segment Anything (SAM / EfficientSAM)**: Automatically generate masks and polygon contours with a single click.
*   **YOLO Auto-Detection**: scan and annotate all known objects in the frame with one click.

### 3. Data Formats & Management
*   **Compatibility**: Uses **LabelMe JSON** format by default, compatible with existing datasets created by LabelMe.
*   **Export Support**: Supports exporting annotations to YOLO format (TXT) and COCO format (JSON).
*   **Large Image Support**: Optimized rendering engine for smooth navigation and zooming of high-resolution images.

## 📦 Installation & Usage

### Requirements
*   Python 3.8+
*   wxCvModule (Core rendering library)

### Quick Start

1.  **Install Dependencies**
    ```bash
    pip install wxcvmodule
    pip install -r requirements.txt
    ```

2.  **Run Application**
    ```bash
    python main.py
    ```

## 🛠️ Controls

*   **Left Click**: Draw, select, and edit objects.
*   **Right Click**: Open context menu (Delete, Properties).
*   **Mouse Wheel**: Zoom image in/out.
*   **Middle Click (or hold Space)**: Pan image.
*   **S Key**: Switch to Select Mode.

---
*Maintained by wxCvRoot Organization*
