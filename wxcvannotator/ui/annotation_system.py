#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Annotation Data Structures and Manager
Manages annotation data, state, and operation history.
"""

import json
import uuid
import time
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


class Annotation:
    """Annotation Data Structure Class"""
    
    def __init__(self, annotation_type: str, points: List[Tuple[float, float]], 
                 category: str = "object", color: str = "#FF0000"):
        """
        Initialize annotation object
        
        Args:
            annotation_type: Type (polygon, rectangle, rotated_rect, circle, point, mask)
            points: List of coordinates [(x1, y1), (x2, y2), ...] (for mask, can be empty or bounding box)
            category: Label category
            color: Color hex string
        """
        self.id = str(uuid.uuid4())
        self.type = annotation_type
        self.points = points  # Original coordinate points
        self.category = category
        self.color = color
        self.visible = True
        self.selected = False
        self.created_time = datetime.now()
        self.modified_time = datetime.now()
        self.attributes = {}  # Custom attributes
        self.flags = {}      # Boolean flags (occluded, truncated, etc.)
        self.label = category       # Primary label used for display/matching
        
        # Mask specific data (Lazy loading/Optional)
        self.mask_data = None        # bytearray or RLE string
        self.mask_shape = None       # (height, width)
        self.mask_alpha = 0.5        # Transparency for rendering
        
        # OCR specific fields
        self.transcription = ""      # OCR recognized text
        self.line_id = -1            # Line grouping ID
        self.word_id = -1            # Word ID within line
        self.confidence = 1.0        # Recognition confidence
        self.source = "manual"       # "manual" or "AI"

        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        # Encode mask data: numpy array → zlib compress → base64 string
        mask_data_encoded = None
        if self.mask_data is not None:
            if isinstance(self.mask_data, str):
                mask_data_encoded = self.mask_data  # Already encoded
            else:
                try:
                    import zlib
                    import base64
                    compressed = zlib.compress(self.mask_data.tobytes())
                    mask_data_encoded = base64.b64encode(compressed).decode('ascii')
                except Exception as e:
                    print(f"⚠️ mask encoding error: {e}")

        return {
            "id": self.id,
            "type": self.type,
            "points": [[float(x), float(y)] for x, y in self.points],
            "category": self.category,
            "color": self.color,
            "visible": self.visible,
            "selected": self.selected,
            "created_time": self.created_time.isoformat(),
            "modified_time": self.modified_time.isoformat(),
            "attributes": self.attributes,
            "flags": self.flags,
            "label": self.label,
            "transcription": self.transcription,
            "line_id": self.line_id,
            "word_id": self.word_id,
            "confidence": self.confidence,
            "source": self.source,
            # Mask data (zlib + base64 encoded for JSON storage)
            "mask_data": mask_data_encoded,
            "mask_shape": list(self.mask_shape) if self.mask_shape else None,
            "mask_alpha": self.mask_alpha
        }

    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Annotation':
        """Create annotation from dictionary"""
        annotation = cls(
            annotation_type=data["type"],
            points=[(point[0], point[1]) for point in data["points"]],
            category=data.get("category", "object"),
            color=data.get("color", "#FF0000")
        )
        annotation.id = data["id"]
        annotation.visible = data.get("visible", True)
        annotation.selected = data.get("selected", False)
        annotation.attributes = data.get("attributes", {})
        annotation.flags = data.get("flags", {})
        annotation.label = data.get("label", data.get("category", "object"))
        
        # Load OCR specific fields
        annotation.transcription = data.get("transcription", "")
        annotation.line_id = data.get("line_id", -1)
        annotation.word_id = data.get("word_id", -1)
        annotation.confidence = data.get("confidence", 1.0)
        annotation.source = data.get("source", "manual")

        # Load Mask data
        annotation.mask_data = data.get("mask_data")
        if "mask_shape" in data and data["mask_shape"]:
            annotation.mask_shape = tuple(data["mask_shape"])
        annotation.mask_alpha = data.get("mask_alpha", 0.5)

        
        # Parse time
        if "created_time" in data:
            try:
                annotation.created_time = datetime.fromisoformat(data["created_time"])
            except: pass
        if "modified_time" in data:
            try:
                annotation.modified_time = datetime.fromisoformat(data["modified_time"])
            except: pass
            
        return annotation
    
    def get_bounding_box(self) -> Tuple[float, float, float, float]:
        """Get bounding box (x, y, width, height)"""
        if not self.points:
            return (0, 0, 0, 0)
            
        x_coords = [p[0] for p in self.points]
        y_coords = [p[1] for p in self.points]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        return (min_x, min_y, max_x - min_x, max_y - min_y)
    
    def contains_point(self, x: float, y: float, tolerance: float = 5.0) -> bool:
        """Check if point is inside annotation (simplified)"""
        if self.type == "point":
            if not self.points:
                return False
            px, py = self.points[0]
            return ((x - px) ** 2 + (y - py) ** 2) <= (tolerance ** 2)

        # For rect/polygon, use a simple bbox check for now
        # More precise logic can be added if needed
        bx, by, bw, bh = self.get_bounding_box()
        return bx - tolerance <= x <= bx + bw + tolerance and by - tolerance <= y <= by + bh + tolerance

    def get_mask_array(self):
        """Return mask data as a numpy uint8 binary array (values 0 or 255).

        If mask_data is already a numpy array, returns it directly.
        If mask_data is a base64+zlib encoded string (loaded from file), decodes it.
        Returns None if no mask data is available or decoding fails.
        """
        if self.mask_data is None or self.mask_shape is None:
            return None
        try:
            import numpy as np
            if not isinstance(self.mask_data, str):
                return self.mask_data  # Already a numpy array
            import zlib
            import base64
            compressed = base64.b64decode(self.mask_data.encode('ascii'))
            raw = zlib.decompress(compressed)
            h, w = self.mask_shape
            return np.frombuffer(raw, dtype=np.uint8).reshape(h, w).copy()
        except Exception as e:
            print(f"⚠️ mask decode error: {e}")
            return None


class AnnotationManager:
    """Annotation Manager - Handles data operations and history"""
    
    def __init__(self):
        """Initialize annotation manager"""
        self.annotations: List[Annotation] = []
        self.selected_annotation: Optional[str] = None
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []
        self.history_limit = 50
        
        # Dataset split status (train/val/test/None)
        self.current_status = "None"
        
    def add_annotation(self, annotation: Annotation):
        """Add new annotation"""
        self._save_state_to_undo()
        self.annotations.append(annotation)
        self.redo_stack.clear()
        
    def remove_annotation(self, annotation_id: str) -> bool:
        """Remove annotation by ID"""
        for i, ann in enumerate(self.annotations):
            if ann.id == annotation_id:
                self._save_state_to_undo()
                self.annotations.pop(i)
                if self.selected_annotation == annotation_id:
                    self.selected_annotation = None
                self.redo_stack.clear()
                return True
        return False
    
    def update_annotation(self, annotation_id: str, data: Dict[str, Any]) -> bool:
        """Update annotation data"""
        for ann in self.annotations:
            if ann.id == annotation_id:
                self._save_state_to_undo()
                if "points" in data:
                    ann.points = data["points"]
                if "category" in data:
                    ann.category = data["category"]
                    ann.label = data["category"]
                if "color" in data:
                    ann.color = data["color"]
                if "visible" in data:
                    ann.visible = data["visible"]
                if "attributes" in data:
                    ann.attributes.update(data["attributes"])
                if "flags" in data:
                    ann.flags.update(data["flags"])
                if "transcription" in data:
                    ann.transcription = data["transcription"]

                ann.modified_time = datetime.now()
                self.redo_stack.clear()
                return True
        return False
    
    def get_annotation(self, annotation_id: str) -> Optional[Annotation]:
        """Get annotation by ID"""
        for ann in self.annotations:
            if ann.id == annotation_id:
                return ann
        return None
    
    def get_all_annotations(self) -> List[Annotation]:
        """Get all annotations"""
        return self.annotations

    def get_annotation_at(self, x: float, y: float, tolerance: float = 5.0) -> Optional[Annotation]:
        """Find the top-most visible annotation at the given point"""
        hits = self.get_annotations_at(x, y, tolerance)
        return hits[0] if hits else None

    def get_annotations_at(self, x: float, y: float, tolerance: float = 5.0) -> List[Annotation]:
        """[REQ-009] Get all visible annotations at the given point, sorted by Z-order (top-most first)"""
        hits = []
        # Search in reverse order (top-most is at the end of the list)
        for ann in reversed(self.annotations):
            if ann.visible and ann.contains_point(x, y, tolerance):
                hits.append(ann)
        return hits

    def bring_to_front(self, annotation_id: str) -> bool:
        """[REQ-009] Move annotation to the end of the list (top-most)"""
        for i, ann in enumerate(self.annotations):
            if ann.id == annotation_id:
                self._save_state_to_undo()
                target = self.annotations.pop(i)
                self.annotations.append(target)
                self.redo_stack.clear()
                return True
        return False

    def send_to_back(self, annotation_id: str) -> bool:
        """[REQ-009] Move annotation to the beginning of the list (bottom-most)"""
        for i, ann in enumerate(self.annotations):
            if ann.id == annotation_id:
                self._save_state_to_undo()
                target = self.annotations.pop(i)
                self.annotations.insert(0, target)
                self.redo_stack.clear()
                return True
        return False
    
    def select_annotation(self, annotation_id: Optional[str]):
        """Select annotation"""
        self.selected_annotation = annotation_id
        for ann in self.annotations:
            ann.selected = (ann.id == annotation_id)
            
    def clear_all(self):
        """Clear all annotations"""
        if self.annotations:
            self._save_state_to_undo()
            self.annotations = []
            self.selected_annotation = None
            self.redo_stack.clear()
            
    def save_to_file(self, file_path: str, image_path: str = "", width: int = 0, height: int = 0, embed_data: bool = False, **kwargs) -> bool:
        """Save annotations to file (JSON) - LabelMe Compatible"""
        try:
            # Skip saving if there are no annotations and no dataset status assigned,
            # unless the caller explicitly requests saving empty files.
            if kwargs.get("skip_if_empty", False):
                has_status = self.current_status not in ("None", None, "")
                if not self.annotations and not has_status:
                    return True
            import base64
            
            # Prepare LabelMe compatible shapes
            shapes = []
            for ann in self.annotations:
                # Strategy: Hybrid Fallback
                lm_type = "polygon"
                lm_points = [[float(p[0]), float(p[1])] for p in ann.points]
                lm_mask_b64 = None
                
                if ann.type == "circle" and len(ann.points) == 2:
                    lm_type = "circle"
                elif ann.type == "rectangle" and len(ann.points) == 2:
                    lm_type = "rectangle"
                elif ann.type == "point" and len(ann.points) == 1:
                    lm_type = "point"
                elif ann.type == "line" and len(ann.points) == 2:
                    lm_type = "line"
                elif ann.type == "mask":
                    lm_type = "mask"
                    # Derive bounding box from mask pixels for LabelMe points field
                    mask_arr = ann.get_mask_array()
                    if mask_arr is not None:
                        try:
                            import numpy as np
                            import cv2
                            ys, xs = np.where(mask_arr > 0)
                            if len(xs) > 0:
                                x1, y1 = int(xs.min()), int(ys.min())
                                x2, y2 = int(xs.max()), int(ys.max())
                                lm_points = [[float(x1), float(y1)], [float(x2), float(y2)]]
                                # LabelMe stores mask cropped to bounding box
                                mask_crop = mask_arr[y1:y2 + 1, x1:x2 + 1]
                                ok, buf = cv2.imencode('.png', mask_crop)
                                if ok:
                                    lm_mask_b64 = base64.b64encode(buf.tobytes()).decode('ascii')
                        except Exception:
                            lm_mask_b64 = None
                elif ann.type == "annulus":
                    # Generate a "Keyhole" polygon for LabelMe to show a hollow ring
                    import math
                    cx = ann.attributes.get("center_x", 0)
                    cy = ann.attributes.get("center_y", 0)
                    r_in = ann.attributes.get("inner_radius", 0)
                    r_out = ann.attributes.get("outer_radius", 10)
                    s_ang = ann.attributes.get("start_angle", 0)
                    e_ang = ann.attributes.get("end_angle", 360)
                    
                    # Tweak: If it's a full 360 circle, offset slightly to prevent point pruning
                    # when start and end points are identical. 359.99 is invisible but logically distinct.
                    span = abs(e_ang - s_ang)
                    actual_e_ang = e_ang
                    if span >= 360:
                        actual_e_ang = s_ang + 359.99
                    
                    num_pts = 64
                    outer_pts = []
                    inner_pts = []
                    
                    # 1. Outer circle (Clockwise)
                    for i in range(num_pts + 1):
                        angle = math.radians(s_ang + (actual_e_ang - s_ang) * i / num_pts)
                        outer_pts.append([float(cx + r_out * math.cos(angle)), float(cy + r_out * math.sin(angle))])
                    
                    # 2. Inner circle (Counter-Clockwise)
                    for i in range(num_pts, -1, -1):
                        angle = math.radians(s_ang + (actual_e_ang - s_ang) * i / num_pts)
                        inner_pts.append([float(cx + r_in * math.cos(angle)), float(cy + r_in * math.sin(angle))])
                    
                    # 3. Combine. No complicated de-duplication needed as actual_e_ang != s_ang
                    lm_points = outer_pts + inner_pts
                    lm_type = "polygon"
                else:
                    lm_type = "polygon"

                shape = {
                    "label": ann.label,
                    "points": lm_points,
                    "group_id": None,
                    "description": ann.transcription if ann.transcription else "",
                    "shape_type": lm_type,
                    "flags": ann.flags if ann.flags else {},
                    "attributes": ann.attributes if ann.attributes else {}
                }
                if lm_type == "mask" and lm_mask_b64:
                    shape["mask"] = lm_mask_b64
                shapes.append(shape)

            # Handle imageData (Base64)
            image_data_b64 = None
            if embed_data and image_path and os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as img_file:
                        image_data_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                except Exception as b64_err:
                    print(f"B64 encoding failed: {b64_err}")

            data = {
                "version": "2.0",
                "flags": {},
                "shapes": shapes,
                "imagePath": Path(image_path).name if image_path else "",
                "imageData": image_data_b64,
                "imageHeight": height,
                "imageWidth": width,
                # Dataset split status
                "status": self.current_status,
                # Perfect restoration block for our app
                "annotations": [ann.to_dict() for ann in self.annotations]
            }
            
            # Optional User Info (Annotator metadata)
            user_info = kwargs.get("user_info")
            if user_info and user_info.get("save_user_info"):
                data["annotator_name"] = user_info.get("annotator_name", "")
                data["annotator_quality"] = user_info.get("annotator_quality", 100.0)
                # Timestamp of saving
                data["save_time"] = datetime.now().isoformat()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to save annotations: {e}")
            return False
            
    def load_from_file(self, file_path: str) -> bool:
        """Load annotations from file (JSON)"""
        try:
            if not Path(file_path).exists():
                return False
                
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.annotations = []
            self.current_status = data.get("status", "None")
            
            if "annotations" in data:
                print(f"  -> Detected internal format, loading {len(data['annotations'])} items")
                for ann_data in data["annotations"]:
                    self.annotations.append(Annotation.from_dict(ann_data))
            elif "shapes" in data:
                print(f"  -> Detected LabelMe format, parsing {len(data['shapes'])} shapes")
                for shape in data["shapes"]:
                    try:
                        stype = shape.get("shape_type", "polygon").lower()
                        points = [(p[0], p[1]) for p in shape.get("points", [])]
                        label = shape.get("label", "object")
                        
                        print(f"    - Parsing LabelMe shape: {label} ({stype}) with {len(points)} points")
                        
                        annotation = Annotation(
                            annotation_type=stype,
                            points=points,
                            category=label
                        )
                        
                        # Calculate specialized attributes for our UI/C++ panel
                        if stype == "circle" and len(points) >= 2:
                            c, p = points[0], points[1]
                            r = ((p[0]-c[0])**2 + (p[1]-c[1])**2)**0.5
                            annotation.attributes.update({"center_x": c[0], "center_y": c[1], "radius": r})
                            print(f"      * Circle calculated: center=({c}), radius={r:.2f}")
                        elif stype in ["rectangle", "rect"] and len(points) == 2:
                            p1, p2 = points[0], points[1]
                            x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
                            w, h = abs(p2[0]-p1[0]), abs(p2[1]-p1[1])
                            annotation.annotation_type = "rectangle" # Normalize
                            annotation.attributes.update({"x": x, "y": y, "width": w, "height": h})
                            print(f"      * Rect calculated: x={x}, y={y}, w={w}, h={h}")
                        elif stype == "mask" and "mask" in shape:
                            # LabelMe mask: PNG base64 (cropped to bbox) → full-image numpy array
                            try:
                                import base64 as _b64
                                import numpy as np
                                import cv2
                                png_bytes = _b64.b64decode(shape["mask"])
                                crop = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
                                if crop is not None:
                                    img_h = data.get("imageHeight", 0)
                                    img_w = data.get("imageWidth", 0)
                                    # Bbox top-left from points (LabelMe convention)
                                    ox = int(points[0][0]) if len(points) >= 1 else 0
                                    oy = int(points[0][1]) if len(points) >= 1 else 0
                                    if img_h > 0 and img_w > 0:
                                        full = np.zeros((img_h, img_w), dtype=np.uint8)
                                        ch, cw = crop.shape
                                        y2 = min(oy + ch, img_h)
                                        x2 = min(ox + cw, img_w)
                                        full[oy:y2, ox:x2] = (crop[:y2 - oy, :x2 - ox] > 0).astype(np.uint8) * 255
                                        annotation.mask_data = full
                                        annotation.mask_shape = full.shape
                                    else:
                                        # No image size info: store crop as-is
                                        annotation.mask_data = (crop > 0).astype(np.uint8) * 255
                                        annotation.mask_shape = crop.shape
                                    print(f"      * LabelMe mask decoded: crop={crop.shape} → full={annotation.mask_shape}")
                            except Exception as me:
                                print(f"      ! Failed to decode LabelMe mask: {me}")
                        
                        if "attributes" in shape:
                            annotation.attributes.update(shape["attributes"])
                        if "flags" in shape and isinstance(shape["flags"], dict):
                            annotation.flags.update(shape["flags"])
                        if "description" in shape and shape["description"]:
                            annotation.transcription = shape["description"]

                        self.annotations.append(annotation)
                    except Exception as e:
                        print(f"    ✗ Failed to parse LabelMe shape: {e}")
            else:
                print(f"  -> Unknown JSON format in {file_path}")
            
            print(f"  ✓ Load complete. Total annotations in manager: {len(self.annotations)}")
            self.selected_annotation = None
            self.undo_stack.clear()
            self.redo_stack.clear()
            return True
        except Exception as e:
            print(f"Failed to load annotations: {e}")
            return False
            
    def _save_state_to_undo(self):
        """Save current state to undo stack"""
        if len(self.undo_stack) >= self.history_limit:
            self.undo_stack.pop(0)
            
        state = {
            "annotations": [ann.to_dict() for ann in self.annotations],
            "selected_annotation": self.selected_annotation,
            "timestamp": time.time()
        }
        self.undo_stack.append(state)
    
    def undo(self) -> bool:
        """Undo last operation"""
        if not self.undo_stack:
            return False
        
        current_state = {
            "annotations": [ann.to_dict() for ann in self.annotations],
            "selected_annotation": self.selected_annotation,
            "timestamp": time.time()
        }
        self.redo_stack.append(current_state)
        
        undo_state = self.undo_stack.pop()
        self._restore_state(undo_state)
        return True
    
    def redo(self) -> bool:
        """Redo last undone operation"""
        if not self.redo_stack:
            return False
        
        self._save_state_to_undo()
        
        redo_state = self.redo_stack.pop()
        self._restore_state(redo_state)
        return True
    
    def _restore_state(self, state: Dict[str, Any]):
        """Restore state from snapshot"""
        self.annotations = []
        for ann_data in state["annotations"]:
            annotation = Annotation.from_dict(ann_data)
            self.annotations.append(annotation)
        
        self.selected_annotation = state["selected_annotation"]
    
    def can_undo(self) -> bool:
        """Check if undo is available"""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available"""
        return len(self.redo_stack) > 0


