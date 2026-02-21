[English](../README.md) | [繁體中文](README_zh-TW.md)

# wxCvAnnotator

**工業級 AI 輔助圖像標註工具**

wxCvAnnotator 是一款基於 **wxPython** 與 **C++ OpenCV 引擎 (wxCvModule)** 構建的高效標註工具，針對工業視覺場景優化，提供高解析度大圖的流暢操作以及 AI 輔助標註能力。

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/wxCvRoot/wxCvAnnotator)

---

## ✨ 功能特色

### 核心標註工具

提供多種幾何形狀繪製功能，適用於各種電腦視覺任務：

| 工具 | 說明 | 適用任務 |
|------|------|---------|
| **矩形 (Rectangle)** | 標準邊界框 | 物件偵測 (Detection) |
| **旋轉矩形 (Rotated Rect)** | 帶角度的矩形框 | 工業檢測 (AOI)、OBB |
| **多邊形 (Polygon)** | 任意形狀輪廓 | 實例分割 (Segmentation) |
| **圓形 (Circle) / 環形 (Annulus)** | 圓形與環形標註 | 幾何特徵標註 |
| **點 (Point)** | 單點關鍵點 | 姿態估計 (Pose Estimation) |

### AI 輔助標註

整合主流深度學習模型，大幅加速標註作業：

- **Segment Anything (SAM / SAM 2 / EfficientSAM)**：點選物件即可自動生成精確的遮罩與多邊形輪廓，首次使用時自動從 HuggingFace 下載 ONNX 量化模型（40 MB～600 MB）。

### 資料格式與管理

- **儲存格式**：預設使用 **LabelMe JSON**（每張圖片對應一個 `.json`），可直接用於既有 LabelMe 資料集。
- **匯出格式**：支援 YOLO TXT、COCO JSON、Pascal VOC XML、CSV。
- **標籤管理**：支援三層級載入（專案 → 全域 → 預設）、自定義顏色、批次重新命名 (Batch Rename)。
- **屬性面板**：為每個標註添加 `flags`（布林屬性）、自定義 key-value 屬性與轉錄文字 (transcription)。

### 介面與體驗

- **大圖支援**：C++ 渲染引擎針對高解析度影像優化，縮放與瀏覽流暢。
- **三欄佈局**：工具欄（左）→ 畫布（中）→ 實例清單（右），直覺清晰。
- **可調整面板**：拖曳分隔線自由調整各區塊寬度，設定自動記憶。
- **多語系**：介面支援 **繁體中文**、**英文**、**日文** 切換。
- **主題切換**：內建淺色 / 深色主題，支援自定義色彩方案。

---

## 📦 安裝說明

### 前置條件

所有平台都需要先安裝 **wxCvModule**（C++ 核心渲染引擎）：

```bash
# 從 PyPI 安裝（若有支援的 wheel）
pip install wxcvmodule

# 或從 Releases 頁面下載對應平台的 wheel 手動安裝
pip install wxcvmodule-*.whl
```

> wxCvModule 是預編譯的 C++ 擴充套件，若未安裝，程式會進入 Mock 模式（部分渲染功能停用，但基礎 UI 仍可啟動）。

---

### Windows 安裝

**測試環境**：Windows 10/11 x64

**1. 安裝 Python 3.10+**

