#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR Service — multi-backend text recognition.

Backends:
  VLM (require torch + transformers):
    Qwen2.5-VL-3B, Qwen3-VL-2B, Qwen3-VL-4B, InternVL3-2B, GOT-OCR2.0
  ONNX (require onnxruntime only — no torch, no paddle):
    PPOCRv5-Mobile, PPOCRv5-Server

Optional install (install PyTorch first for your CUDA version):
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install "wxcvannotator[ocr]"

Two modes:
    Mode 1 — recognize_full(image_bgr)  → List[OCRResult]  (with bbox where supported)
    Mode 2 — recognize_roi(roi_bgr)     → str              (transcription for an annotation)

Usage:
    svc = OCRService()
    print(OCRService.available_backends())   # ['Qwen3-VL-2B', ...]
    svc.set_backend('Qwen3-VL-2B')
    text = svc.recognize_roi(roi_crop_bgr)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Type
import logging
import re
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Package root: wxcvannotator/utils/ → wxcvannotator/
_PACKAGE_ROOT = Path(__file__).parent.parent
_DEFAULT_MODEL_DIR = _PACKAGE_ROOT / 'models'

# ---------------------------------------------------------------------------
# Optional dependency probes (mirror ai_service.py pattern)
# ---------------------------------------------------------------------------

import importlib.util