# Utility functions
def create_rectangle_annotation(x: float, y: float, w: float, h: float, 
                               category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create rectangle annotation"""
    points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    ann = Annotation("rectangle", points, category, color)
    ann.attributes.update({"x": x, "y": y, "width": w, "height": h})
    return ann


def create_polygon_annotation(points: List[Tuple[float, float]], 
                             category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create polygon annotation"""
    return Annotation("polygon", points, category, color)


def create_circle_annotation(center_x: float, center_y: float, radius: float,
                           category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create circle annotation"""
    import math
    num_points = 32
    circle_points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        circle_points.append((x, y))
    ann = Annotation("circle", circle_points, category, color)
    ann.attributes.update({"center_x": center_x, "center_y": center_y, "radius": radius})
    return ann


def create_annulus_annotation(center_x: float, center_y: float, inner_radius: float, outer_radius: float,
                             start_angle: float = 0.0, end_angle: float = 360.0,
                             category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create annulus annotation"""
    import math
    num_points = 32
    annulus_points = []
    # Generate points for outer circle as basic visual representation
    for i in range(num_points):
        angle = math.radians(start_angle + (end_angle - start_angle) * i / num_points)
        x = center_x + outer_radius * math.cos(angle)
        y = center_y + outer_radius * math.sin(angle)
        annulus_points.append((x, y))
        
    ann = Annotation("annulus", annulus_points, category, color)
    ann.attributes.update({
        "center_x": center_x, 
        "center_y": center_y, 
        "inner_radius": inner_radius,
        "outer_radius": outer_radius,
        "start_angle": start_angle,
        "end_angle": end_angle
    })
    return ann


def create_rotated_rectangle_annotation(x: float, y: float, w: float, h: float, angle: float,
                                    category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create rotated rectangle annotation"""
    import math
    cx, cy = x + w/2, y + h/2
    rad = math.radians(angle)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    
    def rotate_point(px, py):
        dx, dy = px - cx, py - cy
        rx = cx + dx * cos_a - dy * sin_a
        ry = cy + dx * sin_a + dy * cos_a
        return (rx, ry)
    
    points = [
        rotate_point(x, y),
        rotate_point(x + w, y),
        rotate_point(x + w, y + h),
        rotate_point(x, y + h)
    ]
    ann = Annotation("rotated_rect", points, category, color)
    ann.attributes.update({"x": x, "y": y, "width": w, "height": h, "angle": angle})
    return ann


def create_line_annotation(p1: Tuple[float, float], p2: Tuple[float, float],
                       category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create line annotation"""
    return Annotation("line", [p1, p2], category, color)


def create_point_annotation(x: float, y: float, 
                           category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create point annotation"""
    return Annotation("point", [(x, y)], category, color)


def create_mask_annotation(mask_data: Any, shape: Tuple[int, int],
                          category: str = "object", color: str = "#FF0000") -> Annotation:
    """Create mask annotation"""
    # For mask, points can be empty or represent the bounding box
    ann = Annotation("mask", [], category, color)
    ann.mask_data = mask_data
    ann.mask_shape = shape
    return ann


# Default Categories
DEFAULT_CATEGORY_COLORS = {
    "defect": "#FF0000",     # Red
    "dent": "#00FF00",       # Green
    "scratch": "#0000FF",     # Blue
    "default": "#808080"      # Gray
}


class CategoryManager:
    """Category Manager - Handles annotation categories and colors"""
    
    def __init__(self):
        """Initialize category manager"""
        self.categories = DEFAULT_CATEGORY_COLORS.copy()
        self.category_order = list(DEFAULT_CATEGORY_COLORS.keys())
        self.recent_categories = []
        
    def add_category(self, name: str, color: str = None) -> bool:
        """Add new category"""
        if name in self.categories:
            return False
        
        if not color:
            # Generate a default color if none provided
            # Using a simple cycle or default gray
            color = "#808080"
            
        self.categories[name] = color
        if name not in self.category_order:
            self.category_order.append(name)
        return True
        
    def remove_category(self, name: str) -> bool:
        """Remove category."""
        if name in self.categories:
            del self.categories[name]
            if name in self.category_order:
                self.category_order.remove(name)
            if name in self.recent_categories:
                self.recent_categories.remove(name)
            return True
        return False
        
    def update_category(self, old_name: str, new_name: str, color: str) -> bool:
        """Update category name/color"""
        if old_name not in self.categories:
            return False
            
        if old_name != new_name and new_name in self.categories:
            return False
            
        # Update data
        del self.categories[old_name]
        self.categories[new_name] = color
        
        # Update order
        if old_name in self.category_order:
            idx = self.category_order.index(old_name)
            self.category_order[idx] = new_name
            
        # Update recent
        if old_name in self.recent_categories:
            idx = self.recent_categories.index(old_name)
            self.recent_categories[idx] = new_name
            
        return True
        
    def get_color(self, category: str) -> str:
        """Get color for category"""
        return self.categories.get(category, DEFAULT_CATEGORY_COLORS["default"])
        
    def get_all_categories(self) -> Dict[str, str]:
        """Get all categories"""
        return self.categories
        
    def get_ordered_categories(self) -> List[str]:
        """Get ordered category names"""
        return self.category_order
        
    def use_category(self, name: str):
        """Record category usage for 'recent' list"""
        if name in self.categories:
            if name in self.recent_categories:
                self.recent_categories.remove(name)
            self.recent_categories.append(name)
            # Limit history
            if len(self.recent_categories) > 10:
                self.recent_categories.pop(0)
                
    def get_recent_categories(self, limit: int = 5) -> List[str]:
        """Get recently used categories"""
        return self.recent_categories[-limit:] if self.recent_categories else []
    
    def search_categories(self, query: str) -> List[str]:
        """Search categories"""
        query = query.lower()
        return [name for name in self.categories.keys() if query in name.lower()]
    
    def export_categories(self) -> Dict[str, Any]:
        """Export category configuration"""
        return {
            "categories": self.categories,
            "order": self.category_order,
            "recent": self.recent_categories
        }
    
    def import_categories(self, data: Dict[str, Any], overwrite: bool = False):
        """Import category configuration.

        Args:
            data: Category data dict (same format as export_categories).
            overwrite: If True, replace all existing categories; if False, merge.
        """
        if overwrite:
            self.categories = {}
            self.category_order = []

        if "categories" in data:
            for name, color in data["categories"].items():
                self.categories[name] = color

        if "order" in data:
            new_order = [name for name in data["order"] if name in self.categories]
            # Append any that exist in categories but weren't in the order list
            for name in self.categories:
                if name not in new_order:
                    new_order.append(name)
            self.category_order = new_order
        else:
            # Ensure order is consistent with categories
            for name in self.categories:
                if name not in self.category_order:
                    self.category_order.append(name)

        if "recent" in data:
            self.recent_categories = [name for name in data["recent"] if name in self.categories]
    
    def clear_all(self):
        """Clear all categories (empty list is valid)."""
        self.categories = {}
        self.category_order = []
        self.recent_categories = []

    def reorder(self, new_order: List[str]):
        """Reorder categories. Names not in new_order are appended at end."""
        valid = [n for n in new_order if n in self.categories]
        for n in self.category_order:
            if n not in valid:
                valid.append(n)
        self.category_order = valid

    def reset_to_default(self):
        """Reset to default categories"""
        self.categories = DEFAULT_CATEGORY_COLORS.copy()
        self.category_order = list(DEFAULT_CATEGORY_COLORS.keys())
        self.recent_categories = []

    def load_labels(self, file_path: str) -> bool:
        """Load categories from a labels.json file"""
        try:
            path = Path(file_path)
            if not path.exists():
                return False
                
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # If data is simple list, convert to dict with default colors
            if isinstance(data, list):
                # Simple list of strings
                self.categories = {}
                self.category_order = []
                # Re-add defaults first if we want, or just start fresh
                # Let's start fresh based on the file content as it's a project-level file
                colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#00FFFF", "#FF00FF"]
                for i, name in enumerate(data):
                    color = colors[i % len(colors)]
                    self.categories[name] = color
                    self.category_order.append(name)
            elif isinstance(data, dict):
                # Advanced format
                if "categories" in data:
                    self.categories = data["categories"]
                if "order" in data:
                    self.category_order = data["order"]
                else:
                    self.category_order = list(self.categories.keys())
                if "recent" in data:
                    self.recent_categories = data["recent"]
            
            return True
        except Exception as e:
            print(f"Error loading labels from {file_path}: {e}")
            return False

    def save_labels(self, file_path: str) -> bool:
        """Save current categories to a labels.json file"""
        try:
            data = self.export_categories()
            path = Path(file_path)
            
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving labels to {file_path}: {e}")
            return False
