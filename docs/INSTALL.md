# wxCvAnnotator 安裝指南

> **最後更新：2026-02-25** — linux add ocr service

## 目錄

- [系統需求](#系統需求)
- [安裝模式](#安裝模式)
- [macOS 安裝](#macos-安裝)
- [Windows 安裝](#windows-安裝)
- [Linux 安裝](#linux-安裝)
- [選擇性功能安裝](#選擇性功能安裝)
- [常見問題](#常見問題)

---

## 系統需求

| 項目 | 最低需求 |
|------|---------|
| Python | 3.10+ |
| wxPython | 4.2.0+ |
| 作業系統 | macOS 12+、Windows 10+、Ubuntu 20.04+ |
| 記憶體 | 4 GB RAM（AI 功能建議 8 GB+） |

---

## 安裝模式

本專案支援兩種使用方式：

| 模式 | 適用對象 | 安裝指令 | 啟動方式 |
|------|---------|---------|---------|
| **使用者安裝** | 一般使用者 | `pip install wxcvannotator` | `wxcv-annotator` |
| **開發者安裝** | 貢獻者／開發 | `git clone` + `pip install -e .` | `wxcv-annotator` 或 `python main.py` |

> **共同前提**：兩種模式都需要先安裝 wxCvModule（C++ 核心引擎）。

---

## macOS 安裝

> **測試環境**：macOS 25.3 (arm64 / Apple Silicon)，pyenv Python 3.12.12

### 1. 安裝 pyenv（若尚未安裝）

```bash
brew install pyenv
```

在 `~/.zshrc` 加入：

```bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

### 2. 安裝 Python 3.12

```bash
pyenv install 3.12.12
pyenv global 3.12.12   # 或 pyenv local 3.12.12（僅限本專案目錄）
```

### 3. 安裝 wxCvModule（C++ 核心引擎）

wxCvModule 是預編譯的 C++ 擴充套件，需從發布頁面下載對應平台的 wheel：

```bash
pip install wxcvmodule-*.macosx-*.whl
```

> 若 `pip install wxcvmodule` 在 PyPI 上找不到 macOS wheel，請從專案 Releases 頁面手動下載。

### 4a. 使用者安裝

```bash
pip install wxcvannotator
```

安裝完成後直接執行：

```bash
wxcv-annotator
wxcv-annotator /path/to/image.jpg
wxcv-annotator /path/to/folder/
```

### 4b. 開發者安裝

```bash
git clone https://github.com/wxCvRoot/wxCvAnnotator.git
cd wxCvAnnotator
pip install -e .
```

`-e`（editable mode）安裝後，對原始碼的修改立即生效，無需重新安裝。

啟動方式：

```bash
wxcv-annotator                    # entry point（推薦）
python -m wxcvannotator           # module 模式
python main.py                    # 開發用薄啟動器
```

---

### macOS 已知注意事項

#### wxCvModule 載入順序

wxCvModule 在 macOS 上需要 wxPython 先完成初始化才能正確解析 C++ 符號。
程式的 import 順序已正確處理此問題，**請勿在 shell 中單獨** `import wxCvModule`：

```bash
# 錯誤 — 會產生 symbol not found 錯誤
python3 -c "import wxCvModule"

# 正確
python3 -c "import wx; import wxCvModule"
```

透過 `wxcv-annotator` 或 `python main.py` 正常啟動時不受此問題影響。

#### objc[] duplicate class 警告

啟動時終端可能出現：

```
objc[...]: Class AVFFrameReceiver is implemented in both ...
```

這是 `cv2` 與 wxCvModule 各自內嵌 OpenCV dylib 產生的衝突，屬已知問題（REQ-012），**不影響功能**，可忽略。

#### wxCvModule 未找到時的 Mock 模式

若 wxCvModule 未安裝，程式會顯示警告並進入 mock 模式，部分 C++ 渲染功能無法使用，但 Python UI 仍可啟動：

```
⚠️  Warning: Cannot find wxCvModule lib in: .../wxcvannotator/lib
   Running in mock mode...
```

#### 首次使用 AI 功能

AI 標註（SAM / EfficientSAM）模型在首次使用時從 HuggingFace 自動下載（40 MB～600 MB），請確保網路連線正常。

---

## Windows 安裝

> **測試環境**：Windows 10/11 x64

### 1. 安裝 Python 3.12

從 [python.org](https://www.python.org/downloads/) 下載安裝，勾選 **Add Python to PATH**。

### 2. 安裝 wxCvModule

```cmd
pip install wxcvmodule-*.win-amd64.whl
```

> 或將 `wxCvModule.pyd` 及相關 DLL 放入 `wxcvannotator/lib/`（開發者模式才需要此目錄）。

### 3a. 使用者安裝

```cmd
pip install wxcvannotator
wxcv-annotator
```

### 3b. 開發者安裝

```cmd
git clone https://github.com/wxCvRoot/wxCvAnnotator.git
cd wxCvAnnotator
pip install -e .
wxcv-annotator
```

> **GPU 加速（NVIDIA）**：
> ```cmd
> pip install onnxruntime-gpu
> ```

---

## Linux 安裝

> **測試環境**：Ubuntu 22.04 x64

### 1. 安裝系統依賴

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-pip python3-dev \
    libgtk-3-dev libgl1-mesa-glx libglib2.0-0
```

### 2. 安裝 wxCvModule

```bash
pip install wxcvmodule-*.manylinux*.whl
```

### 3a. 使用者安裝

```bash
pip install wxcvannotator
wxcv-annotator
```

### 3b. 開發者安裝

```bash
git clone https://github.com/wxCvRoot/wxCvAnnotator.git
cd wxCvAnnotator
pip install -e .
wxcv-annotator
```

> **GPU 加速（NVIDIA CUDA）**：
> ```bash
> pip install onnxruntime-gpu
> ```

---

---

## 選擇性功能安裝

wxCvAnnotator 核心功能（標註、編輯、匯出）安裝後即可使用，無需額外套件。
AI 相關功能可依需求選擇性安裝，不影響主程式運作。

### AI 輪廓標註（SAM / EfficientSAM）

使用 ONNX Runtime 推論，**已包含在核心依賴中**（`onnxruntime`），安裝主程式後即可使用。
模型在首次點擊「AI 標註」時自動從 HuggingFace 下載（40 MB – 600 MB）。

```bash
# GPU 加速（NVIDIA）
pip install onnxruntime-gpu
```

### AI OCR 文字識別（VLM 後端）

使用大型語言視覺模型（Qwen3-VL、InternVL3、GOT-OCR2.0 等），需額外安裝依賴。
模型在首次使用時自動從 HuggingFace 下載（1.4 GB – 8 GB）。

> **注意**：安裝前必須先安裝 PyTorch（選擇符合你的 CUDA 版本）。
> OCR 功能**不安裝也不影響**標註與 AI 輪廓功能。

#### 步驟 1：安裝 PyTorch

選擇符合你的 CUDA 版本（從 [pytorch.org](https://pytorch.org/get-started/locally/) 查詢指令）：

```bash
# CUDA 12.1（最常見，NVIDIA GTX/RTX 20xx–40xx）
pip install torch --index-url https://download.pytorch.org/whl/cu121

# CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118

# CPU only（無 GPU 或 Mac）
pip install torch
```

> macOS Apple Silicon 使用者：`pip install torch` 即可（MPS 加速內建）。

#### 步驟 2：安裝 OCR 套件

```bash
pip install "wxcvannotator[ocr]"
```

此指令安裝所有 VLM 後端所需套件：

| 套件 | 用途 | 使用的後端 |
|------|------|-----------|
| `transformers>=4.50` | 模型載入與推論 | 全部 VLM |
| `Pillow>=9.0` | 影像處理 | 全部 VLM |
| `accelerate>=0.26` | 4-bit 量化所需 | Qwen 系列 |
| `bitsandbytes>=0.43` | 4-bit 量化（低 VRAM GPU）| Qwen 系列 |
| `qwen-vl-utils` | Qwen2.5-VL 影像前處理 | Qwen2.5-VL |
| `tiktoken` | GOT-OCR2.0 tokenizer | GOT-OCR2.0 |
| `verovio` | GOT-OCR2.0 格式輸出 | GOT-OCR2.0 |
| `sentencepiece` | InternVL3 tokenizer | InternVL3 |

#### 關於 PaddleOCR

PaddleOCR 是獨立的深度學習框架（非 PyTorch），安裝相依套件較多。
目前在 Linux + CUDA 12 環境下有已知推論問題（GTX 10xx，輸出全零），**待 Windows 驗證通過後加入**。
目前版本尚未整合，敬請期待。

#### VRAM 需求參考

| 後端 | 磁碟 | VRAM（推論） | 最低 GPU |
|------|------|------------|---------|
| GOT-OCR2.0 | 1.4 GB | ~1.4 GB (fp16) | GTX 1060 6GB |
| Qwen3-VL-2B | ~4 GB | ~1.7 GB (4-bit) | GTX 1060 6GB |
| Qwen2.5-VL-3B | 7.5 GB | ~2.5 GB (4-bit) | GTX 1060 6GB |
| Qwen3-VL-4B | ~8.3 GB | ~3.1 GB (4-bit) | GTX 1060 6GB |
| InternVL3-2B | ~4 GB | ~4.2 GB (bf16) | RTX 3060 8GB+ |

> 若無 NVIDIA GPU，所有 VLM 後端均可使用 CPU 推論，但速度會慢 20–100 倍。

---

## 常見問題

### `ModuleNotFoundError: No module named 'wx'`

```bash
pip install wxPython
```

---

### `ImportError: dlopen ... symbol not found in flat namespace '__ZN11wxScrollBar...'`

macOS 上未先載入 wxPython 直接 import wxCvModule 的問題，透過正常啟動指令不會觸發。
詳見 [macOS 已知注意事項](#wxcvmodule-載入順序)。

---

### `ModuleNotFoundError: No module named 'yaml'`

```bash
pip install PyYAML
```

---

### `ModuleNotFoundError: No module named 'onnxruntime'`

AI 功能所需，無此套件時 AI 標註將停用：

```bash
pip install onnxruntime          # CPU
pip install onnxruntime-gpu      # NVIDIA GPU（Linux/Windows）
```

---

### wxCvModule 未找到（Mock 模式警告）

確認 wxCvModule 已正確安裝（`pip show wxcvmodule`），並確認使用對應平台的預編譯版本。

---

## 快速驗證安裝

```bash
python3 -c "
import wx; print(f'wxPython: {wx.version()}')
import numpy; print(f'numpy: {numpy.__version__}')
import cv2; print(f'opencv: {cv2.__version__}')
import yaml; print('PyYAML: OK')
import requests; print('requests: OK')
try:
    import onnxruntime; print(f'onnxruntime: {onnxruntime.__version__}')
except ImportError:
    print('onnxruntime: NOT installed (AI features disabled)')
import wx; import wxCvModule; print('wxCvModule: OK')
import wxcvannotator; print(f'wxcvannotator: {wxcvannotator.__version__}')
"
```
