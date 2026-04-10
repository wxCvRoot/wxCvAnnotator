#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Service - Handles AI model inference (SAM, SAM2, EfficientSAM)
Provides real multi-model support with auto-downloading.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from pathlib import Path
import time
import requests
import os
import cv2
import traceback

try:
    import onnxruntime as ort
except ImportError:
    ort = None

try:
    import skimage.measure as _skimage_measure
except ImportError:
    _skimage_measure = None

try:
    import osam.apis as _osam_apis
    import osam.types as _osam_types
except ImportError:
    _osam_apis = None
    _osam_types = None

class AIService:
    """AI Inference Service Wrapper with multi-family support (SAM, SAM2, EfficientSAM)"""
    
    @staticmethod
    def is_available() -> bool:
        """Check if AI backend (onnxruntime) is available in the environment"""
        return ort is not None
    
    # Model Registry (Public URLs from shubham0204 and Acly)
    MODEL_REGISTRY = {
        "Sam(speed)": {
            "family": "sam",
            "encoder": {
                "filename": "sam_vit_b_encoder_quant.onnx",
                "url": "https://huggingface.co/Xenova/sam-vit-base/resolve/main/onnx/vision_encoder_quantized.onnx"
            },
            "decoder": {
                "filename": "sam_vit_b_decoder_quant.onnx",
                "url": "https://huggingface.co/Xenova/sam-vit-base/resolve/main/onnx/prompt_encoder_mask_decoder_quantized.onnx"
            },
            "description": "SAM ViT-B (Quantized) - Official LabelMe speed model."
        },
        "Sam(balanced)": {
            "family": "sam",
            "encoder": {
                "filename": "sam_vit_l_encoder_quant.onnx",
                "url": "https://huggingface.co/Xenova/sam-vit-large/resolve/main/onnx/vision_encoder_quantized.onnx"
            },
            "decoder": {
                "filename": "sam_vit_l_decoder_quant.onnx",
                "url": "https://huggingface.co/Xenova/sam-vit-large/resolve/main/onnx/prompt_encoder_mask_decoder_quantized.onnx"
            },
            "description": "SAM ViT-L (Quantized) - Official LabelMe balanced model."
        },
        "Sam(accuracy)": {
            "family": "sam",
            "encoder": {
                "filename": "sam_vit_h_encoder_quant.onnx",
                "url": "https://huggingface.co/Xenova/sam-vit-huge/resolve/main/onnx/vision_encoder_quantized.onnx"
            },
            "decoder": {
                "filename": "sam_vit_h_decoder_quant.onnx",
                "url": "https://huggingface.co/Xenova/sam-vit-huge/resolve/main/onnx/prompt_encoder_mask_decoder_quantized.onnx"
            },
            "description": "SAM ViT-H (Quantized) - Official LabelMe accuracy model."
        },
        "Sam2(speed)": {
            "family": "sam2",
            "encoder": {
                "filename": "sam2_hiera_tiny_encoder.onnx",
                "url": "https://huggingface.co/shubham0204/sam2-onnx-models/resolve/main/sam2_hiera_tiny_encoder.onnx"
            },
            "decoder": {
                "filename": "sam2_hiera_tiny_decoder.onnx",
                "url": "https://huggingface.co/shubham0204/sam2-onnx-models/resolve/main/sam2_hiera_tiny_decoder.onnx"
            },
            "description": "SAM 2 Tiny - Latest generation speed model."
        },
        "Sam2(balanced)": {
            "family": "sam2",
            "encoder": {
                "filename": "sam2_hiera_small_encoder.onnx",
                "url": "https://huggingface.co/shubham0204/sam2-onnx-models/resolve/main/sam2_hiera_small_encoder.onnx"
            },
            "decoder": {
                "filename": "sam2_hiera_small_decoder.onnx",
                "url": "https://huggingface.co/shubham0204/sam2-onnx-models/resolve/main/sam2_hiera_small_decoder.onnx"
            },
            "description": "SAM 2 Small - High stability."
        },
        "Sam2(accuracy)": {
            "family": "sam2",
            "encoder": {
                "filename": "sam2_hiera_base_plus_encoder.onnx",
                "url": "https://huggingface.co/shubham0204/sam2-onnx-models/resolve/main/sam2_hiera_base_plus_encoder.onnx"
            },
            "decoder": {
                "filename": "sam2_hiera_base_plus_decoder.onnx",
                "url": "https://huggingface.co/shubham0204/sam2-onnx-models/resolve/main/sam2_hiera_base_plus_decoder.onnx"
            },
            "description": "SAM 2 Base+ - Professional accuracy."
        },
        # Compatibility aliases - ensure they use the correct internal keys or represent real models
        "EfficientSAM (speed)": {
            "family": "efficientsam",
            "encoder": {
                "filename": "efficientsam_ti_encoder.onnx",
                # Original: "https://huggingface.co/shubham0204/EfficientSAM-ONNX-Models/resolve/main/efficientsam_ti_encoder.onnx"
                "url": "https://huggingface.co/yunyangx/EfficientSAM/resolve/main/efficientsam_ti_encoder.onnx"
            },
            "decoder": {
                "filename": "efficientsam_ti_decoder.onnx",
                # Original: "https://huggingface.co/shubham0204/EfficientSAM-ONNX-Models/resolve/main/efficientsam_ti_decoder.onnx"
                "url": "https://huggingface.co/yunyangx/EfficientSAM/resolve/main/efficientsam_ti_decoder.onnx"
            },
            "description": "EfficientSAM Ti - Fastest performance."
        },
        "EfficientSAM (accuracy)": {
            "family": "efficientsam",
            "encoder": {
                "filename": "efficientsam_s_encoder.onnx",
                # Original: "https://huggingface.co/shubham0204/EfficientSAM-ONNX-Models/resolve/main/efficientsam_s_encoder.onnx"
                "url": "https://huggingface.co/yunyangx/EfficientSAM/resolve/main/efficientsam_s_encoder.onnx"
            },
            "decoder": {
                "filename": "efficientsam_s_decoder.onnx",
                # Original: "https://huggingface.co/shubham0204/EfficientSAM-ONNX-Models/resolve/main/efficientsam_s_decoder.onnx"
                "url": "https://huggingface.co/yunyangx/EfficientSAM/resolve/main/efficientsam_s_decoder.onnx"
            },
            "description": "EfficientSAM S - High accuracy Efficient model."
        },
        # SAM 2.1 via osam backend (LabelMe-compatible, auto-downloads to ~/.cache/osam/)
        "Sam2.1(speed)": {
            "family": "osam",
            "osam_model_name": "sam2:small",
            "description": "SAM 2.1 Small via osam — fast, high-res capable."
        },
        "Sam2.1(balanced)": {
            "family": "osam",
            "osam_model_name": "sam2:latest",
            "description": "SAM 2.1 Base+ via osam — recommended for high-res images with small objects."
        },
        "Sam2.1(accuracy)": {
            "family": "osam",
            "osam_model_name": "sam2:large",
            "description": "SAM 2.1 Large via osam — maximum accuracy."
        },
    }

    def __init__(self, model_dir: str = "models"):
        """Initialize AI service"""
        _path = Path(model_dir)
        if not _path.is_absolute():
            # Resolve relative paths to project root (utils/ is one level below root)
            _path = Path(__file__).parent.parent / _path
        self.model_dir = _path
        self.is_ready = False
        self.current_model_name = None
        self.current_family = None
        
        # Sessions
        self.encoder_session = None
        self.decoder_session = None
        
        # Current image state
        self.image_embedding = None
        self.image_pos_embedding = None
        self.high_res_feats = None
        self.original_size = (0, 0) # (H, W)
        self.current_scale = 1.0
        self.input_size = (1024, 1024)
        self.last_image = None # Cache for model switching

        # osam state (SAM 2.1 via osam backend)
        self.osam_model = None
        self._osam_model_name = None
        self.osam_embedding = None

    def initialize(self, model_name: str = "Sam(balanced)") -> bool:
        """Initialize AI service with a specific model"""
        print(f"🤖 Real AI Initialization: {model_name}...")
        
        if model_name not in self.MODEL_REGISTRY:
            print(f"❌ Unknown model: {model_name}")
            return False
            
        # Handle alias
        if "alias" in self.MODEL_REGISTRY[model_name]:
            model_name = self.MODEL_REGISTRY[model_name]["alias"]

        self.current_model_name = model_name
        model_info = self.MODEL_REGISTRY[model_name]
        self.current_family = model_info.get("family", "sam")

        # osam family: managed by osam package (auto-downloads to ~/.cache/osam/)
        if self.current_family == "osam":
            if _osam_apis is None:
                print("❌ osam not installed. Run: pip install osam")
                return False
            osam_name = model_info["osam_model_name"]
            model_cls = next(
                (m for m in _osam_apis.registered_model_types if m.name == osam_name), None
            )
            if model_cls is None:
                print(f"❌ osam model '{osam_name}' not found in registry.")
                return False
            print(f"📥 Loading osam model '{osam_name}' (auto-downloads if missing)...")
            self.osam_model = model_cls()
            self._osam_model_name = osam_name
            self.is_ready = True
            if self.last_image is not None:
                print("🔄 Model switched, re-calculating embeddings...")
                self.set_image(self.last_image)
            print(f"✅ AI Service Ready: {model_name} (Family: osam)")
            return True

        # 1. Ensure all parts are downloaded
        if not self._download_all_parts(model_info):
            return False
            
        # 2. Load ONNX Sessions
        success = self._load_model_parts(model_info)
        if success:
            self.is_ready = True
            # Reset and re-embed if we have an image
            self.image_embedding = None
            self.image_pos_embedding = None
            self.high_res_feats = None
            if self.last_image is not None:
                print("🔄 Model switched, re-calculating embeddings...")
                self.set_image(self.last_image)
            print(f"✅ AI Service Ready: {model_name} (Family: {self.current_family})")
        return success

    def _download_all_parts(self, model_info: Dict) -> bool:
        """Download encoder and decoder if missing"""
        for part_name in ["encoder", "decoder"]:
            part = model_info[part_name]
            path = self.model_dir / part["filename"]
            if not path.exists():
                if not self._download_part(part["url"], path):
                    return False
        return True

    def _download_part(self, url: str, path: Path) -> bool:
        """Real stream downloader with basic progress feedback"""
        print(f"📥 Downloading Part: {path.name}...")
        try:
            # Ensure dir
            path.parent.mkdir(parents=True, exist_ok=True)
            
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and downloaded % (10*1024*1024) == 0:
                            print(f"   📊 {path.name}: {downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB")
            
            print(f"✅ Downloaded {path.name}")
            return True
        except Exception as e:
            print(f"❌ Download failed for {url}: {e}")
            if path.exists():
                path.unlink()
            return False

    def _load_model_parts(self, model_info: Dict) -> bool:
        """Initialize ONNX sessions"""
        if ort is None:
            print("❌ onnxruntime not found. Cannot load models.")
            return False
            
        try:
            print(f"🧠 Loading ONNX Sessions for {self.current_model_name}...")
            
            encoder_path = self.model_dir / model_info["encoder"]["filename"]
            decoder_path = self.model_dir / model_info["decoder"]["filename"]
            
            providers = ['CPUExecutionProvider']
            
            self.encoder_session = ort.InferenceSession(str(encoder_path), providers=providers)
            self.decoder_session = ort.InferenceSession(str(decoder_path), providers=providers)
            
            print("✨ Sessions Ready.")
            return True
        except Exception as e:
            print(f"❌ Failed to load sessions: {e}\n{traceback.format_exc()}")
            return False

    @property
    def is_loaded(self) -> bool:
        """True if a model is currently loaded in memory."""
        if self.current_family == "osam":
            return self.osam_model is not None
        return self.encoder_session is not None

    def unload(self) -> None:
        """Release all loaded AI segmentation model sessions from memory."""
        self.encoder_session = None
        self.decoder_session = None
        self.osam_model = None
        self._osam_model_name = None
        self.image_embedding = None
        self.image_pos_embedding = None
        self.high_res_feats = None
        self.osam_embedding = None
        self.last_image = None
        self.is_ready = False
        self.current_model_name = None
        self.current_family = None
        try:
            import onnxruntime as _ort_cleanup  # noqa: F401
            # ONNX sessions freed by setting to None above
        except ImportError:
            pass
        print("🗑 AI segmentation model unloaded.")

    def is_embedding_ready(self) -> bool:
        """Check if image embedding is precomputed"""
        if self.current_family == "osam":
            return self.osam_embedding is not None
        return self.image_embedding is not None

    def set_image(self, image: np.ndarray):
        """Precompute image embeddings for the current image"""
        if self.current_family == "osam":
            if self.osam_model is None:
                print("❌ osam model not loaded.")
                return
            print("🖼️ Preparing image for osam (Encoder)...")
            self.last_image = image
            self.original_size = image.shape[:2]
            self.current_scale = 1.0
            self.osam_embedding = None
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            try:
                self.osam_embedding = self.osam_model.encode_image(rgb)
                self.is_ready = True
                print("✅ osam image embedded.")
            except Exception as e:
                print(f"❌ osam encode_image failed: {e}")
                self.is_ready = False
            return

        if self.encoder_session is None:
            print("❌ Encoder not ready.")
            return
            
        print("🖼️ Preparing image for AI (Encoder)...")
        self.last_image = image # Store for model change
        self.original_size = image.shape[:2] # (H, W)
        
        # 0. Reset previous state
        self.image_embedding = None
        self.image_pos_embedding = None
        self.high_res_feats = None
        
        # 1. Prepare input tensor (family-specific preprocessing)
        if self.current_family == "efficientsam":
            # EfficientSAM: pass the original image without resize/pad.
            # The ONNX encoder handles coordinate scaling internally;
            # orig_im_size tells the decoder to output mask at original resolution.
            self.current_scale = 1.0
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            input_tensor = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        else:
            # SAM / SAM2: resize longest side to input_size, pad to square
            h, w = self.original_size
            target_h, target_w = self.input_size

            self.current_scale = min(target_h / h, target_w / w)
            new_h, new_w = int(h * self.current_scale), int(w * self.current_scale)

            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            resized_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)

            if self.current_family == "sam2":
                # SAM 2: normalize to [0,1] with ImageNet mean/std
                mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
                std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
                normalized = (resized_rgb / 255.0 - mean) / std
            else:
                # Standard SAM: (x - pixel_mean) / pixel_std (values in 0-255 range)
                pixel_mean = np.array([123.675, 116.28, 103.53], dtype=np.float32)
                pixel_std = np.array([58.395, 57.12, 57.375], dtype=np.float32)
                normalized = (resized_rgb - pixel_mean) / pixel_std

            # Zero-pad in normalized space — padding area = 0.0, the model's neutral value.
            # Padding BEFORE normalization (old approach) left non-zero artifacts in the
            # padding region, causing the model to treat padding as image content.
            input_tensor = np.zeros((target_h, target_w, 3), dtype=np.float32)
            input_tensor[:new_h, :new_w, :] = normalized

            input_tensor = input_tensor.transpose(2, 0, 1).astype(np.float32)  # CHW
            input_tensor = np.expand_dims(input_tensor, axis=0)  # NCHW
        
        # 3. Run Encoder
        print(f"⚡ Running {self.current_family.upper()} Encoder...")
        try:
            encoder_inputs = self.encoder_session.get_inputs()
            input_names = [inp.name for inp in encoder_inputs]
            print(f"DEBUG: Encoder input names: {input_names}")
            print(f"DEBUG: Input tensor shape: {input_tensor.shape}, dtype: {input_tensor.dtype}")
            
            # 1. Xenova/Official SAM: pixel_values -> (image_embeddings, reshaped_input_pos_features, iou_predictions, low_res_masks)
            if "pixel_values" in input_names:
                print("DEBUG: Using 'pixel_values' input path")
                outputs = self.encoder_session.run(None, {"pixel_values": input_tensor})
                self.image_embedding = outputs[0]  # image_embeddings
                print(f"DEBUG: Encoder output[0] shape: {self.image_embedding.shape}")
                
                # Check for positional embeddings in outputs (usually index 1)
                # Output names might be transparent, but usually 2nd output is pos embed if present
                if len(outputs) > 1:
                     print("✅ Captured Positional Embeddings from Encoder")
                     self._pos_embed_cache = outputs[1] # Cache for decoder
                
            # 2. EfficientSAM / Original MobileSAM: images -> image_embeddings
            else:
                input_name = encoder_inputs[0].name
                print(f"DEBUG: Using '{input_name}' input path")
                outputs = self.encoder_session.run(None, {input_name: input_tensor})
                # SAM 2 special handling: 3 outputs [high_res_0, high_res_1, embed]
                if self.current_family == "sam2" and len(outputs) >= 3:
                     self.image_embedding = outputs[2]
                     self.high_res_feats = [outputs[0], outputs[1]]
                else:
                     self.image_embedding = outputs[0]
                print(f"DEBUG: Encoder output[0] shape: {self.image_embedding.shape}")
            
            self.is_ready = True
            print("✅ Image normalized and embedded.")
        except Exception as e:
            print(f"❌ Encoder failure detail: {e}")
            import traceback
            traceback.print_exc()
            self.is_ready = False

    def _get_positional_embedding(self):
        """Generate static positional embedding for 1024x1024 input (64x64 feature map)"""
        # This is constant for a fixed input size of 1024x1024 -> 64x64 embeddings
        if hasattr(self, '_pos_embed_cache'):
            return self._pos_embed_cache
            
        # Standard SAM positional embedding logic is complex to replicate exactly without torch.
        # However, for ONNX runtime with Xenova models, usually the Encoder outputs it, 
        # OR we can pass a zero-initialized buffer if we don't have it, though strictly usually required.
        # Xenova/Transformers.js usually pre-computes this.
        # Let's try to find if the Encoder returned it.
        
        # If not available, creating a dummy one of correct shape: (1, 256, 64, 64)
        print("⚠️ Generating dummy positional embedding (1, 256, 64, 64)")
        self._pos_embed_cache = np.zeros((1, 256, 64, 64), dtype=np.float32)
        return self._pos_embed_cache
        
        # 3. Run Encoder
        print(f"⚡ Running {self.current_family.upper()} Encoder...")
        try:
            encoder_inputs = self.encoder_session.get_inputs()
            input_names = [inp.name for inp in encoder_inputs]
            print(f"DEBUG: Encoder input names: {input_names}")
            print(f"DEBUG: Input tensor shape: {input_tensor.shape}, dtype: {input_tensor.dtype}")
            
            # 1. Xenova/Official SAM: pixel_values -> (image_embeddings, reshaped_input_pos_features, iou_predictions, low_res_masks)
            if "pixel_values" in input_names:
                print("DEBUG: Using 'pixel_values' input path")
                outputs = self.encoder_session.run(None, {"pixel_values": input_tensor})
                self.image_embedding = outputs[0]  # image_embeddings
                print(f"DEBUG: Encoder output[0] shape: {self.image_embedding.shape}")
                
                # Check for positional embeddings in outputs (usually index 1)
                # Output names might be transparent, but usually 2nd output is pos embed if present
                if len(outputs) > 1:
                     print("✅ Captured Positional Embeddings from Encoder")
                     self._pos_embed_cache = outputs[1] # Cache for decoder
                
            # 2. EfficientSAM / Original MobileSAM: images -> image_embeddings
            else:
                input_name = encoder_inputs[0].name
                print(f"DEBUG: Using '{input_name}' input path")
                outputs = self.encoder_session.run(None, {input_name: input_tensor})
                # SAM 2 special handling: 3 outputs [high_res_0, high_res_1, embed]
                if self.current_family == "sam2" and len(outputs) >= 3:
                     self.image_embedding = outputs[2]
                     self.high_res_feats = [outputs[0], outputs[1]]
                else:
                     self.image_embedding = outputs[0]
                print(f"DEBUG: Encoder output[0] shape: {self.image_embedding.shape}")
            
            self.is_ready = True
            print("✅ Image normalized and embedded.")
        except Exception as e:
            print(f"❌ Encoder failure detail: {e}")
            import traceback
            traceback.print_exc()
            self.is_ready = False

    def _run_decoder(self, prompts: List[Dict[str, Any]]) -> Optional[np.ndarray]:
        """Run the mask decoder and return the best raw 2D float mask, or None on failure.

        This is the shared backbone used by both predict_polygon and predict_mask.
        """
        # osam family: handled separately from the ONNX pipeline
        if self.current_family == "osam":
            if self.osam_embedding is None or not prompts or _osam_types is None:
                return None
            try:
                print("⚡ Running osam Mask Decoder...")
                points = np.array([[p["pos"][0], p["pos"][1]] for p in prompts], dtype=np.float32)
                labels = np.array([p["label"] for p in prompts], dtype=np.int32)
                prompt = _osam_types.Prompt(points=points, point_labels=labels)
                request = _osam_types.GenerateRequest(
                    model=self._osam_model_name,
                    image_embedding=self.osam_embedding,
                    prompt=prompt,
                )
                response = self.osam_model.generate(request)
                if not response.annotations or response.annotations[0].mask is None:
                    return None
                # osam mask is bool (H_orig, W_orig); convert to float for _project_mask
                return response.annotations[0].mask.astype(np.float32)
            except Exception as e:
                print(f"❌ osam decoder failed: {e}")
                return None

        if self.decoder_session is None or self.image_embedding is None or not prompts:
            return None

        print(f"⚡ Running Mask Decoder ({self.current_family})...")
        try:
            family = self.current_family.lower()

            # 1. Build prompt tensors (model-family specific coordinate space)
            coords, labels = [], []
            for p in prompts:
                px, py = p["pos"]
                if family == "efficientsam":
                    coords.append([float(px), float(py)])          # ONNX bakes coordinate scaling internally
                else:
                    coords.append([float(px * self.current_scale), float(py * self.current_scale)])
                labels.append(float(p["label"]))

            # Dummy negative prompt required by official SAM / Xenova decoders
            if family == "sam":
                coords.append([0.0, 0.0])
                labels.append(-1.0)

            input_coords = np.array(coords, dtype=np.float32).reshape(1, 1, len(coords), 2)
            input_labels = np.array(labels, dtype=np.int64).reshape(1, 1, len(labels))

            # 2. Assemble decoder inputs dynamically
            decoder_inputs = {}
            input_objs  = self.decoder_session.get_inputs()
            input_names = [inp.name for inp in input_objs]
            output_objs  = self.decoder_session.get_outputs()
            output_names = [out.name for out in output_objs]

            # --- Image embeddings ---
            if "image_embeddings" in input_names:
                decoder_inputs["image_embeddings"] = self.image_embedding
            elif input_names and "low_res_embedding" not in input_names:
                decoder_inputs[input_names[0]] = self.image_embedding

            # --- Point prompts ---
            if "input_points" in input_names:
                decoder_inputs["input_points"] = input_coords
                decoder_inputs["input_labels"] = input_labels
            elif "point_coords" in input_names:
                inp = next(i for i in input_objs if i.name == "point_coords")
                if len(inp.shape) == 3:
                    decoder_inputs["point_coords"] = input_coords.reshape(1, len(coords), 2)
                    lbl = input_labels.reshape(1, len(labels))
                    decoder_inputs["point_labels"] = lbl.astype(np.float32) if "float" in inp.type else lbl
                else:
                    decoder_inputs["point_coords"] = input_coords
                    decoder_inputs["point_labels"] = input_labels
            elif "batched_point_coords" in input_names:
                decoder_inputs["batched_point_coords"] = input_coords
                inp_l = next(i for i in input_objs if i.name == "batched_point_labels")
                decoder_inputs["batched_point_labels"] = (
                    input_labels.astype(np.float32) if "float" in inp_l.type else input_labels
                )

            # --- SAM 2 high-res features ---
            if "high_res_feats_0" in input_names and hasattr(self, "high_res_feats"):
                decoder_inputs["high_res_feats_0"] = self.high_res_feats[0]
                decoder_inputs["high_res_feats_1"] = self.high_res_feats[1]

            # --- Positional embeddings ---
            if "image_positional_embeddings" in input_names:
                decoder_inputs["image_positional_embeddings"] = self._get_positional_embedding()

            # --- Extra metadata ---
            if "mask_input" in input_names:
                decoder_inputs["mask_input"] = np.zeros((1, 1, 256, 256), dtype=np.float32)
            if "has_mask_input" in input_names:
                inp_meta = next(i for i in input_objs if i.name == "has_mask_input")
                sanitized_shape = [1 if isinstance(s, str) else int(s) for s in (inp_meta.shape or [1])]
                decoder_inputs["has_mask_input"] = np.zeros(tuple(sanitized_shape), dtype=np.float32)
            if "orig_im_size" in input_names:
                inp_meta = next(i for i in input_objs if i.name == "orig_im_size")
                dtype = np.int32 if "int32" in inp_meta.type else (np.int64 if "int64" in inp_meta.type else np.float32)
                h_orig, w_orig = self.original_size
                if family == "sam2":
                    # SAM2 (shubham0204): decoder resizes its internal mask directly to
                    # orig_im_size without first cropping the padding added during encoding.
                    # Pass the full canvas size so the decoder outputs at 1024×1024 (the
                    # full padded canvas); _project_mask then crops and rescales correctly.
                    target_h, target_w = self.input_size
                    decoder_inputs["orig_im_size"] = np.array([target_h, target_w], dtype=dtype)
                else:
                    # SAM (Xenova) and EfficientSAM correctly handle orig_im_size.
                    decoder_inputs["orig_im_size"] = np.array([h_orig, w_orig], dtype=dtype)

            # 3. Run decoder
            outputs = self.decoder_session.run(None, decoder_inputs)

            # 4. Extract best mask
            mask, iou_scores = None, None
            for mn in ["output_masks", "masks", "low_res_masks", "pred_masks"]:
                if mn in output_names:
                    mask = outputs[output_names.index(mn)]
                    for sn in ["iou_predictions", "iou_prediction", "iou_scores", "scores"]:
                        if sn in output_names:
                            iou_scores = outputs[output_names.index(sn)]
                            break
                    break
            if mask is None:
                for out in outputs:
                    if len(out.shape) >= 4 and out.shape[-1] > 10:
                        mask = out
                        break
            if mask is None:
                return None

            # 5. Squeeze to 2D, selecting best candidate by IoU score
            while len(mask.shape) > 2:
                if mask.shape[1] > 1 and iou_scores is not None:
                    best_idx = np.argmax(iou_scores.flatten())
                    m_3d = mask.reshape(-1, mask.shape[-2], mask.shape[-1])
                    mask = m_3d[min(best_idx, m_3d.shape[0] - 1)]
                else:
                    mask = mask[0] if mask.shape[1] == 1 else mask[0, 0]

            return mask  # 2D float array

        except Exception as e:
            print(f"❌ Decoder failed: {e}")
            return None

    def _project_mask(self, raw_mask: np.ndarray, denoise: bool = True) -> np.ndarray:
        """Project a raw 2D model-space mask back to the original image resolution.

        Returns a uint8 binary mask (0 / 255) of shape (H_orig, W_orig).
        """
        binary = (raw_mask > 0.0).astype(np.uint8) * 255
        h_orig, w_orig = self.original_size
        h_m, w_m = raw_mask.shape

        if (h_m, w_m) == (h_orig, w_orig):
            final = binary
        else:
            target_h, target_w = self.input_size
            # Scale mask to input_size if it is a low-res output (e.g. 256x256)
            if (h_m, w_m) != (target_h, target_w):
                full = cv2.resize(binary, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            else:
                full = binary
            # Crop the padded region before rescaling.
            # The image was placed at [0:h_scaled, 0:w_scaled] inside the input_size canvas.
            h_scaled = max(1, min(int(h_orig * self.current_scale), target_h))
            w_scaled = max(1, min(int(w_orig * self.current_scale), target_w))
            final = cv2.resize(full[:h_scaled, :w_scaled], (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)

        if denoise:
            n, labels, stats, _ = cv2.connectedComponentsWithStats(final, connectivity=8)
            if n > 1:
                largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                final = (labels == largest).astype(np.uint8) * 255

        return final

    def predict_polygon(self, image: Optional[np.ndarray], prompts: List[Dict[str, Any]],
                        tolerance: float = 0.004, denoise: bool = True) -> List[Tuple[float, float]]:
        """Run AI inference and return a simplified polygon (list of (x, y) tuples)."""
        raw_mask = self._run_decoder(prompts)
        if raw_mask is None:
            return []
        return self._mask_to_polygon(raw_mask, tolerance=tolerance, denoise=denoise)

    def predict_mask(self, prompts: List[Dict[str, Any]],
                     denoise: bool = True) -> Optional[np.ndarray]:
        """Run AI inference and return the full pixel-level binary mask.

        Returns a uint8 numpy array of shape (H, W) with values 0 or 255,
        aligned to the original image resolution.  Returns None on failure.
        """
        raw_mask = self._run_decoder(prompts)
        if raw_mask is None:
            return None
        result = self._project_mask(raw_mask, denoise=denoise)
        print(f"✨ Mask Prediction Result: {result.shape}, nonzero={np.count_nonzero(result)}")
        return result

    def _mask_to_polygon(self, mask: np.ndarray, tolerance: float = 0.004,
                         denoise: bool = True) -> List[Tuple[float, float]]:
        """Convert a raw model mask to a simplified polygon via contour extraction.

        Uses skimage marching-squares (same as LabelMe) when available, which produces
        sub-pixel (.5) coordinates and avoids the integer-pixel staircase / jagged-teeth
        artifact that cv2.findContours produces on binary masks.
        """
        projected = self._project_mask(mask, denoise=denoise)
        h_orig, w_orig = self.original_size

        if _skimage_measure is not None:
            # --- skimage path (preferred, matches LabelMe exactly) ---
            bool_mask = projected > 0
            # pad_width=1 ensures the contour can be traced at mask edges
            raw_contours = _skimage_measure.find_contours(np.pad(bool_mask, pad_width=1))
            if not raw_contours:
                return []
            # Pick contour with longest perimeter (most points → largest object)
            contour = max(raw_contours,
                          key=lambda c: float(np.sum(np.linalg.norm(np.diff(c, axis=0), axis=1))))
            # Adaptive RDP tolerance — based on contour's own extent (not image size)
            tol = np.ptp(contour, axis=0).max() * tolerance
            polygon = _skimage_measure.approximate_polygon(contour, tolerance=tol)
            # Clip back to original mask bounds (handles pad offset)
            polygon = np.clip(polygon, (0, 0), (h_orig - 1, w_orig - 1))
            polygon = polygon[:-1]  # remove duplicate closing point
            # skimage returns (row, col) = (y, x); convert to (x, y)
            return [(float(p[1]), float(p[0])) for p in polygon]

        else:
            # --- cv2 fallback (integer-pixel only, less smooth) ---
            contours, _ = cv2.findContours(projected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return []
            main_contour = max(contours, key=cv2.contourArea)
            contour_pts = main_contour.reshape(-1, 2)
            ptp = np.ptp(contour_pts, axis=0)
            epsilon = float(ptp.max()) * tolerance
            approx = cv2.approxPolyDP(main_contour, epsilon, True)
            return [(float(p[0][0]), float(p[0][1])) for p in approx]
