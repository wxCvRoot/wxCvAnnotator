#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Display Panel - Integrated with wxCvROIAdvPanel and implements annotation features
Handles onCrop events, creates and manages annotation data.
"""

import wx
import wx.lib.agw.customtreectrl as CT
from pathlib import Path
import numpy as np
from typing import Optional, Callable, List, Tuple, Dict, Any
from .i18n import _
import math
import threading
from datetime import datetime
import cv2

import sys as _sys
from pathlib import Path as _Path

# Dev lib override: prepend package-local lib/ if it contains wxCvModule binaries
_lib_path = _Path(__file__).parent.parent / "lib"
if _lib_path.exists() and any(_lib_path.iterdir()):
    _sys.path.insert(0, str(_lib_path))

import wx as _wx  # macOS: must import wx before wxCvModule
try:
    import wxCvModule
except ImportError:
    wxCvModule = None

# Import annotation system
from .annotation_system import (
    AnnotationManager, Annotation,
    create_rectangle_annotation, create_polygon_annotation,
    create_rotated_rectangle_annotation, create_circle_annotation,
    create_point_annotation, create_annulus_annotation, create_line_annotation,
    create_mask_annotation,
    DEFAULT_CATEGORY_COLORS
)

# Import AI service
from ..utils.ai_service import AIService


class ImageDisplayPanel(wx.Panel):
    """Image Display Panel - Integrated with wxCvROIAdvPanel"""
    
    def __init__(self, parent, settings_manager=None):
        """Initialize Image Display Panel"""
        super().__init__(parent, wx.ID_ANY)
        
        self.settings_manager = settings_manager
        
        # Annotation Manager
        self.annotation_manager = AnnotationManager()
        
        self.current_tool = "select"  # Default tool
        self.current_category = "defect"
        self.current_color = DEFAULT_CATEGORY_COLORS.get("defect", "#FF0000")
        
        # C++ Panel reference
        self.cv_panel = None
        
        # Image info
        self.current_image_path = None
        self.current_image_mat = None # Cache for AI
        self.current_image_channels = 0  # Original channel count before normalization
        self.image_size = (0, 0)
        
        # Annotation state
        self.is_creating_annotation = False
        self.selected_annotation_id = None
        
        # ROI tracking state (for completion detection)
        self.roi_tracking_enabled = False
        self.last_mouse_down = (0, 0)
        self.last_mouse_up = (0, 0)
        self.roi_polling_timer = None
        self.previous_roi_state = {}
        
        # Callbacks
        self.on_annotation_changed: Optional[Callable] = None
        self.on_selection_changed: Optional[Callable] = None
        self.on_status_update: Optional[Callable] = None
        self.on_ui_lock: Optional[Callable] = None # [REQ-010]
        self.on_pos_update: Optional[Callable] = None  # (x, y, zoom_or_None)
        
        # [REQ-010] AI State
        model_dir = "models"
        if settings_manager:
            stored_path = settings_manager.get("ai_model_path", "models")
            _p = Path(stored_path)
            # If an absolute path was saved on a different OS and is not usable here, reset to default
            if _p.is_absolute():
                try:
                    _p.mkdir(parents=True, exist_ok=True)
                    model_dir = stored_path
                except (OSError, PermissionError):
                    print(f"⚠️ AI model path '{stored_path}' is not accessible on this OS, resetting to 'models'.")
                    settings_manager.set("ai_model_path", "models")
                    model_dir = "models"
            else:
                model_dir = stored_path

        self.ai_service = AIService(model_dir=model_dir)
        self.ai_prompts = []  # List of {"pos": (x, y), "label": 1 or 0}
        self.ai_preview_poly = []
        self.ai_preview_mask = None  # numpy uint8 binary mask for ai_mask mode
        self.last_ai_click_pt = (-1, -1)
        self.current_ai_model = "EfficientSAM (speed)"
        self._ai_right_neg_timer = None      # wx.CallLater for deferred negative prompt
        self._ai_pending_neg_pos = None      # (x, y) of pending negative prompt
        self._ai_right_dclick_done = False   # Suppress right-click callback trailing a dclick
        
        # Category Manager reference
        self.category_manager = None
        self.ROI_MODE_MAPPING = {
            "select": 0,         # Select/Edit mode
            "rotated_rect": 4,   # Rotated rectangle mode
            "polygon": 7,        # Polygon mode
            "rectangle": 3,      # Rectangle mode
            "circle": 5,         # Circle mode
            "annulus": 6,        # Annulus mode
            "point": 1,          # Point mode
            "ai_polygon": 0,     # AI mode (Use Select mode in C++ to avoid ROI drawing)
            "ai_mask": 0,        # AI mode
        }
        
        # Setup UI
        self._setup_ui()
        self._bind_events()
        
        # Initialize C++ panel on show
        self.Bind(wx.EVT_SHOW, self._on_panel_show)
        
        # Attempt immediate init (if window already displayed)
        self._attempt_init_cv_panel()
        
        # New: AI Optimization state
        self.last_ai_inference_time = 0
        self.ai_mouse_pos = wx.Point(-1, -1)
    
    def _attempt_init_cv_panel(self):
        """Attempt to initialize C++ panel (single attempt)"""
        if self.cv_panel is None:
            wx.CallAfter(self._init_cv_panel)
    
    def _setup_ui(self):
        """Setup UI layout"""
        # Main layout
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.main_sizer)
        
        # Create C++ container
        self.cv_container = wx.Panel(self, wx.ID_ANY)
        # Use a lighter gray that is distinctly different from both black and white.
        # This is closer to Photoshop's "Medium Gray" workspace.
        self.workspace_bg_color = wx.Colour(100, 100, 105) 
        self.cv_container.SetBackgroundColour(self.workspace_bg_color)
        
        # Add a margin (5px) to ensure the container background color is visible
        # as a frame around the C++ ROI panel.
        self.main_sizer.Add(self.cv_container, 1, wx.EXPAND | wx.ALL, 5)
        
        # Bind events
        self.cv_container.Bind(wx.EVT_SIZE, self._on_container_resize)
        self.cv_container.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu_legacy)
    
    def _bind_events(self):
        """Bind event handlers"""
        self.Bind(wx.EVT_PAINT, self._on_paint)
        # Keyboard events [REQ-010]
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        
    def _on_panel_show(self, event):
        """Initialize C++ panel on first show"""
        if event.IsShown() and self.cv_panel is None:
            # Increased delay to ensure handle is valid
            wx.CallLater(300, self._init_cv_panel)
            print("✓ Show event received, scheduling C++ panel init (300ms delay)")
        event.Skip()
    
    def _on_container_resize(self, event):
        """Handle container resize"""
        if self.cv_panel and self.cv_panel.IsOk():
            size = self.cv_container.GetSize()
            self.cv_panel.SetSize(size.width, size.height)
            self.cv_panel.Refresh()
        event.Skip()
    
    def _init_cv_panel(self):
        """Initialize C++ panel"""
        if wxCvModule is None:
            print("✗ wxCvModule not found")
            return

        try:
            if not self.cv_container:
                print("✗ C++ container not found")
                return
                
            container_handle = self.cv_container.GetHandle()
            container_size = self.cv_container.GetSize()
            
            if container_handle == 0:
                print("✗ Invalid container handle, retrying...")
                import time
                time.sleep(0.1)
                container_handle = self.cv_container.GetHandle()
                if container_handle == 0:
                    print("✗ Container handle still invalid, aborting init")
                    return
            
            print(f"=== Initializing wxCvROIAdvPanel ===")
            print(f"Handle: {hex(container_handle)}")
            print(f"Size: {container_size.width}x{container_size.height}")
            
            self.cv_panel = wxCvModule.wxCvROIAdvPanel(
                container_handle, wx.ID_ANY, -1, -1, 
                container_size.width, container_size.height
            )
            
            if not self.cv_panel or not self.cv_panel.IsOk():
                print("✗ C++ panel failed to initialize")
                return
            
            # Enable ROI features
            self.cv_panel.SetFuncEnable(True, True, True)
            # [REQ-006] We will use the return value of the callback to intercept the menu
            self.cv_panel.SetMenuROIEnable(True, True, True, True, True, True, True)
            print("✓ C++ internal menu enabled (Python callback can intercept)")
            
            # [REQ-010] Callbacks and onCrop are primary.
            if hasattr(self.cv_panel, 'SetOnCropCallback'):
                self.cv_panel.SetOnCropCallback(self._on_crop_callback)
                print("✓ Python onCrop callback registered")
            else:
                self._bind_roi_events_polling()
            
            # [REQ-006] Register Right-click Callback
            if hasattr(self.cv_panel, 'SetOnRightClickCallback'):
                self.cv_panel.SetOnRightClickCallback(self._on_python_right_click)
                print("✓ Python right-click callback registered")
            
            # [REQ-004] Set canvas background color (C++ side)
            if hasattr(self.cv_panel, 'SetCanvasBgColor'):
                bg = self.workspace_bg_color.Get()
                # Pass RGB to C++ API
                self.cv_panel.SetCanvasBgColor(bg[0], bg[1], bg[2])
                print(f"✓ Canvas background set to {bg}")
            
            # [REQ-005] Enable image centering in canvas
            if hasattr(self.cv_panel, 'SetCenterImageEnable'):
                self.cv_panel.SetCenterImageEnable(True)
                print("✓ Image centering enabled")
            
            print("✓ C++ panel initialized successfully")
            
            # Set default tool
            self.set_tool(self.current_tool)
            
            # [REQ-010] Bind Mouse events (Motion and DClick will need REQ-010 C++ implementation)
            # self.cv_panel.Bind(wx.EVT_MOTION, self._on_ai_mouse_move) 
            # self.cv_panel.Bind(wx.EVT_LEFT_DCLICK, self._on_ai_double_click_left)
            # self.cv_panel.Bind(wx.EVT_RIGHT_DCLICK, self._on_ai_double_click_right)
            
            # [REQ-010] Revert to container Bind for single-click as fallback
            self.cv_container.Bind(wx.EVT_LEFT_DOWN, self._on_ai_mouse_down)
            print("✓ Python left-click binding on container restored")
             
            # [REQ-010] Register New Mouse Callbacks
            if hasattr(self.cv_panel, 'SetOnLeftDClickCallback'):
                self.cv_panel.SetOnLeftDClickCallback(self._on_ai_double_click_left_cv)
                print("✓ Python left double-click callback registered")
            
            if hasattr(self.cv_panel, 'SetOnRightDClickCallback'):
                self.cv_panel.SetOnRightDClickCallback(self._on_ai_double_click_right_cv)
                print("✓ Python right double-click callback registered")
                
            if hasattr(self.cv_panel, 'SetOnMouseMoveCallback'):
                self.cv_panel.SetOnMouseMoveCallback(self._on_ai_mouse_move_cv)
                print("✓ Python mouse move callback registered")
            
        except Exception as e:
            print(f"✗ Failed to init C++ panel: {e}")
            import traceback
            traceback.print_exc()
    
    def _bind_roi_events_polling(self):
        """Fallback to polling if SetOnCropCallback is not supported"""
        try:
            self.roi_tracking_enabled = True
            self.roi_polling_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_roi_polling_timer, self.roi_polling_timer)
            self.roi_polling_timer.Start(150) # 150ms interval for balance
            print("✓ AI/ROI polling timer started")
        except Exception as e:
            print(f"Failed to bind polling: {e}")

    def _on_roi_polling_timer(self, event):
        """Timer callback for polling ROI changes and AI clicks"""
        if not self.cv_panel or not self.cv_panel.IsOk():
            return

        # [REQ-010] AI Left-click Polling Fallback
        if self.current_tool.startswith("ai_"):
            try:
                # Get the last left mouse down point from C++
                pt = self.cv_panel.GetLeftMouseDownPoint()
                if pt != self.last_ai_click_pt:
                    # Valid range check (roughly)
                    if pt[0] >= 0 and pt[1] >= 0:
                        self.last_ai_click_pt = pt
                        self._on_ai_click_polled(pt)
                # else:
                #     print(f"DEBUG: AI Polling - no point change ({pt})")
            except Exception as e:
                pass

    def _on_crop_callback(self, rect):
        """Handle onCrop event from C++ panel"""
        # Guard 1: C++ sometimes fires this callback with a raw bytes object
        # (e.g. when SetRect / SetROIMode is called internally).  Reject those.
        if isinstance(rect, (bytes, bytearray)):
            return

        # Guard 2: Reject (0,0,0,0) callbacks — spurious fires from SetRect /
        # SetROIMode / SetPolygonPoints called internally.  A real user click
        # always produces at least one non-zero coordinate (or non-zero w/h for
        # shapes).  Only reject when ALL four values are zero.
        try:
            if rect[0] == 0 and rect[1] == 0 and rect[2] == 0 and rect[3] == 0:
                return
        except (IndexError, TypeError):
            return

        print(f"DEBUG: _on_crop_callback rect={rect}, tool={self.current_tool}")

        # [REQ-010] AI Prompt Detection via standard Point tool (Mode 1)
        if self.current_tool.startswith("ai_"):
             # For a point ROI, rect[0] and rect[1] is the click point.
             pt = (rect[0], rect[1])
             print(f"🤖 AI Click (via onCrop): {pt}")
             self._add_ai_prompt(pt[0], pt[1], 1)

             # Defer SetRect to the next event-loop turn via CallAfter so that
             # it does NOT re-fire _on_crop_callback from within this callback.
             # _clear_ai_crop_roi also re-runs sync_overlays so UpdateDrawImage(True)
             # happens after SetRect, keeping the mask overlay visible.
             wx.CallAfter(self._clear_ai_crop_roi)
             return

        if self.on_status_update:
            self.on_status_update(_("ROI Complete: Right-click image or use Toolbar/Enter to save"))

    def _clear_ai_crop_roi(self):
        """Clear the C++ ROI crosshair and re-sync overlays.

        Called via wx.CallAfter from _on_crop_callback so that SetRect is
        executed in the next event-loop turn, outside the C++ callback scope.
        This prevents SetRect from re-firing _on_crop_callback recursively.
        """
        if self.cv_panel and self.cv_panel.IsOk():
            self.cv_panel.SetRect((0, 0, 0, 0))
            self.sync_overlays()

    def _prompt_for_category(self) -> Optional[str]:
        """Pop up dialog for category selection"""
        if self.category_manager:
            categories = self.category_manager.get_ordered_categories()
        else:
            categories = list(DEFAULT_CATEGORY_COLORS.keys())
            
        dlg = wx.SingleChoiceDialog(self, _("Select Category:"), _("Category"), categories)
        dlg.SetSelection(categories.index(self.current_category) if self.current_category in categories else 0)
        
        if dlg.ShowModal() == wx.ID_OK:
            cat = dlg.GetStringSelection()
            self.current_category = cat
            if self.category_manager:
                self.current_color = self.category_manager.get_color(cat)
            else:
                self.current_color = DEFAULT_CATEGORY_COLORS.get(cat, "#888888")
            return cat
        return None

    def _extract_current_roi_state_ext(self, mode, rect) -> Optional[Dict[str, Any]]:
        """Extract detailed ROI data"""
        try:
            roi_type = self._mode_to_annotation_type(mode)
            data = {"type": roi_type, "rect": rect, "mode": mode}
            
            if mode == 7:  # Polygon
                pts = self.cv_panel.GetPolygonPoints()
                data["points"] = [(p[0], p[1]) for p in pts]
            elif mode == 4:  # RotatedRectangle
                data["angle"] = self.cv_panel.GetRotateAngle()
            elif mode == 5:  # Circle
                data["center_x"] = rect[0]
                data["center_y"] = rect[1]
                data["outer_radius"] = self.cv_panel.GetOuterRadius()
                if data["outer_radius"] <= 0:
                    data["outer_radius"] = rect[2]  # Fallback
            elif mode == 6:  # Annulus
                data["center_x"] = rect[0]
                data["center_y"] = rect[1]
                data["outer_radius"] = self.cv_panel.GetOuterRadius()
                if data["outer_radius"] <= 0:
                    data["outer_radius"] = rect[2]  # Fallback
                data["inner_radius"] = self.cv_panel.GetInnerRadius()
                data["start_angle"] = self.cv_panel.GetStartAngle()
                data["end_angle"] = self.cv_panel.GetEndAngle()
            elif mode == 2:  # Line
                data["p1"] = self.cv_panel.GetLeftMouseDownPoint()
                data["p2"] = self.cv_panel.GetLeftMouseUpPoint()
            
            return data
        except Exception as e:
            print(f"Failed to extract data: {e}")
            return None

    def _create_annotation_from_roi_data(self, data: Dict[str, Any]):
        """Create Annotation object from data"""
        ann_type = data["type"]
        rect = data["rect"]
        cat = data.get("category", self.current_category)
        
        if self.category_manager:
            color = self.category_manager.get_color(cat)
        else:
            color = DEFAULT_CATEGORY_COLORS.get(cat, self.current_color)
        
        annotation = None
        if ann_type == "polygon":
            annotation = create_polygon_annotation(data["points"], cat, color)
        elif ann_type == "rotated_rect":
            annotation = create_rotated_rectangle_annotation(
                rect[0], rect[1], rect[2], rect[3], data.get("angle", 0.0), cat, color
            )
        elif ann_type == "rectangle":
            annotation = create_rectangle_annotation(rect[0], rect[1], rect[2], rect[3], cat, color)
        elif ann_type == "circle":
            center_x = data.get("center_x", rect[0])
            center_y = data.get("center_y", rect[1])
            radius = data.get("outer_radius", rect[2])
            annotation = create_circle_annotation(center_x, center_y, radius, cat, color)
        elif ann_type == "annulus":
            center_x = data.get("center_x", rect[0])
            center_y = data.get("center_y", rect[1])
            outer_radius = data.get("outer_radius", rect[2])
            inner_radius = data.get("inner_radius", -1)
            if inner_radius <= 0:
                 inner_radius = outer_radius * 0.5
            
            start_angle = data.get("start_angle", 0.0)
            end_angle = data.get("end_angle", 360.0)
            annotation = create_annulus_annotation(center_x, center_y, inner_radius, outer_radius, start_angle, end_angle, cat, color)
        elif ann_type == "point":
            annotation = create_point_annotation(rect[0], rect[1], cat, color)
        elif ann_type == "line":
            p1 = data.get("p1", (rect[0], rect[1]))
            p2 = data.get("p2", (rect[0] + rect[2], rect[1] + rect[3]))
            annotation = create_line_annotation(p1, p2, cat, color)
        
        if annotation:
            annotation.label = cat
            self.annotation_manager.add_annotation(annotation)
            return True
        return False

    def sync_overlays(self):
        """Sync annotations to C++ panel overlays"""
        if not self.cv_panel or not self.cv_panel.IsOk():
            return
            
        self.cv_panel.ClearOverlay()
        for ann in self.annotation_manager.get_all_annotations():
            if not ann.visible: continue
            
            # Skip if editing in ROI mode
            if ann.id == self.selected_annotation_id and self.cv_panel.GetROIMode() != 0:
                continue

            is_selected = (ann.id == self.selected_annotation_id)
            color = self._hex_to_bgr(ann.color)
            thickness = 1  # Standard thickness to 1
            
            if ann.type == "polygon":
                self.cv_panel.AppendOverlay(7, ann.points, color, thickness)
            elif ann.type in ["rotated_rectangle", "rotated_rect"]:
                x = ann.attributes.get("x", ann.points[0][0])
                y = ann.attributes.get("y", ann.points[0][1])
                w = ann.attributes.get("width", 0)
                h = ann.attributes.get("height", 0)
                angle = ann.attributes.get("angle", 0.0)
                self.cv_panel.AppendOverlay(4, [(x, y), (w, h)], color, thickness, angle)
            elif ann.type == "rectangle":
                bbox = ann.get_bounding_box()
                # Fix: AppendOverlay for rectangle expects [(x, y), (w, h)] or similar? 
                # Checking other usages, it seems AppendOverlay might be overloaded.
                # For rect (mode 3), it likely expects rect struct or 2 points.
                # Previous code used: self.cv_panel.AppendOverlay(3, [(bbox[0], bbox[1]), (bbox[2], bbox[3])], color, thickness)
                # This seems to pass 2 points (top-left, bottom-right?) or (x,y), (w,h)? 
                # Let's assume consistent with RotatedRect usage above [(x, y), (w, h)].
                # bbox is (x, y, w, h). So [(x, y), (w, h)] is consistent.
                self.cv_panel.AppendOverlay(3, [(bbox[0], bbox[1]), (bbox[2], bbox[3])], color, thickness)
            elif ann.type == "circle":
                 center = (ann.attributes.get("center_x", 0), ann.attributes.get("center_y", 0))
                 radius = ann.attributes.get("radius", 10)
                 # Format from demo: [(cx, cy), (radius, 0)]
                 points = [center, (radius, 0)]
                 self.cv_panel.AppendOverlay(5, points, color, thickness)
            elif ann.type == "annulus":
                 center = (ann.attributes.get("center_x", 0), ann.attributes.get("center_y", 0))
                 inner_r = ann.attributes.get("inner_radius", 0)
                 outer_r = ann.attributes.get("outer_radius", 10)
                 start_a = ann.attributes.get("start_angle", 0)
                 end_a = ann.attributes.get("end_angle", 360)
                 # Format from demo: [(cx, cy), (0, 0), (inner_r, outer_r), (start_angle, end_angle)]
                 points = [center, (0, 0), (inner_r, outer_r), (start_a, end_a)]
                 self.cv_panel.AppendOverlay(6, points, color, thickness)
            elif ann.type == "point":
                self.cv_panel.AppendOverlay(1, ann.points, color, thickness + 3)
            elif ann.type == "line":
                self.cv_panel.AppendOverlay(2, ann.points, color, thickness)
            elif ann.type == "mask":
                # [REQ-007] Render Mask Overlay via C++ AppendMaskOverlay
                if not hasattr(self.cv_panel, 'AppendMaskOverlay'):
                    print("⚠️ AppendMaskOverlay not available in C++ panel — mask hidden")
                elif ann.mask_shape:
                    mask_arr = ann.get_mask_array()
                    if mask_arr is not None:
                        mask_arr = np.ascontiguousarray(mask_arr)
                        try:
                            self.cv_panel.AppendMaskOverlay(mask_arr, color, ann.mask_alpha)
                        except Exception as e:
                            print(f"❌ AppendMaskOverlay error: {e}")
                            # Fallback: draw contour outline
                            contours, _ = cv2.findContours(mask_arr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                            if contours:
                                main_c = max(contours, key=cv2.contourArea)
                                pts = [(float(p[0][0]), float(p[0][1])) for p in main_c]
                                if pts:
                                    self.cv_panel.AppendOverlay(7, pts, color, 2)
                        # Cache bounding box into ann.points on first render (avoids re-decode later)
                        if not ann.points:
                            ys, xs = np.where(mask_arr > 0)
                            if len(xs) > 0:
                                ann.points = [
                                    [float(xs.min()), float(ys.min())],
                                    [float(xs.max()), float(ys.max())],
                                ]
                        # Draw bounding box rectangle so the mask region is clearly visible
                        if ann.points and len(ann.points) >= 2:
                            x1, y1 = ann.points[0]
                            x2, y2 = ann.points[1]
                            self.cv_panel.AppendOverlay(
                                3, [(x1, y1), (x2 - x1, y2 - y1)], color, thickness
                            )

        # Draw AI Preview Overlay
        if self.current_tool.startswith("ai_"):
            if self.current_tool == "ai_mask":
                # Preview Mask Overlay
                if self.ai_preview_mask is not None and hasattr(self.cv_panel, 'AppendMaskOverlay'):
                    preview_color = (255, 200, 0)  # BGR: Yellow-ish
                    h, w = self.ai_preview_mask.shape[:2]
                    preview_arr = np.ascontiguousarray(self.ai_preview_mask)
                    try:
                        self.cv_panel.AppendMaskOverlay(preview_arr, preview_color, 0.5)
                    except Exception as e:
                        print(f"❌ Preview AppendMaskOverlay error: {e}")
                        # Fallback: draw contour outline
                        contours, _ = cv2.findContours(preview_arr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        if contours:
                            main_c = max(contours, key=cv2.contourArea)
                            pts = [(float(p[0][0]), float(p[0][1])) for p in main_c]
                            if pts:
                                self.cv_panel.AppendOverlay(7, pts, preview_color, 2)
            else:
                # Preview Prediction Polygon
                if self.ai_preview_poly:
                    preview_color = (255, 200, 0)  # BGR: Yellow-ish
                    self.cv_panel.AppendOverlay(7, self.ai_preview_poly, preview_color, 2)

            # Preview Prompt Points (always shown regardless of mode)
            for p in self.ai_prompts:
                dot_color = (0, 0, 255) if p["label"] == 0 else (0, 255, 0)  # Blue for Neg, Green for Pos
                self.cv_panel.AppendOverlay(1, [p["pos"]], dot_color, 8)
                
        self.cv_panel.SetDisplayOverlay(True)
        self.cv_panel.UpdateDrawImage(True)
        self.cv_panel.Refresh()

    def _hex_to_bgr(self, hex_color: str) -> Tuple[int, int, int]:
        """Hex to BGR for OpenCV colors"""
        hex_color = hex_color.lstrip('#')
        rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
        return (rgb[2], rgb[1], rgb[0])

    def _mode_to_annotation_type(self, mode: int) -> str:
        """Map ROI mode to annotation type"""
        mode_map = {1: "point", 2: "line", 3: "rectangle", 4: "rotated_rect", 5: "circle", 6: "annulus", 7: "polygon"}
        return mode_map.get(mode, "unknown")

    def _on_paint(self, event):
        """Handle paint event (overlays managed by C++)"""
        event.Skip()

    def set_category_manager(self, manager):
        """Pass category manager reference"""
        self.category_manager = manager

    def set_current_category(self, category: str):
        """Set current drawing category"""
        self.current_category = category
        
        # Get color from category manager if available
        if self.category_manager:
            self.current_color = self.category_manager.get_color(category)
        else:
            self.current_color = DEFAULT_CATEGORY_COLORS.get(category, "#888888")
        
        if self.on_status_update:
            self.on_status_update(_("Drawing Label: {}").format(category))

    def _on_category_changed(self, event):
        """Handle category change (deprecated)"""
        pass
    
    # --- Control API ---
    
    def zoom_in(self):
        if self.cv_panel: self.cv_panel.ZoomIn()
    
    def zoom_out(self):
        if self.cv_panel: self.cv_panel.ZoomOut()
    
    def zoom_fit(self):
        if self.cv_panel: self.cv_panel.SetZoomToFit()
        
    def _on_zoom_in(self, event):
        self.zoom_in()
    
    def _on_zoom_out(self, event):
        self.zoom_out()
    
    def _on_zoom_fit(self, event):
        self.zoom_fit()
    
    # Public API
    
    def set_tool(self, tool_type: str):
        """Set active annotation tool"""
        # Update ROI_MODE_MAPPING to include "annulus": 6.
        self.ROI_MODE_MAPPING = {
            "select": 0,
            "point": 1,
            "line": 2,
            "rectangle": 3,
            "rotated_rect": 4,
            "circle": 5,
            "annulus": 6, # Added annulus
            "polygon": 7,
            "ai_polygon": 1, # Map to Point mode for fallback click capture
            "ai_mask": 1,
        }
        if tool_type not in self.ROI_MODE_MAPPING:
            return False
            
        # [REQ-011] Auto-deselect if switching tools while editing
        if self.selected_annotation_id is not None:
             print(f"DEBUG: Auto-deselecting {self.selected_annotation_id} due to tool switch to {tool_type}")
             self.select_annotation(None, reset_tool=False)
             
        self.current_tool = tool_type
        
        # [REQ-010] UI Locking Trigger
        is_ai = tool_type.startswith("ai_")
        if self.on_ui_lock:
            self.on_ui_lock(is_ai)

        if self.cv_panel and self.cv_panel.IsOk():
            if is_ai:
                # [REQ-010] Enable creation (True) to trigger onCrop callback
                self.cv_panel.SetROIMode(1)
                self.cv_panel.SetFuncEnable(True, True, False)
                # Ensure no menu from C++ panel
                self.cv_panel.SetMenuROIEnable(False, False, False, False, False, False, False)
                
                if self.on_status_update:
                    self.on_status_update(_("AI Mode Active: Left-click (Green) to add, Right-click (Red) to exclude."))
                self.ai_prompts = []
                self.ai_preview_poly = None
                self.ai_preview_mask = None
                self.last_ai_click_pt = (-1, -1)
            else:
                mode = self.ROI_MODE_MAPPING.get(tool_type, 0)
                self.cv_panel.SetROIMode(mode)
                self.cv_panel.SetFuncEnable(True, True, True)
                self.cv_panel.SetMenuROIEnable(True, True, True, True, True, True, True)
        
        if self.cv_panel and self.cv_panel.IsOk():
            self.cv_panel.Refresh()
            
        self.sync_overlays()
        return True

    def set_ai_model(self, model_name: str):
        """Set AI model from selector"""
        if self.current_ai_model != model_name:
            print(f"🤖 Switching AI model in panel: {model_name}")
            self.current_ai_model = model_name
            # Reset existing prompts for new model to avoid confusion
            self.ai_prompts = []
            self.ai_preview_poly = []
            self.ai_service.is_ready = False # Trigger re-load/download on next click
            self.sync_overlays()

    def set_ui_lock_callback(self, callback: Callable):
        """Set callback for UI locking [REQ-010]"""
        self.on_ui_lock = callback
    
    def get_annotations(self) -> List[Annotation]:
        """Get all annotations"""
        return self.annotation_manager.get_all_annotations()
        
    def refresh_translations(self):
        """Update any cached translated strings"""
        # Current tool might have a translated status message
        if self.on_status_update:
            if self.current_tool.startswith("ai_"):
                self.on_status_update(_("AI Mode Active: Left-click (Green) to add, Right-click (Red) to exclude."))
            elif self.current_category:
                self.on_status_update(_("Drawing Label: {}").format(self.current_category))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get annotation statistics"""
        return self.annotation_manager.get_statistics()
    
    def get_annotation_manager(self) -> AnnotationManager:
        """Get annotation manager instance"""
        return self.annotation_manager
    
    def get_image_size(self) -> Optional[Tuple[int, int]]:
        """Get current image size"""
        return self.image_size
    
    def load_image(self, image_path: str) -> bool:
        """Load image into panel"""
        try:
            print(f"🔄 Loading Image: {image_path}")
            if not Path(image_path).exists():
                print(f"✗ File not found: {image_path}")
                return False
            
            if not self.cv_panel or not self.cv_panel.IsOk():
                self._init_cv_panel()
                
            if self.cv_panel and hasattr(self.cv_panel, 'LoadImage'):
                if self.cv_panel.LoadImage(image_path):
                    self.cv_panel.SetZoomToFit()
                    self.current_image_path = image_path
                    
                    # Get the decoded image for AI inference.
                    #
                    # Priority 1: cv_panel.GetMat() — the C++ panel has
                    # already decoded the file (using wxWidgets handlers that
                    # support HEIC, WebP, and other platform-native formats
                    # that OpenCV cannot handle).  This is the most reliable
                    # source and avoids re-reading the file entirely.
                    #
                    # Priority 2: np.fromfile + cv2.imdecode — [REQ-010]
                    # handles Unicode paths that cv2.imread rejects.
                    # imdecode may return None silently; always check.
                    #
                    # Priority 3: cv2.imread — plain fallback.
                    img = None
                    try:
                        img = self.cv_panel.GetMat()
                        # GetMat() always returns BGR (C++ normalises internally).
                        # Do NOT rely on its ndim for channel count — use IMREAD_UNCHANGED probe below.
                        if img is not None and img.ndim == 3 and img.shape[2] == 4:
                            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                        elif img is not None and img.ndim == 2:
                            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                    except Exception as e:
                        print(f"⚠️ GetMat() failed: {e}")

                    if img is None:
                        try:
                            img_array = np.fromfile(image_path, np.uint8)
                            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        except Exception as e:
                            print(f"⚠️ imdecode failed: {e}")

                    if img is None:
                        try:
                            img = cv2.imread(image_path)
                        except Exception as e:
                            print(f"⚠️ cv2.imread failed: {e}")

                    if img is None:
                        print(f"⚠️ Could not read image into memory: {image_path}")

                    # --- Channel count probe (IMREAD_UNCHANGED gives true depth) ---
                    # HEIC/JXL: cv2 cannot decode them → default to 3.
                    # All other formats: imdecode with UNCHANGED returns real ndim.
                    ext = Path(image_path).suffix.lower()
                    if ext in ('.heic', '.jxl'):
                        self.current_image_channels = 3
                    else:
                        try:
                            probe = cv2.imdecode(
                                np.fromfile(image_path, np.uint8), cv2.IMREAD_UNCHANGED
                            )
                            if probe is not None:
                                self.current_image_channels = 1 if probe.ndim == 2 else probe.shape[2]
                                del probe
                            else:
                                self.current_image_channels = 3
                        except Exception:
                            self.current_image_channels = 3

                    self.current_image_mat = img
                    
                    self.annotation_manager.clear_all()
                    self.ai_service.image_embedding = None # Reset embedding for new image
                    self.select_annotation(None) # Reset selection and ROI state
                    return True
            return False
        except Exception as e:
            print(f"Failed to load image: {e}")
            return False

    def select_annotation(self, annotation_id: Optional[str], reset_tool: bool = True):
        """Select annotation and load into editor"""
        self.annotation_manager.select_annotation(annotation_id)
        self.selected_annotation_id = annotation_id
        
        if annotation_id:
            ann = self.annotation_manager.get_annotation(annotation_id)
            if ann:
                # Disable C++ panel's ROI mode switching right-click menu during edit
                if self.cv_panel:
                    self.cv_panel.SetMenuROIEnable(False, False, False, False, False, False, False)
                
                self._load_annotation_to_cv_panel(ann)
                if self.on_status_update:
                    self.on_status_update(_("Editing {}. Shape locked. Press Enter to update.").format(ann.label))
        else:
                self.cv_panel.SetRect((0, 0, 0, 0))
                if hasattr(self.cv_panel, 'SetPolygonPoints'):
                    self.cv_panel.SetPolygonPoints([])
                
                # Re-enable C++ panel's ROI menus
                if self.cv_panel:
                    self.cv_panel.SetMenuROIEnable(True, True, True, True, True, True, True)

                # Reset to current toolbar tool mode
                # Bypass the "selected_annotation_id" check by ensuring it's None now
                if reset_tool:
                    self.set_tool(self.current_tool)
        
        if self.on_selection_changed:
            self.on_selection_changed(annotation_id)
        self.sync_overlays()
    def _on_ai_click_polled(self, pt):
        """Handle AI click detected via polling"""
        # pt is in image coordinates
        img_x, img_y = float(pt[0]), float(pt[1])
        self._add_ai_prompt(img_x, img_y, 1) # Polled from LeftMouseDownPoint

    def _on_ai_mouse_down_cv(self, pt):
        """Handle AI prompt clicks from C++ callback"""
        if not self.current_tool.startswith("ai_"):
            return
        
        # pt is already in image coordinates from C++ 
        img_x, img_y = float(pt[0]), float(pt[1])
        self._add_ai_prompt(img_x, img_y, 1) # Positive

    def _on_ai_mouse_down(self, event):
        """Handle AI prompt clicks from wx events (parent container)"""
        if not self.current_tool.startswith("ai_"):
            event.Skip()
            return

        # Get local coordinates
        pos = event.GetPosition()
        is_right = (event.IsRightDown() or event.GetButton() == wx.MOUSE_BTN_RIGHT)
        
        img_x, img_y = pos.x, pos.y
        if self.cv_panel and hasattr(self.cv_panel, 'ViewToImage'):
             img_pos = self.cv_panel.ViewToImage(pos.x, pos.y)
             img_x, img_y = img_pos[0], img_pos[1]
        
        self._add_ai_prompt(img_x, img_y, 0 if is_right else 1)

    def _add_ai_prompt(self, img_x, img_y, label: int):
        """Internal helper to add and run AI prompt"""
        if not self.current_tool.startswith("ai_"):
             return

        # [REQ-010] First point MUST be positive (Left click / Label 1)
        if len(self.ai_prompts) == 0 and label == 0:
            print("⚠️ AI: First prompt must be positive. Ignoring negative prompt.")
            if self.on_status_update:
                self.on_status_update(_("AI: First point must be a positive prompt (Left-click)."))
            return

        prompt = {
            "type": "point",
            "pos": (float(img_x), float(img_y)),
            "label": label
        }
        self.ai_prompts.append(prompt)
        
        print(f"🤖 AI Prompt added: {prompt} (Total: {len(self.ai_prompts)})")
        
        # Trigger prediction
        self._run_ai_prediction()
        self.sync_overlays()

    def _on_ai_mouse_move_cv(self, pt):
        """Handle mouse move from C++ callback — position display and AI hover inference."""
        # pt is in image coordinates from C++
        img_x, img_y = float(pt[0]), float(pt[1])

        # Always update position display regardless of current tool
        self._update_mouse_pos_display(img_x, img_y)

        # AI hover inference (only in AI mode)
        if not self.current_tool.startswith("ai_"):
            return

        # Throttling
        import time
        current_time = time.time() * 1000 # ms
        throttle_ms = 100
        if self.settings_manager:
            throttle_ms = self.settings_manager.get("ai_inference_throttle_ms", 100)

        if current_time - self.last_ai_inference_time < throttle_ms:
            return

        # Continuous inference check
        is_continuous = False
        if self.settings_manager:
            is_continuous = self.settings_manager.get("ai_continuous_inference", False)

        if not is_continuous or len(self.ai_prompts) == 0:
            return

        print(f"🖱️ AI Motion (CV): ({img_x}, {img_y})")
        self.last_ai_inference_time = current_time

        temp_prompts = self.ai_prompts + [{
            "type": "point",
            "pos": (img_x, img_y),
            "label": 1
        }]

        if self.ai_service.is_embedding_ready():
            tolerance = 0.004
            denoise = True
            if self.settings_manager:
                tolerance = self.settings_manager.get("ai_polygon_tolerance", 0.004)
                if not self.settings_manager.get("ai_auto_simplify_polygon", True):
                    tolerance = 0.0001
                denoise = self.settings_manager.get("ai_denoise_mask", True)

            if self.current_tool == "ai_mask":
                self.ai_preview_mask = self.ai_service.predict_mask(
                    temp_prompts, denoise=denoise
                )
                self.ai_preview_poly = []
            else:
                self.ai_preview_poly = self.ai_service.predict_polygon(
                    None, temp_prompts,
                    tolerance=tolerance, denoise=denoise
                )
                self.ai_preview_mask = None
            self.sync_overlays()

    def _update_mouse_pos_display(self, img_x: float, img_y: float):
        """Fire on_pos_update callback with current image coordinates.

        Zoom is not included here — see REQ-013 (GetZoomFactor C++ API).
        """
        if self.on_pos_update:
            self.on_pos_update(img_x, img_y)

    def _on_ai_double_click_left_cv(self, pt):
        """[REQ-010] Double-left-click to complete AI annotation from C++ callback"""
        if not self.current_tool.startswith("ai_"):
            return
            
        print(f"🖱️ AI Double-Left-Click (CV) at {pt}")
        # Backtrack: Remove the positive prompt added by the first click of this dclick sequence
        if self.ai_prompts:
            self.ai_prompts.pop()
            print("🤖 Backtracked extra positive prompt from double-click.")
            
        wx.CallAfter(self.add_active_roi)

    def _cancel_pending_right_neg(self):
        """Cancel any deferred negative prompt from a previous right-click."""
        if self._ai_right_neg_timer is not None:
            try:
                self._ai_right_neg_timer.Stop()
            except Exception:
                pass
            self._ai_right_neg_timer = None
        self._ai_pending_neg_pos = None

    def _commit_pending_right_neg(self):
        """Called by wx.CallLater — commit the deferred negative prompt."""
        self._ai_right_neg_timer = None
        if self._ai_pending_neg_pos is not None:
            px, py = self._ai_pending_neg_pos
            self._ai_pending_neg_pos = None
            self._add_ai_prompt(px, py, 0)

    def _on_ai_double_click_right_cv(self, pt):
        """[REQ-010] Double-right-click to undo last AI prompt from C++ callback"""
        if not self.current_tool.startswith("ai_"):
            return

        print(f"🖱️ AI Double-Right-Click (CV) at {pt}")
        # Cancel any pending negative from click 1, and suppress the right-click that
        # C++ fires immediately after this dclick event (for the same 2nd mouse press).
        self._cancel_pending_right_neg()
        self._ai_right_dclick_done = True  # Suppress next right-click callback

        # Remove the actual undo target (the last real prompt).
        if self.ai_prompts:
            self.ai_prompts.pop()
            print(f"🤖 AI Undo via DClick-Right. Remaining: {len(self.ai_prompts)}")
            self._run_ai_prediction()
            self.sync_overlays()

    def _on_ai_mouse_move(self, event):
        """Handle AI continuous inference with Throttling (Legacy wx event)"""
        if not self.current_tool.startswith("ai_"):
            event.Skip()
            return
            
        # If we have C++ motion callback, we might not need this, 
        # but keep it as fallback or let it skip.
        event.Skip()

    def _on_ai_double_click_left(self, event):
        """Double-left-click Legacy Handler"""
        if not self.current_tool.startswith("ai_"):
            event.Skip()
            return
        self.add_active_roi()

    def _on_ai_double_click_right(self, event):
        """Double-right-click Legacy Handler"""
        if not self.current_tool.startswith("ai_"):
            event.Skip()
            return
        self.remove_last_ai_prompt()

    def _run_ai_prediction(self):
        """Run AI inference on current prompts"""
        if not self.current_image_path or self.current_image_mat is None:
            print("⚠️ Skipping AI Prediction: Image not loaded in memory.")
            return
            
        print(f"🤖 AI Prediction Triggered: {self.current_ai_model}, prompts={len(self.ai_prompts)}")

        # Lazy Loading & Download Notification
        if not self.ai_service.is_ready or self.ai_service.current_model_name != self.current_ai_model:
            print(f"🔄 Need to initialize AI model: {self.current_ai_model}")
            msg = _("🤖 Preparing AI Model: {}... (Downloading if needed)").format(self.current_ai_model)
            if self.on_status_update:
                self.on_status_update(msg)
            
            # This is a blocking call
            success = self.ai_service.initialize(self.current_ai_model)
            if not success:
               print("❌ AI Service failed to initialize.")
               if self.on_status_update:
                   self.on_status_update(_("❌ AI Model initialization failed."))
               return

        # Ensure image is set in AI service (Calculates Embedding)
        if not self.ai_service.is_embedding_ready():
            print("🧠 Pre-calculating Image Embedding (Encoder)...")
            if self.on_status_update:
                self.on_status_update(_("🧠 AI Embedding... (Wait)"))
            
            self.ai_service.set_image(self.current_image_mat)
            print("✅ Embedding Calculation Done.")

        # Real inference
        # Fetch settings for optimization
        tolerance = self.settings_manager.get("ai_polygon_tolerance", 0.004)
        if not self.settings_manager.get("ai_auto_simplify_polygon", True):
            tolerance = 0.0001  # Very low tolerance for raw mask
        denoise = self.settings_manager.get("ai_denoise_mask", True)

        if self.current_tool == "ai_mask":
            print("🔮 Generating AI Mask prediction...")
            self.ai_preview_mask = self.ai_service.predict_mask(
                self.ai_prompts, denoise=denoise
            )
            self.ai_preview_poly = []
            px_count = int(np.count_nonzero(self.ai_preview_mask)) if self.ai_preview_mask is not None else 0
            print(f"✨ Mask Prediction: {px_count} positive pixels.")
        else:
            print("🔮 Generating AI Prediction Polygon...")
            self.ai_preview_poly = self.ai_service.predict_polygon(
                None, self.ai_prompts,
                tolerance=tolerance,
                denoise=denoise
            )
            self.ai_preview_mask = None
            print(f"✨ Prediction Result: {len(self.ai_preview_poly)} points.")
        
        # UI Feedback
        if self.on_status_update:
            msg = _("AI Active: {} positive, {} negative prompts.").format(
                len([p for p in self.ai_prompts if p['label'] == 1]),
                len([p for p in self.ai_prompts if p['label'] == 0])
            )
            self.on_status_update(msg)

    def add_active_roi(self):
        """Confirm AI prediction or normal ROI"""
        if self.current_tool.startswith("ai_"):
            if self.current_tool == "ai_mask":
                # --- Commit AI Mask ---
                if self.ai_preview_mask is None:
                    print("⚠️ No AI preview mask to add.")
                    return

                try:
                    print("✅ Committing AI Mask annotation.")
                    category = self.current_category
                    h, w = self.ai_preview_mask.shape[:2]
                    ann = create_mask_annotation(
                        self.ai_preview_mask.copy(), (h, w), category, self.current_color
                    )
                    ann.source = "AI-" + self.current_ai_model
                    self.annotation_manager.add_annotation(ann)

                    self.ai_prompts = []
                    self.ai_preview_mask = None

                    if self.on_status_update:
                        self.on_status_update(_("AI Mask annotation added."))

                    if self.on_annotation_changed:
                        self.on_annotation_changed("added", ann.id)

                    if self.cv_panel:
                        self.cv_panel.SetRect((0, 0, 0, 0))
                        self.cv_panel.Refresh()

                    if self.on_ui_lock:
                        self.on_ui_lock(False)

                    self.sync_overlays()
                except Exception as e:
                    print(f"❌ Failed to commit AI mask: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # --- Commit AI Polygon ---
                if not self.ai_preview_poly:
                    print("⚠️ No AI preview polygon to add.")
                    return

                try:
                    print(f"✅ Committing AI Polygon with {len(self.ai_preview_poly)} points.")
                    category = self.current_category
                    ann = create_polygon_annotation(self.ai_preview_poly, category, self.current_color)
                    ann.source = "AI-" + self.current_ai_model
                    self.annotation_manager.add_annotation(ann)

                    self.ai_prompts = []
                    self.ai_preview_poly = []

                    if self.on_status_update:
                        self.on_status_update(_("AI Annotation added."))

                    if self.on_annotation_changed:
                        self.on_annotation_changed("added", ann.id)

                    if self.cv_panel:
                        self.cv_panel.SetRect((0, 0, 0, 0))
                        self.cv_panel.Refresh()

                    if self.on_ui_lock:
                        self.on_ui_lock(False)

                    self.sync_overlays()
                except Exception as e:
                    print(f"❌ Failed to commit AI polygon: {e}")
                    import traceback
                    traceback.print_exc()
            return
            
        self._on_add_object_from_menu(None)

    def _on_python_right_click(self, pt, item_idx: int = -1):
        """
        [REQ-009] Context-Sensitive Right-click Menu Implementation
        pt: (x, y) image coordinates
        item_idx: Index of clicked ROI (Optional)
        """
        img_x, img_y = float(pt[0]), float(pt[1])
        print(f"🖱️ Right-click detected at ({img_x}, {img_y}), item_idx={item_idx}")
        
        # 1. AI Mode Logic: Intercept and handle prompting
        if self.current_tool.startswith("ai_"):
            # Suppress the right-click that fires immediately after a dclick event.
            # (C++ fires dclick first, then right-click for the same 2nd mouse press.)
            if self._ai_right_dclick_done:
                self._ai_right_dclick_done = False
                return True
            # Defer negative prompt via CallLater so a right double-click can cancel it.
            self._cancel_pending_right_neg()
            self._ai_pending_neg_pos = (img_x, img_y)
            self._ai_right_neg_timer = wx.CallLater(250, self._commit_pending_right_neg)
            return True # Intercept C++ menu in AI mode

        menu = wx.Menu()
        
        # 2. Check if we are currently DRAWING or EDITING an existing ROI
        roi_mode = self.cv_panel.GetROIMode() if self.cv_panel else 0
        rect = self.cv_panel.GetRect() if self.cv_panel else (0,0,0,0)
        
        # For Polygon, also check if it has points being collected
        pts = []
        if roi_mode == 7 and hasattr(self.cv_panel, 'GetPolygonPoints'):
            pts = self.cv_panel.GetPolygonPoints()

        # [REQ-011] Enhanced active ROI detection (includes Polygon points-in-progress)
        is_active_roi = (roi_mode != 0 and (rect[2] > 0 or rect[3] > 0 or roi_mode == 1 or (roi_mode == 7 and len(pts) > 0)))

        if is_active_roi:
            # --- Mode B/C: Active Operation (Drawing or Editing) ---
            label = _("Complete Annotation") if not self.selected_annotation_id else _("Update Object")
            item_done = menu.Append(wx.ID_ANY, label + " (Enter)")
            self.Bind(wx.EVT_MENU, self._on_add_object_from_menu, item_done)
            
            item_cancel = menu.Append(wx.ID_ANY, _("Cancel Drawing") + " (Esc)")
            self.Bind(wx.EVT_MENU, self._on_cancel_drawing, item_cancel)
            menu.AppendSeparator()

        # 3. Check for existing annotations at click position (Multi-hit support)
        hits = self.annotation_manager.get_annotations_at(img_x, img_y)
        
        if hits:
            # --- Mode C: Object Context ---
            hit_ann = hits[0] # Priority to top-most
            
            # Sub-menu for overlapping objects if multiple hits
            if len(hits) > 1:
                sub_select = wx.Menu()
                for ann in hits:
                    item_label = f"{ann.category} ({ann.id[:8]})"
                    sub_item = sub_select.Append(wx.ID_ANY, item_label)
                    # Closure to capture 'ann_id' correctly
                    def make_select_handler(aid):
                        return lambda e: self.select_annotation(aid)
                    self.Bind(wx.EVT_MENU, make_select_handler(ann.id), sub_item)
                menu.AppendSubMenu(sub_select, _("Select Overlapping Object"))
            
            # Object Actions
            edit_label = f"{_('Edit Label')}: {hit_ann.category}"
            item_edit = menu.Append(wx.ID_ANY, edit_label)
            self.Bind(wx.EVT_MENU, lambda e: self.select_annotation(hit_ann.id), item_edit)
            
            menu.AppendSeparator()
            item_front = menu.Append(wx.ID_ANY, _("Bring to Front"))
            self.Bind(wx.EVT_MENU, lambda e: self._on_bring_to_front(hit_ann.id), item_front)
            
            item_back = menu.Append(wx.ID_ANY, _("Send to Back"))
            self.Bind(wx.EVT_MENU, lambda e: self._on_send_to_back(hit_ann.id), item_back)
            
            menu.AppendSeparator()
            item_del = menu.Append(wx.ID_ANY, _("Delete Object") + " (Del)")
            self.Bind(wx.EVT_MENU, lambda e: self._on_delete_specific(hit_ann.id), item_del)
            
            menu.AppendSeparator()

        if not is_active_roi and not hits:
            # --- Mode A: Idle / Global Functionality ---
            # Quick Create
            item_rect = menu.Append(wx.ID_ANY, _("Create Rectangle"))
            self.Bind(wx.EVT_MENU, lambda e: self.set_tool("rectangle"), item_rect)
            
            item_rot = menu.Append(wx.ID_ANY, _("Create Rotated Rect"))
            self.Bind(wx.EVT_MENU, lambda e: self.set_tool("rotated_rect"), item_rot)
            
            item_circ = menu.Append(wx.ID_ANY, _("Create Circle"))
            self.Bind(wx.EVT_MENU, lambda e: self.set_tool("circle"), item_circ)

            item_annu = menu.Append(wx.ID_ANY, _("Create Annulus"))
            self.Bind(wx.EVT_MENU, lambda e: self.set_tool("annulus"), item_annu)
            
            item_poly = menu.Append(wx.ID_ANY, _("Create Polygon"))
            self.Bind(wx.EVT_MENU, lambda e: self.set_tool("polygon"), item_poly)
            
            menu.AppendSeparator()
            
            # Zoom and View
            item_fit = menu.Append(wx.ID_ANY, _("Zoom to Fit"))
            self.Bind(wx.EVT_MENU, lambda e: self.zoom_fit(), item_fit)

            menu.Append(wx.ID_ANY, _("Full Screen") + " (F)")
            
            menu.AppendSeparator()

        # Show Menu
        self.PopupMenu(menu)
        menu.Destroy()
        
        return True # Intercept C++ menu!

    def _on_bring_to_front(self, ann_id: str):
        """[REQ-009] Bring annotation to top layer"""
        if self.annotation_manager.bring_to_front(ann_id):
            self.sync_overlays()
            self._update_status(_("Moved object to top layer"))

    def _on_send_to_back(self, ann_id: str):
        """[REQ-009] Send annotation to bottom layer"""
        if self.annotation_manager.send_to_back(ann_id):
            self.sync_overlays()
            self._update_status(_("Moved object to bottom layer"))

    def _on_delete_specific(self, ann_id: str):
        """Delete a specific annotation from context menu"""
        if self.annotation_manager.remove_annotation(ann_id):
            if self.selected_annotation_id == ann_id:
                self.select_annotation(None)
            else:
                self.sync_overlays()
            
            if self.on_annotation_changed:
                self.on_annotation_changed("deleted", None)

    def _on_context_menu_legacy(self, event):
        """Legacy event handler (no-op if C++ callback is used)"""
        pass

    def delete_selected_annotation(self) -> bool:
        """Delete the currently selected annotation"""
        if self.selected_annotation_id:
            aid = self.selected_annotation_id
            if self.annotation_manager.remove_annotation(aid):
                self.select_annotation(None)
                if self.on_annotation_changed:
                    self.on_annotation_changed("deleted", None)
                return True
        return False
    
    def undo(self) -> bool:
        """Undo last operation"""
        if self.annotation_manager.undo():
            self.sync_overlays()
            if self.on_annotation_changed:
                self.on_annotation_changed("undone", None)
            return True
        return False
    
    def redo(self) -> bool:
        """Redo last undone operation"""
        if self.annotation_manager.redo():
            self.sync_overlays()
            if self.on_annotation_changed:
                self.on_annotation_changed("redone", None)
            return True
        return False
    
    def save_annotations(self, file_path: str, embed_data: bool = False, **kwargs) -> bool:
        """Save annotations to file"""
        w, h = self.image_size if self.image_size else (0, 0)
        return self.annotation_manager.save_to_file(
            file_path, 
            image_path=self.current_image_path,
            width=w,
            height=h,
            embed_data=embed_data,
            **kwargs
        )
    
    def load_annotations(self, file_path: str) -> bool:
        """Load annotations from file"""
        success = self.annotation_manager.load_from_file(file_path)
        if success:
            self.sync_overlays()
            if self.on_annotation_changed:
                self.on_annotation_changed("loaded", None)
        return success

    def _on_add_object_from_menu(self, event):
        """Submit annotation from menu/toolbar"""
        rect = self.cv_panel.GetRect()
        mode = self.cv_panel.GetROIMode()
        
        # [REQ-008] Geometry Validation
        # Point (1), Circle (5), and Annulus (6) are not defined by rect area —
        # their geometry comes from GetOuterRadius() / GetInnerRadius(), so rect[3]
        # can legitimately be 0.  Only validate rect dimensions for rect-based shapes.
        if rect[2] <= 0 or rect[3] <= 0:
            if mode not in (1, 5, 6):
                self._update_status(_("Error: Invalid ROI size"))
                return
        
        if self.selected_annotation_id:
            roi_data = self._extract_current_roi_state_ext(mode, rect)
            if roi_data:
                self._update_existing_annotation(self.selected_annotation_id, roi_data)
                self._update_status(_("Updated: {}").format(self.selected_annotation_id))
        else:
            # Use currently selected category from Label List
            category = self.current_category
            if category:
                roi_data = self._extract_current_roi_state_ext(mode, rect)
                if roi_data:
                    roi_data['category'] = category
                    self._create_annotation_from_roi_data(roi_data)
                    self._update_status(_("Added: {}").format(category))

        if self.selected_annotation_id:
            self.selected_annotation_id = None
            self.annotation_manager.select_annotation(None)
             
        # Notify UI selection cleared
        if self.on_selection_changed:
            self.on_selection_changed(None)

        if self.on_annotation_changed:
            self.on_annotation_changed("updated", None)
            
        # Clear the active ROI drawing after adding/updating
        if self.cv_panel:
            self.cv_panel.SetRect((0, 0, 0, 0))
            if hasattr(self.cv_panel, 'SetPolygonPoints'):
                self.cv_panel.SetPolygonPoints([])
            # Reset ROI mode to current tool to ensure internal C++ state is cleaned up
            self.set_tool(self.current_tool)
            self.cv_panel.Refresh()

        # Synchronize overlays after clearing selection to ensure the updated object is rendered
        self.sync_overlays()

    def _on_cancel_drawing(self, event):
        """Cancel current draw/edit and return to normal tool state"""
        # [REQ-012] Clear AI state
        if self.current_tool.startswith("ai_"):
            self.ai_prompts = []
            self.ai_preview_poly = []
            self.ai_preview_mask = None
            
        self.select_annotation(None)
        self.sync_overlays()
        self._update_status(_("Drawing/Edit cancelled"))

    def remove_last_ai_prompt(self):
        """Remove last added AI prompt (Backspace functionality)"""
        if self.current_tool.startswith("ai_") and self.ai_prompts:
            self.ai_prompts.pop()
            print(f"🤖 AI Prompt removed. Remaining: {len(self.ai_prompts)}")
            self._run_ai_prediction()
            self.sync_overlays()

    def _update_existing_annotation(self, ann_id, data):
        """Update existing annotation object"""
        ann = self.annotation_manager.get_annotation(ann_id)
        if not ann: return
        
        if data["type"] == "polygon":
            ann.points = data["points"]
        elif data["type"] == "rectangle":
            r = data["rect"]
            ann.attributes.update({"x": r[0], "y": r[1], "width": r[2], "height": r[3]})
            ann.points = create_rectangle_annotation(r[0], r[1], r[2], r[3]).points
        elif data["type"] == "rotated_rect":
            r = data["rect"]
            angle = data.get("angle", 0.0)
            ann.attributes.update({"x": r[0], "y": r[1], "width": r[2], "height": r[3], "angle": angle})
            ann.points = create_rotated_rectangle_annotation(r[0], r[1], r[2], r[3], angle).points
        elif data["type"] == "circle":
            ann.attributes["center_x"] = data.get("center_x", ann.attributes.get("center_x"))
            ann.attributes["center_y"] = data.get("center_y", ann.attributes.get("center_y"))
            ann.attributes["radius"] = data.get("outer_radius", ann.attributes.get("radius"))
            # Re-generate points for circle
            ann.points = create_circle_annotation(ann.attributes["center_x"], ann.attributes["center_y"], ann.attributes["radius"]).points
        elif data["type"] == "annulus":
            ann.attributes["center_x"] = data.get("center_x", ann.attributes.get("center_x"))
            ann.attributes["center_y"] = data.get("center_y", ann.attributes.get("center_y"))
            ann.attributes["inner_radius"] = data.get("inner_radius", ann.attributes.get("inner_radius"))
            ann.attributes["outer_radius"] = data.get("outer_radius", ann.attributes.get("outer_radius"))
            ann.attributes["start_angle"] = data.get("start_angle", ann.attributes.get("start_angle"))
            ann.attributes["end_angle"] = data.get("end_angle", ann.attributes.get("end_angle"))
            # Re-generate points for annulus
            ann.points = create_annulus_annotation(
                ann.attributes["center_x"], ann.attributes["center_y"],
                ann.attributes["inner_radius"], ann.attributes["outer_radius"],
                ann.attributes["start_angle"], ann.attributes["end_angle"]
            ).points
        elif data["type"] == "point":
            ann.points = [(data["rect"][0], data["rect"][1])]
        elif data["type"] == "line":
            p1 = data.get("p1", (data["rect"][0], data["rect"][1]))
            p2 = data.get("p2", (data["rect"][0] + data["rect"][2], data["rect"][1] + data["rect"][3]))
            ann.points = [p1, p2]
        
        ann.modified_time = datetime.now()

    def _load_annotation_to_cv_panel(self, ann: Annotation):
        """Load annotation back to editor layer"""
        mode = self.ROI_MODE_MAPPING.get(ann.type, 0)
        
        # New unified API: SetEditingROI(mode, points, angle)
        if hasattr(self.cv_panel, 'SetEditingROI'):
            # Prepare points list of tuples
            points = ann.points
            angle = float(ann.attributes.get("angle", 0.0))
            
            # The SetEditingROI for circle/annulus expects specific format.
            if ann.type in ["rectangle", "rotated_rect"]:
                x = ann.attributes.get("x", ann.points[0][0])
                y = ann.attributes.get("y", ann.points[0][1])
                w = ann.attributes.get("width", 0)
                h = ann.attributes.get("height", 0)
                points = [(x, y), (w, h)]
                
            elif ann.type == "circle":
                center_x = ann.attributes.get("center_x", 0)
                center_y = ann.attributes.get("center_y", 0)
                radius = ann.attributes.get("radius", 10)
                
                # Format: [(center_x, center_y), (radius, 0.1)]
                # Use 0.1 to pass C++ validity check (height > 0)
                points = [(center_x, center_y), (radius, 0.1)] 
                
            elif ann.type == "annulus":
                center_x = ann.attributes.get("center_x", 0)
                center_y = ann.attributes.get("center_y", 0)
                inner_r = ann.attributes.get("inner_radius", 0)
                outer_r = ann.attributes.get("outer_radius", 10)
                start_a = ann.attributes.get("start_angle", 0)
                end_a = ann.attributes.get("end_angle", 360)
                
                # Format: [(center_x, center_y), (outer_r, 0.1), (inner_r, 0), (start_angle, end_angle)]
                points = [(center_x, center_y), (outer_r, 0.1), (inner_r, 0), (start_a, end_a)] 
            
            # Call unified API
            self.cv_panel.SetEditingROI(mode, points, angle)
            print(f"✅ Loaded {ann.type} via SetEditingROI (Points: {len(points)})")
            
        else:
            # Fallback for older module versions
            self.cv_panel.SetROIMode(mode)
            if ann.type == "polygon":
                if hasattr(self.cv_panel, 'SetPolygonPoints'):
                    self.cv_panel.SetPolygonPoints(ann.points)
                else:
                    print("⚠️ Polygon editing requires module update (SetEditingROI missing).")
            elif ann.type in ["rectangle", "rotated_rect"]:
                x = ann.attributes.get("x", ann.points[0][0])
                y = ann.attributes.get("y", ann.points[0][1])
                w = ann.attributes.get("width", 0)
                h = ann.attributes.get("height", 0)
                self.cv_panel.SetRect((int(x), int(y), int(w), int(h)))
                if "angle" in ann.attributes:
                    self.cv_panel.SetRotateAngle(float(ann.attributes["angle"]))
            elif ann.type == "circle":
                 # SetROI for circle using rect if SetEditingROI missing? No, SetEditingROI is preferred.
                 # Fallback logic here is getting complex. Assuming SetEditingROI handles it.
                 pass
            elif ann.type == "annulus":
                 # Fallback for annulus is also complex. Assuming SetEditingROI handles it.
                 pass
                    
        self.cv_panel.Refresh()

    def _update_status(self, msg):
        if self.on_status_update: self.on_status_update(msg)


    def cancel_active_roi(self):
        # Unlock UI
        if self.on_ui_lock:
            self.on_ui_lock(False)
        self._on_cancel_drawing(None)
        # _on_cancel_drawing → select_annotation(None) → set_tool(current_tool)
        # re-locks the UI if current_tool is "ai_*".  Switch to "select" to break the loop.
        if self.current_tool.startswith("ai_"):
            self.set_tool("select")

    # Callback Setters
    def set_annotation_changed_callback(self, callback: Callable):
        """Set callback for annotation changes (add/delete/edit)"""
        self.on_annotation_changed = callback
    
    def set_selection_changed_callback(self, callback: Callable):
        """Set callback for annotation selection changes"""
        self.on_selection_changed = callback
    
    def set_status_update_callback(self, callback: Callable):
        """Set callback for status bar message updates"""
        self.on_status_update = callback

    def set_pos_update_callback(self, callback: Callable):
        """Set callback for mouse position / zoom updates: callback(x, y, zoom_or_None)"""
        self.on_pos_update = callback

    def apply_theme(self, theme_colors):
        """Apply theme to panel and C++ canvas"""
        bg_panel = wx.Colour(theme_colors.bg_panel)
        canvas_bg = wx.Colour(theme_colors.canvas_bg)
        
        self.SetBackgroundColour(bg_panel)
        self.cv_container.SetBackgroundColour(canvas_bg)
        self.workspace_bg_color = canvas_bg
        
        # Update C++ panel background if initialized
        if self.cv_panel and self.cv_panel.IsOk():
            if hasattr(self.cv_panel, 'SetCanvasBgColor'):
                bg = canvas_bg.Get()
                self.cv_panel.SetCanvasBgColor(bg[0], bg[1], bg[2])
        
        self.Refresh()

    def _on_key_down(self, event):
        """Handle keyboard events for image panel"""
        key_code = event.GetKeyCode()
        
        if key_code == wx.WXK_BACK:
            # Backspace removes last AI prompt
            self.remove_last_ai_prompt()
        elif key_code == wx.WXK_ESCAPE:
            # Escape cancels drawing/prompts
            self.cancel_active_roi()
        else:
            event.Skip()

    def cleanup(self):
        """Perform cleanup before destruction"""
        print("🧹 Cleaning up ImageDisplayPanel...")
        if hasattr(self, 'roi_polling_timer') and self.roi_polling_timer:
            self.roi_polling_timer.Stop()
            self.roi_polling_timer = None
        
        if self.cv_panel:
            # We don't necessarily need to call Destroy on cv_panel if it's a child of cv_container
            # but clearing the reference helps.
            self.cv_panel = None
