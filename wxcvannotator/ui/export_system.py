#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-format Annotation Export System
Supports exporting to YOLO, COCO, Pascal VOC, CSV, etc.
"""

import json
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import random
import shutil

from .annotation_system import Annotation, AnnotationManager, CategoryManager


class FormatExporter:
    """Base Format Exporter"""
    
    def __init__(self, annotation_manager: AnnotationManager, category_manager: CategoryManager):
        self.annotation_manager = annotation_manager
        self.category_manager = category_manager
    
    def export(self, output_path: str, image_width: int, image_height: int, 
               image_filename: str = None) -> bool:
        """
        Export annotations to a specific format
        """
        raise NotImplementedError
    
    def _normalize_coordinates(self, annotation: Annotation, 
                              image_width: int, image_height: int) -> Tuple[float, float, float, float]:
        """Normalize coordinates to 0-1 range"""
        bbox = annotation.get_bounding_box()
        x, y, w, h = bbox
        
        # Normalize to 0-1 range
        if image_width <= 0 or image_height <= 0:
            return (0.0, 0.0, 0.0, 0.0)
            
        normalized_x = x / image_width
        normalized_y = y / image_height
        normalized_w = w / image_width
        normalized_h = h / image_height
        
        return (normalized_x, normalized_y, normalized_w, normalized_h)
    
    def _get_category_index(self, category: str) -> int:
        """Get category index (to be overridden)"""
        return 0


class YOLOExporter(FormatExporter):
    """YOLO Format Exporter"""
    
    def export(self, output_path: str, image_width: int, image_height: int, 
               image_filename: str = None) -> bool:
        """
        YOLO format export
        Format: <class_id> <center_x> <center_y> <width> <height>
        """
        try:
            annotations = self.annotation_manager.get_all_annotations()
            if not annotations:
                return False
            
            # Get category to index mapping
            categories = self.category_manager.get_ordered_categories()
            category_to_index = {name: idx for idx, name in enumerate(categories)}
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for annotation in annotations:
                    if not annotation.visible or not annotation.points:
                        continue
                    
                    # Get class ID
                    class_id = category_to_index.get(annotation.category, 0)
                    
                    # Normalize coordinates
                    norm_x, norm_y, norm_w, norm_h = self._normalize_coordinates(
                        annotation, image_width, image_height)
                    
                    # YOLO uses center points
                    center_x = norm_x + norm_w / 2
                    center_y = norm_y + norm_h / 2
                    
                    # Write YOLO format line
                    f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {norm_w:.6f} {norm_h:.6f}\n")
            
            return True
        except Exception as e:
            print(f"YOLO export failed: {e}")
            return False

    def export_dataset(self, output_dir: str, images: List[str], 
                      image_dimensions: List[Tuple[int, int]]) -> bool:
        """Batch export YOLO dataset"""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Create classes.txt
            categories = self.category_manager.get_ordered_categories()
            classes_file = output_path / "classes.txt"
            with open(classes_file, 'w', encoding='utf-8') as f:
                for category in categories:
                    f.write(f"{category}\n")
            
            # Process each image
            for img_file, (width, height) in zip(images, image_dimensions):
                img_path = Path(img_file)
                json_path = img_path.with_suffix('.json')
                
                if not json_path.exists():
                    continue
                
                # Load annotations
                temp_manager = AnnotationManager()
                if temp_manager.load_from_file(str(json_path)):
                    # Switch temporarily
                    saved_manager = self.annotation_manager
                    self.annotation_manager = temp_manager
                    
                    yolo_path = output_path / f"{img_path.stem}.txt"
                    self.export(str(yolo_path), width, height, img_path.name)
                    
                    self.annotation_manager = saved_manager
            return True
        except Exception as e:
            print(f"YOLO dataset export failed: {e}")
            return False


class YOLOSegExporter(FormatExporter):
    """YOLOv8 Segmentation Format Exporter"""
    
    def export(self, output_path: str, image_width: int, image_height: int, 
               image_filename: str = None) -> bool:
        """
        YOLO-Seg format export: <class_id> <x1> <y1> <x2> <y2> ... <xn> <yn>
        """
        try:
            annotations = self.annotation_manager.get_all_annotations()
            if not annotations:
                return False
            
            categories = self.category_manager.get_ordered_categories()
            category_to_index = {name: idx for idx, name in enumerate(categories)}
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for annotation in annotations:
                    if not annotation.visible or not annotation.points or len(annotation.points) < 3:
                        continue
                    
                    if annotation.type not in ['polygon', 'mask', 'circle', 'annulus']:
                        continue
                        
                    class_id = category_to_index.get(annotation.category, 0)
                    
                    norm_points = []
                    for pt in annotation.points:
                        nx = max(0.0, min(1.0, pt[0] / image_width))
                        ny = max(0.0, min(1.0, pt[1] / image_height))
                        norm_points.append(f"{nx:.6f}")
                        norm_points.append(f"{ny:.6f}")
                    
                    f.write(f"{class_id} " + " ".join(norm_points) + "\n")
            return True
        except Exception as e:
            print(f"YOLO-Seg export failed: {e}")
            return False


class YOLOOBBExporter(FormatExporter):
    """YOLOv8 OBB Format Exporter (Rotated BBox)"""
    
    def export(self, output_path: str, image_width: int, image_height: int, 
               image_filename: str = None) -> bool:
        """
        YOLO-OBB format export: <class_id> <x1> <y1> <x2> <y2> <x3> <y3> <x4> <y4>
        """
        try:
            annotations = self.annotation_manager.get_all_annotations()
            if not annotations:
                return False
            
            categories = self.category_manager.get_ordered_categories()
            category_to_index = {name: idx for idx, name in enumerate(categories)}
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for annotation in annotations:
                    if not annotation.visible or not annotation.points:
                        continue
                        
                    if annotation.type not in ['rotated_rect', 'rectangle', 'circle', 'annulus']:
                        continue
                        
                    class_id = category_to_index.get(annotation.category, 0)
                    
                    corners = []
                    if annotation.type == 'rotated_rect' and len(annotation.points) >= 4:
                        corners = annotation.points[:4]
                    else:
                        # rectangle conversion
                        x, y, w, h = annotation.get_bounding_box()
                        corners = [[x, y], [x+w, y], [x+w, y+h], [x, y+h]]
                    
                    norm_points = []
                    for pt in corners:
                        nx = max(0.0, min(1.0, pt[0] / image_width))
                        ny = max(0.0, min(1.0, pt[1] / image_height))
                        norm_points.append(f"{nx:.6f}")
                        norm_points.append(f"{ny:.6f}")
                    
                    while len(norm_points) < 8:
                        norm_points.extend(["0.000000", "0.000000"])
                        
                    f.write(f"{class_id} " + " ".join(norm_points[:8]) + "\n")
            return True
        except Exception as e:
            print(f"YOLO-OBB export failed: {e}")
            return False


class COCOExporter(FormatExporter):
    """COCO Format Exporter"""
    
    def export(self, output_path: str, image_width: int, image_height: int, 
               image_filename: str = None, start_index: int = 1) -> bool:
        try:
            annotations = self.annotation_manager.get_all_annotations()
            if not annotations:
                return False
            
            categories = self.category_manager.get_all_categories()
            # Support selectable start_index (0 or 1)
            category_id_map = {name: idx + start_index for idx, name in enumerate(categories.keys())}
            
            coco_data = {
                "info": {
                    "description": "wxCvAnnotator Export",
                    "version": "1.0",
                    "year": datetime.now().year,
                    "date_created": datetime.now().isoformat()
                },
                "images": [{
                    "id": 1,
                    "file_name": image_filename or "image.jpg",
                    "width": image_width,
                    "height": image_height,
                    "date_captured": datetime.now().isoformat()
                }],
                "annotations": [],
                "categories": []
            }
            
            for category, color in categories.items():
                coco_data["categories"].append({
                    "id": category_id_map[category],
                    "name": category,
                    "supercategory": "object",
                    "color": color
                })
            
            for idx, annotation in enumerate(annotations):
                if not annotation.visible or not annotation.points:
                    continue
                
                bbox = annotation.get_bounding_box()
                coco_data["annotations"].append({
                    "id": idx + 1,
                    "image_id": 1,
                    "category_id": category_id_map.get(annotation.category, start_index),
                    "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                    "area": bbox[2] * bbox[3],
                    "iscrowd": 0,
                    "segmentation": self._annotation_to_segmentation(annotation)
                })
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(coco_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"COCO export failed: {e}")
            return False

    def export_dataset(self, output_path: str, images: List[str], 
                      image_dimensions: List[Tuple[int, int]], start_index: int = 1) -> bool:
        try:
            categories = self.category_manager.get_all_categories()
            category_id_map = {name: idx + start_index for idx, name in enumerate(categories.keys())}
            
            coco_data = {
                "info": {
                    "description": "wxCvAnnotator Batch Export",
                    "version": "1.0",
                    "year": datetime.now().year,
                    "date_created": datetime.now().isoformat()
                },
                "images": [],
                "annotations": [],
                "categories": []
            }
            
            for category, color in categories.items():
                coco_data["categories"].append({"id": category_id_map[category], "name": category})
            
            ann_id = 1
            for img_idx, (img_file, (width, height)) in enumerate(zip(images, image_dimensions)):
                img_path = Path(img_file)
                json_path = img_path.with_suffix('.json')
                
                if not json_path.exists(): continue
                
                coco_data["images"].append({
                    "id": img_idx + 1,
                    "file_name": img_path.name,
                    "width": width,
                    "height": height
                })
                
                temp_manager = AnnotationManager()
                if temp_manager.load_from_file(str(json_path)):
                    for annotation in temp_manager.get_all_annotations():
                        if not annotation.visible or not annotation.points: continue
                        bbox = annotation.get_bounding_box()
                        coco_data["annotations"].append({
                            "id": ann_id,
                            "image_id": img_idx + 1,
                            "category_id": category_id_map.get(annotation.category, start_index),
                            "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                            "area": bbox[2] * bbox[3],
                            "iscrowd": 0,
                            "segmentation": self._annotation_to_segmentation(annotation)
                        })
                        ann_id += 1
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(coco_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"COCO dataset export failed: {e}")
            return False
    
    def _annotation_to_segmentation(self, annotation: Annotation) -> List[List[float]]:
        if annotation.type == "rectangle":
            x, y, w, h = annotation.get_bounding_box()
            return [[x, y, x + w, y, x + w, y + h, x, y + h]]
        elif annotation.type == "polygon":
            points = []
            for x, y in annotation.points:
                points.extend([x, y])
            return [points]
        return []


class PascalVOCExporter(FormatExporter):
    """Pascal VOC Format Exporter"""
    
    def export(self, output_path: str, image_width: int, image_height: int, 
               image_filename: str = None) -> bool:
        """Pascal VOC 2012 Specification"""
        try:
            annotations = self.annotation_manager.get_all_annotations()
            if not annotations: return False
            
            root = ET.Element("annotation")
            ET.SubElement(root, "folder").text = "VOC2012"
            ET.SubElement(root, "filename").text = image_filename or "image.jpg"
            
            source = ET.SubElement(root, "source")
            ET.SubElement(source, "database").text = "wxCvAnnotator_Database"
            ET.SubElement(source, "annotation").text = "PASCAL VOC 2012"
            ET.SubElement(source, "image").text = "flickr"
            
            size = ET.SubElement(root, "size")
            ET.SubElement(size, "width").text = str(image_width)
            ET.SubElement(size, "height").text = str(image_height)
            ET.SubElement(size, "depth").text = "3"
            
            ET.SubElement(root, "segmented").text = "0"
            
            for annotation in annotations:
                if not annotation.visible or not annotation.points: continue
                obj = ET.SubElement(root, "object")
                ET.SubElement(obj, "name").text = annotation.category
                ET.SubElement(obj, "pose").text = "Unspecified"
                ET.SubElement(obj, "truncated").text = "0"
                ET.SubElement(obj, "difficult").text = "0"
                
                bndbox = ET.SubElement(obj, "bndbox")
                bbox = annotation.get_bounding_box()
                # Standard VOC is 1-based, using rounded integers
                ET.SubElement(bndbox, "xmin").text = str(max(1, int(bbox[0]) + 1))
                ET.SubElement(bndbox, "ymin").text = str(max(1, int(bbox[1]) + 1))
                # Add 1 to xmax/ymax as well to wrap around the pixels
                ET.SubElement(bndbox, "xmax").text = str(min(image_width, int(bbox[0] + bbox[2]) + 1))
                ET.SubElement(bndbox, "ymax").text = str(min(image_height, int(bbox[1] + bbox[3]) + 1))
            
            ET.ElementTree(root).write(output_path, encoding='utf-8', xml_declaration=True)
            return True
        except Exception as e:
            print(f"Pascal VOC export failed: {e}")
            return False


class CSVExporter(FormatExporter):
    """CSV Format Exporter"""
    
    def export(self, output_path: str, image_width: int, image_height: int, 
               image_filename: str = None) -> bool:
        try:
            annotations = self.annotation_manager.get_all_annotations()
            if not annotations: return False
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['filename', 'type', 'category', 'x_min', 'y_min', 'x_max', 'y_max'])
                for annotation in annotations:
                    if not annotation.visible or not annotation.points: continue
                    x, y, w, h = annotation.get_bounding_box()
                    writer.writerow([image_filename or "image.jpg", annotation.type, annotation.category, 
                                   round(x, 2), round(y, 2), round(x+w, 2), round(y+h, 2)])
            return True
        except Exception as e:
            print(f"CSV export failed: {e}")
            return False

    def export_dataset(self, output_path: str, images: List[str], 
                      image_dimensions: List[Tuple[int, int]]) -> bool:
        """Batch export aggregate CSV"""
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['filename', 'type', 'category', 'x_min', 'y_min', 'x_max', 'y_max'])
                for img_file, (width, height) in zip(images, image_dimensions):
                    img_path = Path(img_file)
                    json_path = img_path.with_suffix('.json')
                    if not json_path.exists(): continue
                    
                    temp_manager = AnnotationManager()
                    if temp_manager.load_from_file(str(json_path)):
                        for ann in temp_manager.get_all_annotations():
                            if not ann.visible or not ann.points: continue
                            x, y, w, h = ann.get_bounding_box()
                            writer.writerow([img_path.name, ann.type, ann.category, 
                                           round(x, 2), round(y, 2), round(x+w, 2), round(y+h, 2)])
            return True
        except Exception as e:
            print(f"CSV batch export failed: {e}")
            return False


class ExportSystem:
    """Annotation Export System Manager"""
    
    SUPPORTED_FORMATS = {
        'yolo': YOLOExporter,
        'yolo_detect': YOLOExporter,
        'yolo_seg': YOLOSegExporter,
        'yolo_obb': YOLOOBBExporter,
        'coco': COCOExporter,
        'pascal_voc': PascalVOCExporter,
        'csv': CSVExporter
    }
    
    def __init__(self, annotation_manager: AnnotationManager, category_manager: CategoryManager):
        self.annotation_manager = annotation_manager
        self.category_manager = category_manager
        self.exporters = {name: cls(annotation_manager, category_manager) 
                         for name, cls in self.SUPPORTED_FORMATS.items()}
    
    def get_supported_formats(self) -> List[str]:
        return list(self.SUPPORTED_FORMATS.keys())
    
    def get_format_description(self, format_name: str) -> str:
        descriptions = {
            'yolo': 'YOLO Darknet Format',
            'yolo_detect': 'YOLO Detection (Bounding Box)',
            'yolo_seg': 'YOLOv8 Segmentation (Polygon)',
            'yolo_obb': 'YOLOv8 OBB (Rotated Rect)',
            'coco': 'Microsoft COCO Format',
            'pascal_voc': 'Pascal VOC Format',
            'csv': 'CSV Format'
        }
        return descriptions.get(format_name, 'Unknown Format')
    
    def export_to_format(self, format_name: str, output_path: str, 
                        image_width: int, image_height: int, 
                        image_filename: str = None) -> bool:
        if format_name not in self.exporters: return False
        return self.exporters[format_name].export(output_path, image_width, image_height, image_filename)
    
    def batch_export(self, format_name: str, output_dir: str, 
                    image_files: List[str], image_dimensions: List[Tuple[int, int]]) -> Dict[str, bool]:
        if format_name not in self.exporters: return {}
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Auto-detect dimensions if missing
        processed_dims = []
        for i, (w, h) in enumerate(image_dimensions):
            if w <= 0 or h <= 0:
                try:
                    import wx
                    img = wx.Image(image_files[i])
                    processed_dims.append((img.GetWidth(), img.GetHeight()) if img.IsOk() else (0,0))
                except: processed_dims.append((0, 0))
            else: processed_dims.append((w, h))
        
        results = {}
        # Handle format mapping for simple batch export
        s_idx = settings.get("coco_start_index", 1)
        actual_fmt = format_name
        
        if format_name == 'coco_0':
            actual_fmt = 'coco'
            s_idx = 0
        elif format_name == 'coco_1':
            actual_fmt = 'coco'
            s_idx = 1
        elif format_name == 'voc_2012':
            actual_fmt = 'pascal_voc'
            
        if actual_fmt not in self.exporters: return {}
        
        if actual_fmt == 'yolo' or actual_fmt == 'coco': # aggregate formats
             exporter = self.exporters[actual_fmt]
             if actual_fmt == 'coco':
                 success = exporter.export_dataset(str(output_path / "annotations.json"), image_files, processed_dims, start_index=s_idx)
             else:
                 success = exporter.export_dataset(output_dir, image_files, processed_dims)
             for i in image_files: results[Path(i).name] = success
             return results

        # File-per-file formats
        for img_file, (width, height) in zip(image_files, processed_dims):
            img_p = Path(img_file)
            ext = 'xml' if format_name == 'pascal_voc' else 'csv'
            results[img_p.name] = self.export_to_format(format_name, str(output_path / f"{img_p.stem}.{ext}"), 
                                                      width, height, img_p.name)
        return results

    def batch_export_advanced(self, settings: Dict[str, Any], image_files: List[str], 
                              image_dimensions: List[Tuple[int, int]],
                              progress_callback=None) -> Dict[str, bool]:
        """Advanced batch export with splitting and directory structure"""
        import yaml
        format_name = settings["format"]
        output_path = Path(settings["output_dir"])
        honor_manual = settings["honor_manual"]
        copy_images = settings["copy_images"]
        
        # 1. Analyze and Split
        fixed_files = {"train": [], "val": [], "test": []}
        unassigned_files = []
        
        for img_path in image_files:
            assigned = False
            if honor_manual:
                json_path = Path(img_path).with_suffix('.json')
                if json_path.exists():
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            status = data.get("status", "none").lower()
                            if status in fixed_files:
                                fixed_files[status].append(img_path)
                                assigned = True
                    except: pass
            if not assigned: unassigned_files.append(img_path)
        
        random.shuffle(unassigned_files)
        total_p = settings["train_ratio"] + settings["val_ratio"] + settings["test_ratio"]
        if total_p > 0:
            t_cnt = int(len(unassigned_files) * settings["train_ratio"] / total_p)
            v_cnt = int(len(unassigned_files) * settings["val_ratio"] / total_p)
        else: t_cnt = v_cnt = 0
            
        splits = {
            "train": fixed_files["train"] + unassigned_files[:t_cnt],
            "valid": fixed_files["val"] + unassigned_files[t_cnt:t_cnt+v_cnt],
            "test": fixed_files["test"] + unassigned_files[t_cnt+v_cnt:]
        }
        
        results = {}
        processed_count = 0
        
        # 2. Export each split
        for split_name, split_files in splits.items():
            if not split_files: continue
            split_dir = output_path / split_name
            split_img_dir = split_dir / "images"
            split_img_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy images
            for f_path in split_files:
                if copy_images: shutil.copy2(f_path, split_img_dir / Path(f_path).name)

            # Determine split dimensions
            split_dims = []
            for f in split_files:
                try:
                    idx = image_files.index(f)
                    w, h = image_dimensions[idx]
                except: w, h = 0, 0
                
                if w <= 0:
                    try:
                        import wx
                        img = wx.Image(f)
                        if img.IsOk(): w, h = img.GetWidth(), img.GetHeight()
                    except: pass
                split_dims.append((w, h))

            # Handle aggregate formats
            if format_name in ['coco', 'csv']:
                exporter = self.exporters[format_name]
                ext = 'json' if format_name == 'coco' else 'csv'
                
                if format_name == 'coco':
                    s_idx = settings.get("coco_start_index", 1)
                    success = exporter.export_dataset(str(split_dir / f"annotations.{ext}"), split_files, split_dims, start_index=s_idx)
                else: # csv
                    success = exporter.export_dataset(str(split_dir / f"annotations.{ext}"), split_files, split_dims)
                    
                for f in split_files: 
                    results[Path(f).name] = success
                    processed_count += 1
                    if progress_callback: progress_callback(processed_count, f"Exported {Path(f).name}")
            else:
                # Per-file formats (YOLO, Pascal VOC)
                split_lbl_dir = split_dir / "labels"
                if format_name.startswith("yolo"): split_lbl_dir.mkdir(parents=True, exist_ok=True)
                
                for f_path, (w, h) in zip(split_files, split_dims):
                    img_p = Path(f_path)
                    temp_manager = AnnotationManager()
                    json_path = img_p.with_suffix('.json')
                    if json_path.exists():
                        try: temp_manager.load_from_file(str(json_path))
                        except: pass
                    
                    exporter_cls = self.SUPPORTED_FORMATS.get(format_name, YOLOExporter)
                    exporter = exporter_cls(temp_manager, self.category_manager)
                    
                    if format_name == 'pascal_voc':
                        ext = 'xml'
                        lbl_path = split_dir / f"{img_p.stem}.{ext}"
                    else: # yolo
                        ext = 'txt'
                        lbl_path = split_lbl_dir / f"{img_p.stem}.{ext}"
                    
                    results[img_p.name] = exporter.export(str(lbl_path), w, h, img_p.name)
                    processed_count += 1
                    if progress_callback: progress_callback(processed_count, f"Exported {img_p.name}")

        # 3. Project Configs (YOLO)
        if format_name.startswith("yolo"):
            cats = self.category_manager.get_ordered_categories()
            data_yaml = {'train': 'train/images', 'val': 'valid/images', 'test': 'test/images', 'nc': len(cats), 'names': cats}
            with open(output_path / "data.yaml", 'w', encoding='utf-8') as yf:
                yaml.safe_dump(data_yaml, yf, allow_unicode=True, default_flow_style=False)
                
            with open(output_path / "classes.txt", 'w', encoding='utf-8') as cf:
                for cat in cats: cf.write(f"{cat}\n")

        return results