def _has_package(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False

# Global flags for lazy loading
_torch = None
_tfm = None
_ort = None
_PILImage = None

def _get_torch():
    global _torch
    if _torch is None:
        try:
            import torch
            _torch = torch
        except ImportError:
            pass
    return _torch

def _is_torch_available():
    return _has_package("torch")

def _get_transformers():
    global _tfm
    if _tfm is None:
        try:
            import transformers
            _tfm = transformers
        except ImportError:
            pass
    return _tfm

def _is_transformers_available():
    return _has_package("transformers")

def _is_bnb_available():
    return _has_package("bitsandbytes")

def _is_accelerate_available():
    return _has_package("accelerate")

def _get_pil_image():
    global _PILImage
    if _PILImage is None:
        try:
            from PIL import Image
            _PILImage = Image
        except ImportError:
            pass
    return _PILImage

def _is_pil_available():
    return _has_package("PIL")

def _is_qwen_vl_utils_available():
    return _has_package("qwen_vl_utils")

def _get_ort():
    global _ort
    if _ort is None:
        try:
            import onnxruntime
            _ort = onnxruntime
        except ImportError:
            pass
    return _ort

def _is_ort_available():
    return _has_package("onnxruntime")

# ---------------------------------------------------------------------------
# Public utility: 4-point perspective crop (used by PPOCRv5 and main_window)
# ---------------------------------------------------------------------------

def crop_polygon_for_ocr(img_bgr: np.ndarray, pts: List, pad: int = 5) -> Optional[np.ndarray]:
    """
    Perspective-warp a 4-point polygon annotation to an upright axis-aligned crop.

    Mirrors the verified get_rotate_crop_image() logic from PPOCRLabel:
      1. Green's theorem: if points are CCW (d < 0), swap P1↔P3 to normalise to CW.
      2. Perspective transform: P0→TL, P1→TR, P2→BR, P3→BL.
      3. If crop_h / crop_w >= 1.5 (tall strip), rotate 90° CCW (np.rot90 convention).

    pad: expand each corner outward from centroid by this many pixels (default 5)
         to add a small border around tight annotations.

    See docs/design/04_OCR_Annotation_Design.md for the annotation spec.
    Returns None when pts is invalid or the resulting crop is empty.
    """
    if pts is None or len(pts) != 4:
        return None
    src = np.array(pts, dtype=np.float32)

    # Green's theorem: compute signed area to detect CW vs CCW orientation.
    # In image coordinates (y-down): CW → d > 0, CCW → d < 0.
    # Source: PPOCRLabel / get_rotate_crop_image reference implementation.
    d = 0.0
    for i in range(-1, 3):
        d += -0.5 * (src[i + 1][1] + src[i][1]) * (src[i + 1][0] - src[i][0])
    if d < 0:  # CCW annotation — swap P1 and P3 to normalise to CW
        src[1], src[3] = src[3].copy(), src[1].copy()

    # Expand each corner outward from centroid to restore padding
    if pad > 0:
        cx, cy = src[:, 0].mean(), src[:, 1].mean()
        ih, iw = img_bgr.shape[:2]
        for i in range(4):
            dx, dy = src[i, 0] - cx, src[i, 1] - cy
            dist = np.sqrt(dx * dx + dy * dy)
            if dist > 0:
                src[i, 0] = np.clip(src[i, 0] + dx / dist * pad, 0, iw - 1)
                src[i, 1] = np.clip(src[i, 1] + dy / dist * pad, 0, ih - 1)

    crop_w = int(max(
        np.linalg.norm(src[0] - src[1]),   # P0→P1 (top edge width)
        np.linalg.norm(src[2] - src[3]),   # P2→P3 (bottom edge width)
    ))
    crop_h = int(max(
        np.linalg.norm(src[0] - src[3]),   # P0→P3 (left edge height)
        np.linalg.norm(src[1] - src[2]),   # P1→P2 (right edge height)
    ))
    if crop_w == 0 or crop_h == 0:
        return None

    dst = np.array([[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img_bgr, M, (crop_w, crop_h),
                                  borderMode=cv2.BORDER_REPLICATE,
                                  flags=cv2.INTER_CUBIC)

    rotated = crop_h / crop_w >= 1.5
    print(f"[crop_polygon_for_ocr] crop=({crop_w}×{crop_h})  d={d:.1f}  rotate90CCW={rotated}")
    if rotated:
        warped = np.rot90(warped)   # 90° CCW — matches np.rot90 / PPOCRLabel convention

    return warped


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class OCRResult:
    """A single OCR detection result."""
    text: str
    bbox: Optional[List[Tuple[float, float]]] = None  # 4-point polygon [[x,y],...]; None = no location
    confidence: float = -1.0
    line_id: int = -1
    word_id: int = -1

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class OCRBackend(ABC):
    """Abstract base class for all OCR backends."""

    def __init__(self, model_dir: Path):
        self._model_dir = model_dir
        self._model = None
        self._processor = None
        self._device: Optional[str] = None
        self._status_cb: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Status callback helpers (called from background thread)
    # ------------------------------------------------------------------

    def _status(self, msg: str) -> None:
        """Fire the status callback if one is registered."""
        if self._status_cb:
            self._status_cb(msg)

    @property
    def is_loaded(self) -> bool:
        """True if the model is already in memory (no load needed)."""
        return self._model is not None

    @staticmethod
    @abstractmethod
    def is_available() -> bool:
        """True if all required Python packages are installed."""
        ...

    @staticmethod
    def missing_packages() -> List[str]:
        """Return list of package names that are missing."""
        return []

    @abstractmethod
    def recognize_roi(self, roi_bgr: np.ndarray) -> str:
        """Mode 2: OCR a cropped annotation patch; return text string."""
        ...

    @abstractmethod
    def recognize_full(self, image_bgr: np.ndarray) -> List[OCRResult]:
        """Mode 1: OCR a full image; return results (with bbox if backend supports grounding)."""
        ...

    def unload(self) -> None:
        """Release model from GPU memory."""
        self._model = None
        self._processor = None
        torch = _get_torch()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.debug('%s unloaded.', self.__class__.__name__)

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _bgr_to_pil(bgr: np.ndarray):
    """Convert OpenCV BGR numpy array to PIL RGB Image."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return _get_pil_image().fromarray(rgb)


def _get_device() -> str:
    """Return 'cuda' or 'cpu'."""
    torch = _get_torch()
    if torch and torch.cuda.is_available():
        return 'cuda'
    return 'cpu'


def _get_vram_gb() -> float:
    """Return total VRAM of primary GPU in GB; 0 if no GPU."""
    torch = _get_torch()
    if torch and torch.cuda.is_available():
        return torch.cuda.get_device_properties(0).total_memory / 1e9
    return 0.0


def _parse_qwen_grounding(text: str, img_w: int, img_h: int) -> List[OCRResult]:
    """
    Parse Qwen grounding format: <ref>word</ref><box>[[x1,y1,x2,y2]]</box>
    Coordinates are normalized 0–1000; converts to pixel coordinates.
    """
    pattern = r'<ref>(.*?)</ref>\s*<box>\[\[(\d+),(\d+),(\d+),(\d+)\]\]</box>'
    results = []
    for m in re.finditer(pattern, text, re.DOTALL):
        word = m.group(1).strip()
        if not word:
            continue
        x1 = int(m.group(2)) * img_w / 1000.0
        y1 = int(m.group(3)) * img_h / 1000.0
        x2 = int(m.group(4)) * img_w / 1000.0
        y2 = int(m.group(5)) * img_h / 1000.0
        bbox = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        results.append(OCRResult(text=word, bbox=bbox))
    return results


def _ensure_model_dir(repo_id: str, local_dir: Path) -> bool:
    """
    Check if model is already downloaded; if not, download from HuggingFace.
    Returns True if the model is available locally after the call.
    """
    if (local_dir / 'config.json').exists():
        return True
    logger.info('Model not found at %s — downloading %s ...', local_dir, repo_id)
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id, local_dir=str(local_dir))
        logger.info('Download complete: %s', local_dir)
        return True
    except Exception as exc:
        logger.error('Failed to download %s: %s', repo_id, exc)
        return False

# ---------------------------------------------------------------------------
# GOT-OCR2.0 Backend
# ---------------------------------------------------------------------------

class GOTOCRBackend(OCRBackend):
    """
    GOT-OCR2.0 (stepfun-ai/GOT-OCR-2.0-hf).
    Lightweight (~1.4 GB VRAM fp16). Best for clean single-word / single-line patches.
    Weakness: hallucination on complex backgrounds; small images need 4x upscale.
    Mode 1 returns plain text only (no reliable grounding bbox).
    """

    REPO_ID = 'stepfun-ai/GOT-OCR-2.0-hf'
    MODEL_SUBDIR = 'GOT-OCR2_0'

    @staticmethod
    def is_available() -> bool:
        return (_is_torch_available() and _is_transformers_available()
                and _is_pil_available() and _has_package("tiktoken") 
                and _has_package("verovio"))

    @staticmethod
    def missing_packages() -> List[str]:
        missing = []
        if not _is_torch_available():          missing.append('torch')
        if not _is_transformers_available():   missing.append('transformers>=4.50')
        if not _is_pil_available():            missing.append('Pillow')
        if not _has_package("tiktoken"):       missing.append('tiktoken')
        if not _has_package("verovio"):        missing.append('verovio')
        return missing

    def _load(self) -> bool:
        if self._model is not None:
            return True
        model_dir = self._model_dir / self.MODEL_SUBDIR
        if not (model_dir / 'config.json').exists():
            self._status(f"Downloading {self.MODEL_SUBDIR}...")
        if not _ensure_model_dir(self.REPO_ID, model_dir):
            return False
        self._status(f"Loading {self.MODEL_SUBDIR} into memory...")
        try:
            from transformers import GotOcr2ForConditionalGeneration, GotOcr2Processor
            device = _get_device()
            self._device = device
            logger.info('Loading GOT-OCR2.0 on %s ...', device)
            t0 = time.time()
            self._processor = GotOcr2Processor.from_pretrained(str(model_dir), use_fast=True)
            torch = _get_torch()
            self._model = GotOcr2ForConditionalGeneration.from_pretrained(
                str(model_dir),
                dtype=torch.float16,
                device_map=device,
            ).eval()
            logger.info('GOT-OCR2.0 loaded in %.1fs', time.time() - t0)
            return True
        except Exception as exc:
            logger.error('GOT-OCR2.0 load failed: %s', exc)
            self._model = self._processor = None
            return False

    def _infer_pil(self, pil_image, max_new_tokens: int = 256) -> str:
        inputs = self._processor(pil_image, return_tensors='pt')
        torch = _get_torch()
        inputs = {k: v.to(self._device, torch.float16) if (hasattr(v, 'to') and v.is_floating_point())
                  else v.to(self._device) if hasattr(v, 'to') else v
                  for k, v in inputs.items()}
        with torch.no_grad():
            ids = self._model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=max_new_tokens,
                repetition_penalty=1.3,
            )
        full = self._processor.decode(ids[0], skip_special_tokens=True)
        # Strip the echoed prompt — only keep what comes after "assistant\n"
        return full.split('assistant\n', 1)[-1].strip()

    def recognize_roi(self, roi_bgr: np.ndarray) -> str:
        if not self._load():
            return ''
        try:
            img = _bgr_to_pil(roi_bgr)
            w, h = img.size
            # Upscale tiny images to avoid repetition artifacts
            if min(w, h) < 64:
                scale = 64 / min(w, h)
                img = img.resize((int(w * scale), int(h * scale)), _get_pil_image().LANCZOS)
            return self._infer_pil(img, max_new_tokens=32)
        except Exception as exc:
            logger.error('GOT-OCR2.0 recognize_roi failed: %s', exc)
            return ''

    def recognize_full(self, image_bgr: np.ndarray) -> List[OCRResult]:
        if not self._load():
            return []
        try:
            img = _bgr_to_pil(image_bgr)
            text = self._infer_pil(img, max_new_tokens=512)
            return [OCRResult(text=text, bbox=None)] if text else []
        except Exception as exc:
            logger.error('GOT-OCR2.0 recognize_full failed: %s', exc)
            return []

# ---------------------------------------------------------------------------
# Qwen2.5-VL Backend
# ---------------------------------------------------------------------------

class QwenVLBackend(OCRBackend):
    """
    Qwen2.5-VL-3B (Qwen/Qwen2.5-VL-3B-Instruct).
    Best quality; supports grounding bbox for Mode 1.
    Auto 4-bit quantization when VRAM < 7 GB (requires bitsandbytes + accelerate).
    Requires: torch, transformers, Pillow, qwen-vl-utils.
    """

    REPO_ID = 'Qwen/Qwen2.5-VL-3B-Instruct'
    MODEL_SUBDIR = 'Qwen2.5-VL-3B-Instruct'

    _MODE1_PROMPT = (
        'Detect all text in this image. '
        'For each text region output: <ref>text content</ref><box>[[x1,y1,x2,y2]]</box> '
        'Output only the structured results, no explanation.'
    )
    _MODE2_PROMPT = (
        'What text appears in this image? '
        'Output only the text content, preserving line breaks. No explanation.'
    )

    @staticmethod
    def is_available() -> bool:
        return (_is_torch_available() and _is_transformers_available()
                and _is_pil_available() and _is_qwen_vl_utils_available())

    @staticmethod
    def missing_packages() -> List[str]:
        missing = []
        if not _is_torch_available():           missing.append('torch')
        if not _is_transformers_available():    missing.append('transformers>=4.50')
        if not _is_pil_available():             missing.append('Pillow')
        if not _is_qwen_vl_utils_available():   missing.append('qwen-vl-utils')
        return missing

    def _load(self) -> bool:
        if self._model is not None:
            return True
        model_dir = self._model_dir / self.MODEL_SUBDIR
        if not (model_dir / 'config.json').exists():
            self._status(f"Downloading {self.MODEL_SUBDIR}...")
        if not _ensure_model_dir(self.REPO_ID, model_dir):
            return False
        self._status(f"Loading {self.MODEL_SUBDIR} into memory...")
        try:
            from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
            device = _get_device()
            self._device = device
            vram_gb = _get_vram_gb()
            use_4bit = _is_bnb_available() and _is_accelerate_available() and device == 'cuda' and vram_gb < 7.0
            logger.info('Loading Qwen2.5-VL-3B on %s (4-bit=%s, VRAM=%.1f GB) ...',
                        device, use_4bit, vram_gb)
            t0 = time.time()
            self._processor = AutoProcessor.from_pretrained(str(model_dir))
            load_kw: dict = {'device_map': device}
            if use_4bit:
                load_kw['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True)
            else:
                torch = _get_torch()
                load_kw['torch_dtype'] = torch.float16
            self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                str(model_dir), **load_kw
            ).eval()
            logger.info('Qwen2.5-VL-3B loaded in %.1fs', time.time() - t0)
            return True
        except Exception as exc:
            logger.error('Qwen2.5-VL-3B load failed: %s', exc)
            self._model = self._processor = None
            return False

    def _infer(self, pil_image, prompt: str, max_new_tokens: int = 256) -> str:
        messages = [{'role': 'user', 'content': [
            {'type': 'image', 'image': pil_image},
            {'type': 'text',  'text': prompt},
        ]}]
        text_prompt = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = _process_vision_info(messages)
        inputs = self._processor(
            text=[text_prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors='pt',
        ).to(self._device)
        torch = _get_torch()
        with torch.no_grad():
            ids = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        response = self._processor.batch_decode(
            ids[:, inputs['input_ids'].shape[1]:], skip_special_tokens=True
        )[0]
        return response.strip()

    def recognize_roi(self, roi_bgr: np.ndarray) -> str:
        if not self._load():
            return ''
        try:
            return self._infer(_bgr_to_pil(roi_bgr), self._MODE2_PROMPT, max_new_tokens=128)
        except Exception as exc:
            logger.error('Qwen2.5-VL recognize_roi failed: %s', exc)
            return ''

    def recognize_full(self, image_bgr: np.ndarray) -> List[OCRResult]:
        if not self._load():
            return []
        try:
            h, w = image_bgr.shape[:2]
            text = self._infer(_bgr_to_pil(image_bgr), self._MODE1_PROMPT, max_new_tokens=512)
            results = _parse_qwen_grounding(text, w, h)
            if not results:
                plain = re.sub(r'<[^>]+>', '', text).strip()
                if plain:
                    results = [OCRResult(text=plain, bbox=None)]
            return results
        except Exception as exc:
            logger.error('Qwen2.5-VL recognize_full failed: %s', exc)
            return []

# ---------------------------------------------------------------------------
# Qwen3-VL Backend (shared logic for 2B / 4B)
# ---------------------------------------------------------------------------

class _Qwen3VLBackend(OCRBackend):
    """
    Qwen3-VL (2B or 4B). Newer than Qwen2.5-VL; no qwen-vl-utils needed.
    Grounding supported. Auto 4-bit when VRAM < MODEL_SIZE_B * 3.5 GB.
    Requires: torch, transformers, Pillow. bitsandbytes + accelerate for 4-bit.
    """

    REPO_ID: str       # set by subclass
    MODEL_SUBDIR: str  # set by subclass
    MODEL_SIZE_B: float  # nominal size in billions (for VRAM threshold)

    _MODE1_PROMPT = (
        'Detect all text in this image. '
        'For each text region output: <ref>text content</ref><box>[[x1,y1,x2,y2]]</box> '
        'Output only the structured results, no explanation.'
    )
    _MODE2_PROMPT = (
        'What text appears in this image? '
        'Output only the text content, preserving line breaks. No explanation.'
    )

    @staticmethod
    def is_available() -> bool:
        return _is_torch_available() and _is_transformers_available() and _is_pil_available()

    @staticmethod
    def missing_packages() -> List[str]:
        missing = []
        if not _is_torch_available():          missing.append('torch')
        if not _is_transformers_available():   missing.append('transformers>=4.50')
        if not _is_pil_available():            missing.append('Pillow')
        return missing

    def _load(self) -> bool:
        if self._model is not None:
            return True
        model_dir = self._model_dir / self.MODEL_SUBDIR
        if not (model_dir / 'config.json').exists():
            self._status(f"Downloading {self.MODEL_SUBDIR}...")
        if not _ensure_model_dir(self.REPO_ID, model_dir):
            return False
        self._status(f"Loading {self.MODEL_SUBDIR} into memory...")
        try:
            from transformers import Qwen3VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
            device = _get_device()
            self._device = device
            vram_gb = _get_vram_gb()
            threshold = self.MODEL_SIZE_B * 3.5
            use_4bit = (_is_bnb_available() and _is_accelerate_available()
                        and device == 'cuda' and vram_gb < threshold)
            logger.info('Loading %s on %s (4-bit=%s, VRAM=%.1f GB, threshold=%.0f GB) ...',
                        self.MODEL_SUBDIR, device, use_4bit, vram_gb, threshold)
            t0 = time.time()
            self._processor = AutoProcessor.from_pretrained(str(model_dir))
            load_kw: dict = {'device_map': device}
            if use_4bit:
                load_kw['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True)
            else:
                load_kw['torch_dtype'] = 'auto'
            self._model = Qwen3VLForConditionalGeneration.from_pretrained(
                str(model_dir), **load_kw
            ).eval()
            logger.info('%s loaded in %.1fs', self.MODEL_SUBDIR, time.time() - t0)
            return True
        except Exception as exc:
            logger.error('%s load failed: %s', self.MODEL_SUBDIR, exc)
            self._model = self._processor = None
            return False

    def _infer(self, pil_image, prompt: str, max_new_tokens: int = 256) -> str:
        messages = [{'role': 'user', 'content': [
            {'type': 'image', 'image': pil_image},
            {'type': 'text',  'text': prompt},
        ]}]
        inputs = self._processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors='pt',
        ).to(self._device)
        torch = _get_torch()
        with torch.no_grad():
            ids = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        response = self._processor.batch_decode(
            ids[:, inputs['input_ids'].shape[1]:], skip_special_tokens=True
        )[0]
        return response.strip()

    def recognize_roi(self, roi_bgr: np.ndarray) -> str:
        if not self._load():
            return ''
        try:
            return self._infer(_bgr_to_pil(roi_bgr), self._MODE2_PROMPT, max_new_tokens=128)
        except Exception as exc:
            logger.error('%s recognize_roi failed: %s', self.MODEL_SUBDIR, exc)
            return ''

    def recognize_full(self, image_bgr: np.ndarray) -> List[OCRResult]:
        if not self._load():
            return []
        try:
            h, w = image_bgr.shape[:2]
            text = self._infer(_bgr_to_pil(image_bgr), self._MODE1_PROMPT, max_new_tokens=512)
            results = _parse_qwen_grounding(text, w, h)
            if not results:
                plain = re.sub(r'<[^>]+>', '', text).strip()
                if plain:
                    results = [OCRResult(text=plain, bbox=None)]
            return results
        except Exception as exc:
            logger.error('%s recognize_full failed: %s', self.MODEL_SUBDIR, exc)
            return []


class Qwen3VL2BBackend(_Qwen3VLBackend):
    REPO_ID = 'Qwen/Qwen3-VL-2B-Instruct'
    MODEL_SUBDIR = 'Qwen3-VL-2B-Instruct'
    MODEL_SIZE_B = 2.0


class Qwen3VL4BBackend(_Qwen3VLBackend):
    REPO_ID = 'Qwen/Qwen3-VL-4B-Instruct'
    MODEL_SUBDIR = 'Qwen3-VL-4B-Instruct'
    MODEL_SIZE_B = 4.0

# ---------------------------------------------------------------------------
# InternVL3 Backend
# ---------------------------------------------------------------------------

class InternVL3Backend(OCRBackend):
    """
    InternVL3-2B-hf (OpenGVLab/InternVL3-2B-hf).
    MIT license; native HF (no trust_remote_code). bf16 ~4.2 GB VRAM.
    No grounding bbox — Mode 1 returns plain text only.
    Requires: torch, transformers, Pillow, sentencepiece.
    """

    REPO_ID = 'OpenGVLab/InternVL3-2B-hf'
    MODEL_SUBDIR = 'InternVL3-2B-hf'

    _MODE1_PROMPT = (
        'Read all text in this image. '
        'Output the text content preserving layout and line breaks. No explanation.'
    )
    _MODE2_PROMPT = (
        'What text appears in this image? '
        'Output only the text content. No explanation.'
    )

    @staticmethod
    def is_available() -> bool:
        return (_is_torch_available() and _is_transformers_available()
                and _is_pil_available() and _has_package("sentencepiece"))

    @staticmethod
    def missing_packages() -> List[str]:
        missing = []
        if not _is_torch_available():            missing.append('torch')
        if not _is_transformers_available():     missing.append('transformers>=4.50')
        if not _is_pil_available():              missing.append('Pillow')
        if not _has_package("sentencepiece"):    missing.append('sentencepiece')
        return missing

    def _load(self) -> bool:
        if self._model is not None:
            return True
        model_dir = self._model_dir / self.MODEL_SUBDIR
        if not (model_dir / 'config.json').exists():
            self._status(f"Downloading {self.MODEL_SUBDIR}...")
        if not _ensure_model_dir(self.REPO_ID, model_dir):
            return False
        self._status(f"Loading {self.MODEL_SUBDIR} into memory...")
        try:
            from transformers import AutoProcessor, AutoModelForImageTextToText
            device = _get_device()
            self._device = device
            logger.info('Loading InternVL3-2B on %s (bf16) ...', device)
            t0 = time.time()
            self._processor = AutoProcessor.from_pretrained(str(model_dir))
            # Limit tiles to prevent OOM on 6 GB GPU (default 12 tiles → OOM)
            if hasattr(self._processor, 'image_processor'):
                self._processor.image_processor.max_patches = 2
            torch = _get_torch()
            self._model = AutoModelForImageTextToText.from_pretrained(
                str(model_dir),
                torch_dtype=torch.bfloat16,
                device_map=device,
            ).eval()
            logger.info('InternVL3-2B loaded in %.1fs', time.time() - t0)
            return True
        except Exception as exc:
            logger.error('InternVL3 load failed: %s', exc)
            self._model = self._processor = None
            return False

    def _infer(self, pil_image, prompt: str, max_new_tokens: int = 256) -> str:
        # InternVL3 processor accepts PIL images via the "image" key
        messages = [{'role': 'user', 'content': [
            {'type': 'image', 'image': pil_image},
            {'type': 'text',  'text': prompt},
        ]}]
        inputs = self._processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors='pt',
        ).to(self._device, dtype=_get_torch().bfloat16)
        torch = _get_torch()
        with torch.no_grad():
            ids = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        response = self._processor.decode(
            ids[0, inputs['input_ids'].shape[1]:], skip_special_tokens=True
        )
        return response.strip()

    def recognize_roi(self, roi_bgr: np.ndarray) -> str:
        if not self._load():
            return ''
        try:
            return self._infer(_bgr_to_pil(roi_bgr), self._MODE2_PROMPT, max_new_tokens=128)
        except Exception as exc:
            logger.error('InternVL3 recognize_roi failed: %s', exc)
            return ''

    def recognize_full(self, image_bgr: np.ndarray) -> List[OCRResult]:
        if not self._load():
            return []
        try:
            text = self._infer(_bgr_to_pil(image_bgr), self._MODE1_PROMPT, max_new_tokens=512)
            return [OCRResult(text=text, bbox=None)] if text else []
        except Exception as exc:
            logger.error('InternVL3 recognize_full failed: %s', exc)
            return []

# ---------------------------------------------------------------------------
# PP-OCRv5 ONNX backend (no Paddle required)
# Reference: Class_ppocrv5_Infer.cpp (acvdlo project)
# ---------------------------------------------------------------------------

# ── PP-OCRv5 constants (match C++ Class_ppocrv5_Infer.h defaults) ──────────
_PPOCR_DET_MAX_SIDE  = 960
_PPOCR_DET_ALIGN     = 32
_PPOCR_DET_THRESH    = 0.3
_PPOCR_DET_BOX_THRESH = 0.6
_PPOCR_DET_UNCLIP    = 1.5
_PPOCR_DET_MAX_CANDS = 1000
_PPOCR_REC_H         = 48
_PPOCR_REC_W         = 320
# ImageNet normalization in BGR channel order (C++ mean[3] = {0.406,0.456,0.485})
_PPOCR_DET_MEAN_BGR = np.array([0.406, 0.456, 0.485], dtype=np.float32)
_PPOCR_DET_STD_BGR  = np.array([0.225, 0.224, 0.229], dtype=np.float32)

_PPOCR_MODEL_DIR = _PACKAGE_ROOT / 'models' / 'ppocrv5'
_PPOCR_DICT_PATH = _PPOCR_MODEL_DIR / 'ppocrv5_dict.txt'


class _PPOCRv5Backend(OCRBackend):
    """
    PP-OCRv5 ONNX dual-session backend (det + rec).

    Det model: DBNet++ — resize longest side to 960, ImageNet-BGR normalise → probability map.
    Rec model: CRNN+CTC — resize to h=48, pad to w=320, /255-0.5 → CTC logits.
    Character dict: 18383 entries; blank=0, char k → dict[k-1].

    Both Mobile and Server variants share identical preprocessing pipelines;
    only the ONNX model weights differ.
    """

    _VARIANT: str = ''   # overridden by subclasses: 'mobile' or 'server'

    def __init__(self, model_dir: Path):
        super().__init__(model_dir)
        self._det_sess = None
        self._rec_sess = None
        self._char_list: List[str] = []
        self._providers: List[str] = []

    # ── availability ────────────────────────────────────────────────────────

    @classmethod
    def _det_onnx_path(cls) -> Path:
        return _PPOCR_MODEL_DIR / f'PP-OCRv5_{cls._VARIANT}_det_infer' / f'ppocrv5_{cls._VARIANT}_det.onnx'

    @classmethod
    def _rec_onnx_path(cls) -> Path:
        return _PPOCR_MODEL_DIR / f'PP-OCRv5_{cls._VARIANT}_rec_infer' / f'ppocrv5_{cls._VARIANT}_rec.onnx'

    @classmethod
    def _models_exist(cls) -> bool:
        return (cls._det_onnx_path().exists()
                and cls._rec_onnx_path().exists()
                and _PPOCR_DICT_PATH.exists())

    @staticmethod
    def is_available() -> bool:
        return False  # overridden by subclasses

    @staticmethod
    def missing_packages() -> List[str]:
        return [] if _is_ort_available() else ['onnxruntime']

    # ── lazy load ────────────────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return self._rec_sess is not None

    def _load(self) -> bool:
        if self._rec_sess is not None:
            return True
        self._status(f"Loading PPOCRv5-{self._VARIANT}...")
        if not _is_ort_available():
            logger.error('PPOCRv5: onnxruntime not installed.')
            return False

        # Character dictionary
        try:
            self._char_list = _PPOCR_DICT_PATH.read_text(encoding='utf-8').splitlines()
            logger.info('PPOCRv5: dict loaded (%d chars)', len(self._char_list))
        except Exception as exc:
            logger.error('PPOCRv5: failed to load dict: %s', exc)
            return False

        # Provider: try CUDA → fallback CPU
        ort = _get_ort()
        providers = []
        if 'CUDAExecutionProvider' in ort.get_available_providers():
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        else:
            providers = ['CPUExecutionProvider']

        try:
            self._det_sess = ort.InferenceSession(
                str(self._det_onnx_path()), providers=providers)
            # Verify CUDA actually works with a tiny dummy forward pass
            dummy = np.zeros((1, 3, _PPOCR_DET_ALIGN, _PPOCR_DET_ALIGN), dtype=np.float32)
            self._det_sess.run(None, {'x': dummy})
            self._providers = providers
            logger.info('PPOCRv5-%s: det session on %s', self._VARIANT, providers[0])
        except Exception:
            # CUDA provider present but GPU incompatible (e.g. Pascal / CC<7.0)
            providers = ['CPUExecutionProvider']
            try:
                self._det_sess = ort.InferenceSession(
                    str(self._det_onnx_path()), providers=providers)
                self._providers = providers
                logger.info('PPOCRv5-%s: det session on CPU (CUDA fallback)', self._VARIANT)
            except Exception as exc:
                logger.error('PPOCRv5: failed to load det model: %s', exc)
                return False

        try:
            self._rec_sess = ort.InferenceSession(
                str(self._rec_onnx_path()), providers=self._providers)
            logger.info('PPOCRv5-%s: rec session on %s', self._VARIANT, self._providers[0])
        except Exception as exc:
            logger.error('PPOCRv5: failed to load rec model: %s', exc)
            self._det_sess = None
            return False

        return True

    def unload(self) -> None:
        self._det_sess = None
        self._rec_sess = None
        self._char_list = []
        logger.debug('PPOCRv5-%s unloaded.', self._VARIANT)

    # ── det preprocessing ────────────────────────────────────────────────────

    @staticmethod
    def _preprocess_det(img_bgr: np.ndarray):
        """Resize (longest side ≤ 960, align-32, no upscale), ImageNet-BGR normalize → NCHW."""
        src_h, src_w = img_bgr.shape[:2]
        ratio = min(_PPOCR_DET_MAX_SIDE / max(src_h, src_w), 1.0)
        res_h = max(int(round(src_h * ratio / _PPOCR_DET_ALIGN)) * _PPOCR_DET_ALIGN, _PPOCR_DET_ALIGN)
        res_w = max(int(round(src_w * ratio / _PPOCR_DET_ALIGN)) * _PPOCR_DET_ALIGN, _PPOCR_DET_ALIGN)

        resized = cv2.resize(img_bgr, (res_w, res_h)).astype(np.float32) / 255.0
        resized = (resized - _PPOCR_DET_MEAN_BGR) / _PPOCR_DET_STD_BGR
        nchw = resized.transpose(2, 0, 1)[None].astype(np.float32)
        return nchw, res_h, res_w, src_h, src_w

    # ── det postprocessing (DBPostProcess) ───────────────────────────────────

    @staticmethod
    def _box_score(seg_map: np.ndarray, cnt: np.ndarray) -> float:
        mask = np.zeros_like(seg_map, dtype=np.uint8)
        cv2.fillPoly(mask, [cnt], 255)
        region = seg_map[mask == 255]
        return float(region.mean()) if region.size else 0.0

    @staticmethod
    def _db_postprocess(prob_map: np.ndarray, res_h: int, res_w: int,
                        src_h: int, src_w: int) -> List[Tuple[np.ndarray, float]]:
        """
        DBPostProcess → list of (pts_4x2_int32, score) in original image coordinates.
        pts order from cv2.boxPoints(); use _crop_region() for correct orientation.
        """
        seg_map = prob_map[0, 0]
        binary  = ((seg_map > _PPOCR_DET_THRESH) * 255).astype(np.uint8)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        max_dim = max(res_w, res_h)
        scale_x = src_w / res_w
        scale_y = src_h / res_h
        boxes: List[Tuple[np.ndarray, float]] = []

        for cnt in contours[:_PPOCR_DET_MAX_CANDS]:
            if len(cnt) < 4:
                continue
            score = _PPOCRv5Backend._box_score(seg_map, cnt)
            if score < _PPOCR_DET_BOX_THRESH:
                continue

            area = cv2.contourArea(cnt)
            peri = cv2.arcLength(cnt, True)
            if peri < 1e-5:
                continue

            # Unclip: expand minAreaRect by distance on all sides (C++ approach)
            distance = area * _PPOCR_DET_UNCLIP / peri
            rect = cv2.minAreaRect(cnt)
            cx, cy = rect[0]
            rw, rh = rect[1]
            expanded = ((cx, cy), (rw + 2 * distance, rh + 2 * distance), rect[2])
            box_pts = cv2.boxPoints(expanded)

            # Clip to [0, max_dim] then scale back to original image coordinates
            box_pts[:, 0] = np.clip(np.round(box_pts[:, 0]), 0, max_dim)
            box_pts[:, 1] = np.clip(np.round(box_pts[:, 1]), 0, max_dim)
            box_pts[:, 0] = np.clip(np.round(box_pts[:, 0] * scale_x), 0, src_w)
            box_pts[:, 1] = np.clip(np.round(box_pts[:, 1] * scale_y), 0, src_h)
            pts = box_pts.astype(np.int32)

            # Skip degenerate boxes
            br = cv2.boundingRect(pts)
            if br[2] < 2 or br[3] < 2:
                continue

            boxes.append((pts, score))

        # Sort top-to-bottom, left-to-right (C++ sort criterion)
        boxes.sort(key=lambda item: (item[0][:, 1].mean() // 10, item[0][:, 0].mean()))
        return boxes

    # ── crop region ──────────────────────────────────────────────────────────

    @staticmethod
    def _crop_region(img_bgr: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """
        Perspective-warp 4-point det box to an upright crop.
        Uses x+y / x-y sorting because DBNet++ boxes have unknown corner order.
        (For user annotations use crop_polygon_for_ocr which trusts annotation order.)
        """
        s = pts[:, 0] + pts[:, 1]
        d = pts[:, 0] - pts[:, 1]
        ordered = np.array([
            pts[np.argmin(s)],   # TL
            pts[np.argmax(d)],   # TR
            pts[np.argmax(s)],   # BR
            pts[np.argmin(d)],   # BL
        ], dtype=np.float32)

        crop_w = int(max(
            np.linalg.norm(ordered[0] - ordered[1]),
            np.linalg.norm(ordered[3] - ordered[2]),
        ))
        crop_h = int(max(
            np.linalg.norm(ordered[0] - ordered[3]),
            np.linalg.norm(ordered[1] - ordered[2]),
        ))
        if crop_w == 0 or crop_h == 0:
            return np.zeros((_PPOCR_REC_H, _PPOCR_REC_W, 3), dtype=np.uint8)

        dst = np.array([[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(ordered, dst)
        warped = cv2.warpPerspective(img_bgr, M, (crop_w, crop_h))

        if crop_h > crop_w * 1.5:
            warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)

        return warped

    # ── rec preprocessing ────────────────────────────────────────────────────

    @staticmethod
    def _preprocess_rec(img_bgr: np.ndarray) -> np.ndarray:
        """
        Resize to h=REC_H (keep aspect ratio, clamp w to REC_W),
        zero-pad width to REC_W. Normalize: /255 - 0.5.
        Returns (1, 3, REC_H, REC_W) float32.
        """
        h, w = img_bgr.shape[:2]
        target_w = max(int(round(w * _PPOCR_REC_H / h)), 1) if h > 0 else 1
        target_w = min(target_w, _PPOCR_REC_W)

        resized = cv2.resize(img_bgr, (target_w, _PPOCR_REC_H)).astype(np.float32)
        padded = np.zeros((_PPOCR_REC_H, _PPOCR_REC_W, 3), dtype=np.float32)
        padded[:, :target_w, :] = resized
        padded = padded / 255.0 - 0.5
        return padded.transpose(2, 0, 1)[None].astype(np.float32)   # (1,3,48,320)

    # ── CTC greedy decode ─────────────────────────────────────────────────────

    def _ctc_decode(self, logits: np.ndarray) -> Tuple[str, float]:
        """
        CTC greedy decode. logits shape: (1, T, num_classes).
        blank=0, char k → char_list[k-1] (18383 entries, no prepended 'blank').
        Returns (text, avg_max_score_over_T).
        """
        data = logits[0]                       # (T, num_classes)
        T = data.shape[0]
        indices  = data.argmax(axis=-1)        # (T,)
        max_vals = data.max(axis=-1)           # (T,)

        text = ''
        prev = -1
        for t in range(T):
            idx = int(indices[t])
            if idx != prev and idx != 0:
                dict_idx = idx - 1
                if dict_idx < len(self._char_list):
                    text += self._char_list[dict_idx]
            prev = idx

        avg_score = float(max_vals.mean()) if T > 0 else 0.0
        return text, avg_score

    # ── public API ────────────────────────────────────────────────────────────

    def recognize_roi(self, roi_bgr: np.ndarray) -> str:
        """Mode 2: rec-only on annotation crop. No det is run."""
        if not self._load():
            return ''
        if roi_bgr is None or roi_bgr.size == 0:
            return ''
        try:
            tensor = self._preprocess_rec(roi_bgr)
            logits = self._rec_sess.run(None, {'x': tensor})[0]
            text, _ = self._ctc_decode(logits)
            return text
        except Exception as exc:
            logger.error('PPOCRv5-%s recognize_roi failed: %s', self._VARIANT, exc)
            return ''

    def recognize_full(self, image_bgr: np.ndarray) -> List[OCRResult]:
        """Mode 1: det → crop → rec pipeline; returns results with 4-point bbox."""
        if not self._load():
            return []
        if image_bgr is None or image_bgr.size == 0:
            return []
        try:
            nchw, res_h, res_w, src_h, src_w = self._preprocess_det(image_bgr)
            prob_map = self._det_sess.run(None, {'x': nchw})[0]
            boxes = self._db_postprocess(prob_map, res_h, res_w, src_h, src_w)
            logger.debug('PPOCRv5-%s: %d text region(s) detected', self._VARIANT, len(boxes))

            results: List[OCRResult] = []
            for pts, det_score in boxes:
                crop = self._crop_region(image_bgr, pts)
                if crop.size == 0:
                    continue
                tensor = self._preprocess_rec(crop)
                logits = self._rec_sess.run(None, {'x': tensor})[0]
                text, rec_score = self._ctc_decode(logits)
                if not text:
                    continue
                # Bounding rect as 4-point polygon for OCRResult.bbox
                br = cv2.boundingRect(pts)
                x, y, w, h = br
                bbox = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                results.append(OCRResult(
                    text=text,
                    bbox=bbox,
                    confidence=rec_score,
                ))
            return results
        except Exception as exc:
            logger.error('PPOCRv5-%s recognize_full failed: %s', self._VARIANT, exc)
            return []


class PPOCRv5MobileBackend(_PPOCRv5Backend):
    """PP-OCRv5 Mobile — lightweight, fast, CPU-friendly."""

    _VARIANT = 'mobile'

    @staticmethod
    def is_available() -> bool:
        return _is_ort_available() and PPOCRv5MobileBackend._models_exist()

    @staticmethod
    def missing_packages() -> List[str]:
        return [] if _is_ort_available() else ['onnxruntime']


class PPOCRv5ServerBackend(_PPOCRv5Backend):
    """PP-OCRv5 Server — higher accuracy, heavier compute."""

    _VARIANT = 'server'

    @staticmethod
    def is_available() -> bool:
        return _is_ort_available() and PPOCRv5ServerBackend._models_exist()

    @staticmethod
    def missing_packages() -> List[str]:
        return [] if _is_ort_available() else ['onnxruntime']


# ---------------------------------------------------------------------------
# OCRService
# ---------------------------------------------------------------------------

class OCRService:
    """
    Unified OCR service with pluggable backends.

    Usage::

        svc = OCRService()
        print(OCRService.available_backends())   # ['Qwen3-VL-2B', ...]
        svc.set_backend('Qwen3-VL-2B')
        text  = svc.recognize_roi(roi_crop_bgr)          # Mode 2
        items = svc.recognize_full(full_image_bgr)        # Mode 1
    """

    BACKEND_REGISTRY: Dict[str, Type[OCRBackend]] = {
        'GOT-OCR2.0':       GOTOCRBackend,
        'Qwen2.5-VL-3B':    QwenVLBackend,
        'Qwen3-VL-2B':      Qwen3VL2BBackend,
        'Qwen3-VL-4B':      Qwen3VL4BBackend,
        'InternVL3-2B':     InternVL3Backend,
        'PPOCRv5-Mobile':   PPOCRv5MobileBackend,
        'PPOCRv5-Server':   PPOCRv5ServerBackend,
    }

    def __init__(self, model_dir: Optional[str] = None):
        self._model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        self._model_dir.mkdir(parents=True, exist_ok=True)
        self._backend: Optional[OCRBackend] = None
        self._backend_name: str = ''
        self._status_cb: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Class-level queries (no instance needed)
    # ------------------------------------------------------------------

    @classmethod
    def available_backends(cls) -> List[str]:
        """Return names of backends whose required packages are all installed."""
        return [name for name, cls_ in cls.BACKEND_REGISTRY.items() if cls_.is_available()]

    @classmethod
    def is_ocr_available(cls) -> bool:
        """True if at least one backend is usable."""
        return bool(cls.available_backends())

    @classmethod
    def install_hint(cls, backend_name: str) -> str:
        """Return a pip install hint for a backend that is not available."""
        cls_ = cls.BACKEND_REGISTRY.get(backend_name)
        if cls_ is None:
            return ''
        missing = cls_.missing_packages()
        if not missing:
            return ''
        torch_msg = ''
        pkgs = [p for p in missing if p != 'torch']
        if 'torch' in missing:
            torch_msg = 'pip install torch --index-url https://download.pytorch.org/whl/cu121\n'
        extras = 'pip install "wxcvannotator[ocr]"' if pkgs else ''
        return (torch_msg + extras).strip()

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    @property
    def active_backend(self) -> str:
        """Name of the currently active backend, or empty string."""
        return self._backend_name

    def set_status_callback(self, cb: Optional[Callable[[str], None]]) -> None:
        """Register a callback for model loading status messages.

        The callback is invoked from the background OCR thread — use
        ``wx.CallAfter`` in the UI layer to update widgets safely.
        Pass ``None`` to clear the callback.
        """
        self._status_cb = cb
        if self._backend is not None:
            self._backend._status_cb = cb

    @property
    def is_backend_loaded(self) -> bool:
        """True if the active backend's model is already in memory."""
        return self._backend is not None and self._backend.is_loaded

    def set_backend(self, name: str) -> None:
        """
        Switch the active OCR backend.  Unloads the current model if switching.
        Raises ValueError for unknown names; RuntimeError if packages are missing.
        """
        if name not in self.BACKEND_REGISTRY:
            raise ValueError(
                f'Unknown OCR backend: {name!r}. '
                f'Known: {list(self.BACKEND_REGISTRY)}'
            )
        cls_ = self.BACKEND_REGISTRY[name]
        if not cls_.is_available():
            missing = cls_.missing_packages()
            hint = self.install_hint(name)
            raise RuntimeError(
                f"OCR backend '{name}' is not available.\n"
                f"Missing packages: {missing}\n"
                f"Install hint:\n  {hint}"
            )
        if name != self._backend_name:
            if self._backend is not None:
                self._backend.unload()
            self._backend = cls_(self._model_dir)
            self._backend._status_cb = self._status_cb  # propagate callback
            self._backend_name = name
            logger.info('OCR backend set to: %s', name)

    def recognize_roi(self, roi_bgr: np.ndarray) -> str:
        """
        Mode 2 — OCR a cropped annotation patch.

        Args:
            roi_bgr: BGR numpy array (already cropped with padding by caller).
        Returns:
            Transcription string; empty string on failure.
        """
        if self._backend is None:
            logger.warning('No OCR backend set. Call set_backend() first.')
            return ''
        return self._backend.recognize_roi(roi_bgr)

    def recognize_full(self, image_bgr: np.ndarray) -> List[OCRResult]:
        """
        Mode 1 — OCR full image.

        Args:
            image_bgr: BGR numpy array of the full image.
        Returns:
            List of OCRResult.  bbox is a 4-point polygon when grounding is
            supported (Qwen family); None otherwise (GOT, InternVL3).
        """
        if self._backend is None:
            logger.warning('No OCR backend set. Call set_backend() first.')
            return []
        return self._backend.recognize_full(image_bgr)

    def unload(self) -> None:
        """Release the model weights from GPU/RAM.

        The backend instance is kept so that the next recognize_* call will
        automatically reload the model via _load() without requiring set_backend()
        to be called again.
        """
        if self._backend is not None:
            self._backend.unload()
            # Intentionally do NOT clear _backend / _backend_name here.
            # Keeping the backend instance means recognize_roi/full will call
            # _load() which re-initialises the model on demand.