從 [python.org](https://www.python.org/downloads/) 下載安裝，務必勾選 **Add Python to PATH**。

**2. 安裝 wxCvModule**

```cmd
pip install wxcvmodule
```

**3. 安裝 wxCvAnnotator**

```cmd
pip install wxcvannotator
```

**4. 啟動**

```cmd
wxcv-annotator
```

> **NVIDIA GPU 加速**（可選）：
> ```cmd
> pip install onnxruntime-gpu
> ```

---

### macOS 安裝

**測試環境**：macOS arm64 (Apple Silicon)，Python 3.12

**1. 安裝 pyenv（建議）**

```bash
brew install pyenv
```

在 `~/.zshrc` 加入：

```bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

**2. 安裝 Python 3.12**

```bash
pyenv install 3.12.12
pyenv local 3.12.12
```

**3. 安裝 wxCvModule**

```bash
pip install wxcvmodule
# 若 PyPI 無 macOS wheel，請從 Releases 頁面手動下載：
pip install wxcvmodule-*.macosx-*.whl
```

**4. 安裝並啟動**

```bash
pip install wxcvannotator
wxcv-annotator
```

> **macOS 注意事項**：
> - 啟動時終端可能出現 `objc[] duplicate class` 警告，屬已知問題，**不影響功能**，可忽略。
> - 請勿直接在 shell 執行 `python -c "import wxCvModule"`，請透過 `wxcv-annotator` 正常啟動。

---

### Linux 安裝

**測試環境**：Ubuntu 22.04 x64

**1. 安裝系統依賴**

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-pip python3-dev \
    libgtk-3-dev libgl1-mesa-glx libglib2.0-0
```

**2. 安裝 wxCvModule**

```bash
pip install wxcvmodule
```

**3. 安裝並啟動**

```bash
pip install wxcvannotator
wxcv-annotator
```

> **NVIDIA CUDA GPU 加速**（可選）：
> ```bash
> pip install onnxruntime-gpu
> ```

---

### 開發者安裝

```bash
git clone https://github.com/wxCvRoot/wxCvAnnotator.git
cd wxCvAnnotator
pip install -e .
wxcv-annotator
```

---

### 啟動方式總覽

```bash
wxcv-annotator                        # 標準啟動（安裝後）
wxcv-annotator /path/to/image.jpg    # 直接開啟指定圖片
wxcv-annotator /path/to/folder/      # 開啟資料夾
python -m wxcvannotator              # Module 模式
python main.py                       # 開發用啟動器
```

---

### 快速驗證安裝

```bash
python -c "
import wx; print(f'wxPython: {wx.version()}')
import numpy; print(f'numpy: {numpy.__version__}')
import cv2; print(f'opencv: {cv2.__version__}')
try:
    import onnxruntime; print(f'onnxruntime: {onnxruntime.__version__}')
except ImportError:
    print('onnxruntime: 未安裝（AI 功能停用）')
import wx; import wxCvModule; print('wxCvModule: OK')
import wxcvannotator; print(f'wxcvannotator: {wxcvannotator.__version__}')
"
```

---

## 🔄 基本操作流程

1. **開啟圖片**：從選單 `File > Open Image` 或 `File > Open Folder` 開啟，也可直接拖曳圖片至視窗。
2. **選擇工具**：從左側工具欄點選標註工具（矩形、多邊形、旋轉矩形等）。
3. **繪製**：在圖像上點選或拖曳完成繪製。
4. **加入清單**：繪製完成後按 **Enter** 或點擊工具欄的 **[➕ Add]**，在彈出的對話框設定類別後確認。
5. **編輯**：從右側清單點選標註，在畫布上調整後按 **Enter** 更新。
6. **屬性**：選取標註後，底部面板可編輯 flags、自定義屬性與轉錄文字。
7. **自動存檔**：標註自動存為與圖片同名的 `.json` 檔案（LabelMe 格式）。

---

## 🤖 AI 輔助標註使用教學

### 使用流程

1. 點選左側工具欄的 **AI Polygon** 或 **AI Mask** 工具。
2. 從工具欄下方的 **Model** 下拉選單選擇模型：
   - **EfficientSAM**：速度優先，適合即時標註。
   - **SAM / SAM 2**：精度優先，適合複雜邊界。
3. 在圖像上點選提示點：
   - **左鍵**：添加正向提示（綠點），包含此區域。
   - **右鍵**：添加負向提示（紅點），排除此區域。
   - **Backspace**：撤銷最後一個提示點。
4. 即時預覽：點選後即時顯示預測多邊形。
5. **完成**：
   - 按 **Enter** 或**左鍵雙擊**：確認並加入清單。
   - **右鍵雙擊**：撤銷最後一個提示點。

> **首次使用**：選擇模型後首次點選時，程式會自動從 HuggingFace 下載 ONNX 量化模型，請確保網路連線正常。下載進度會顯示在狀態列。

---

## 📤 資料集匯出

### 單張圖片匯出

前往 **Export > Export Current Image...**，選擇目標格式後確認，檔案將儲存於圖片所在目錄。

### 資料集分割匯出

前往 **Export > Export Dataset (Split)...**，可進行以下設定：

- **依手動標記分割**：勾選後，已在清單中標記為 `train/val/test` 的圖片將優先按標記分配。
- **調整比例**：對未手動標記的圖片，使用滑桿設定 train/val/test 的隨機分配比例。
- **複製原圖**：選擇是否將圖片一併複製，生成可獨立使用的資料集目錄。

**支援格式**：

| 格式 | 說明 |
|------|------|
| YOLO TXT | 適用於 YOLOv5/v8/v11，支援 det / seg / obb |
| COCO JSON | 通用的 COCO 格式，支援偵測與分割 |
| Pascal VOC XML | 傳統 XML 格式，適用於 Detectron2 等框架 |
| CSV | 輕量通用格式，方便自定義處理 |

---

## ⌨️ 快捷鍵總覽

| 按鍵 | 功能 |
|------|------|
| `S` | 切換為選取 / 編輯模式 |
| `P` | 多邊形工具 |
| `R` | 旋轉矩形工具 |
| `Enter` | 新增 / 更新標註 |
| `Esc` | 取消目前繪製 |
| `Delete` | 刪除選取的標註 |
| 滾輪 | 縮放影像 |
| 中鍵 / 按住空白鍵 | 平移影像 |
| 左鍵雙擊 (AI 模式) | 確認 AI 預測並加入 |
| 右鍵雙擊 (AI 模式) | 撤銷最後一個提示點 |

---

## 🛠️ 系統需求

| 項目 | 最低需求 |
|------|---------|
| Python | 3.10+ |
| wxPython | 4.2.0+ |
| 作業系統 | Windows 10+、macOS 12+、Ubuntu 20.04+ |
| 記憶體 | 4 GB RAM（AI 功能建議 8 GB+） |
| 磁碟 | 基本安裝 < 100 MB；AI 模型額外 40 MB～600 MB |

---

## 🔗 常見問題

**Q: 安裝後找不到 `wxcv-annotator` 指令？**
> 確認 Python Scripts 目錄已加入 PATH。Windows 使用者可嘗試 `python -m wxcvannotator`。

**Q: 啟動時出現 `ModuleNotFoundError: No module named 'wx'`？**
> ```bash
> pip install wxPython
> ```

**Q: AI 標註功能無法使用？**
> 確認已安裝 `onnxruntime`：
> ```bash
> pip install onnxruntime      # CPU
> pip install onnxruntime-gpu  # NVIDIA GPU
> ```

**Q: 程式啟動出現「Mock 模式」警告？**
> 表示 `wxCvModule` 未正確安裝，請確認已安裝對應平台的 wheel：
> ```bash
> pip show wxcvmodule
> ```

**Q: macOS 上出現 `objc[] duplicate class` 警告？**
> 此為已知問題（`cv2` 與 `wxCvModule` 各自內嵌 OpenCV 動態庫），**不影響功能**，可忽略。

---

## ⚖️ 授權

本專案採用 **Apache License 2.0**。

Copyright 2026 [wxCvRoot](https://github.com/wxCvRoot)

詳細授權條款請參閱 [LICENSE](LICENSE) 文件。

本專案使用以下開源組件：
- [OpenCV](https://opencv.org/) — Apache 2.0
- [wxWidgets](https://www.wxwidgets.org/) — wxWindows Licence
- [Segment Anything (SAM)](https://github.com/facebookresearch/segment-anything) — Apache 2.0
- [EfficientSAM](https://github.com/yformer/EfficientSAM) — Apache 2.0

---

*Maintained by [wxCvRoot](https://github.com/wxCvRoot)*
