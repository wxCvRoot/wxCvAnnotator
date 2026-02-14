[English](README.md) | [繁體中文](README_zh-TW.md)

# wxCvAnnotator

**高效能 AI 輔助圖像標註工具**

這是一個基於 Python 與 OpenCV 的桌面應用程式，專為圖像標註工作流程設計。它結合了傳統的手動標註工具與現代 AI 模型 (SAM, YOLO)，旨在提供流暢且精確的標註體驗。

## 🎯 主要功能

### 1. 標註工具 (ROI Tools)
提供完整的幾何形狀繪製功能，適用於各種電腦視覺任務：
*   **矩形 (Rectangle)**：標準邊界框 (Bounding Box)。
*   **旋轉矩形 (Rotated Rectangle)**：支援帶角度的物件標註，適用於工業檢測 (AOI) 與 OBB 任務。
*   **多邊形 (Polygon)**：支援任意形狀的分割標註 (Segmentation)。
*   **圓形 (Circle) 與環形 (Annulus)**：適用於特定幾何特徵的標註。

### 2. AI 輔助 (AI-Assisted)
整合深度學習模型以加速標註過程：
*   **Segment Anything (SAM / EfficientSAM)**：點選物件即可自動生成遮罩與多邊形輪廓。
*   **YOLO 自動偵測**：一鍵掃描並標註畫面中所有已知物件。

### 3. 資料格式與管理
*   **格式相容**：預設使用 **LabelMe JSON** 格式，可直接用於由 LabelMe 建立的資料集。
*   **匯出支援**：支援將標註結果導出為 YOLO 格式 (TXT) 與 COCO 格式 (JSON)。
*   **大圖支援**：優化的渲染引擎，可流暢瀏覽與縮放高解析度影像。

## 📦 安裝與執行

### 環境需求
*   Python 3.8+
*   wxCvModule (核心渲染庫)

### 快速開始

1.  **安裝依賴**
    ```bash
    pip install wxcvmodule
    pip install -r requirements.txt
    ```

2.  **執行主程式**
    ```bash
    python main.py
    ```

## 🛠️ 操作說明

*   **左鍵**：繪製、選取與編輯物件。
*   **右鍵**：開啟功能選單 (刪除、屬性設定)。
*   **滾輪**：縮放影像。
*   **中鍵 (或按住空白鍵)**：平移影像。
*   **S 鍵**：切換為選取模式 (Select Mode)。

---
*Maintained by wxCvRoot Organization*
