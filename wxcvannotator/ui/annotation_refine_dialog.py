#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Annotation Shape Refinement Dialogs

Provides morphological operations (Erosion / Dilation / Opening / Closing) and
Mask → Polygon conversion for polygon and mask annotation types.

The module-level utility functions are standalone and can be imported
independently by other parts of the application.
"""

import base64
import platform
import zlib
from typing import List, Optional, Tuple

import cv2
import numpy as np
import wx
import wx.lib.buttons as wxbuttons

from .i18n import _


# ---------------------------------------------------------------------------
# Module-level utility functions
# ---------------------------------------------------------------------------

def polygon_to_mask(
    points: List[Tuple[float, float]],
    img_h: int,
    img_w: int,
) -> np.ndarray:
    """Rasterize polygon points to a binary uint8 mask (values 0 or 255).

    Args:
        points: List of ``(x, y)`` float coordinate pairs.
        img_h: Image height in pixels.
        img_w: Image width in pixels.

    Returns:
        ``uint8`` numpy array of shape ``(img_h, img_w)``.
    """
    mask = np.zeros((img_h, img_w), dtype=np.uint8)
    if len(points) < 3:
        return mask
    pts = np.array(
        [[int(round(x)), int(round(y))] for x, y in points], dtype=np.int32
    )
    cv2.fillPoly(mask, [pts], 255)
    return mask


def apply_morph_to_mask(
    mask: np.ndarray,
    operation: str,
    kernel_size: int,
    iterations: int = 1,
) -> np.ndarray:
    """Apply a morphological operation to a binary uint8 mask.

    Args:
        mask: ``uint8`` array (values 0 or 255).
        operation: One of ``"erosion"``, ``"dilation"``, ``"opening"``,
                   ``"closing"``.
        kernel_size: Side length of the elliptical structuring element
                     (pixels, clamped to ≥ 1).
        iterations: Number of times the operation is applied.

    Returns:
        New ``uint8`` array of the same shape.
    """
    k = max(1, kernel_size)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    op_map = {
        "erosion":  cv2.MORPH_ERODE,
        "dilation": cv2.MORPH_DILATE,
        "opening":  cv2.MORPH_OPEN,
        "closing":  cv2.MORPH_CLOSE,
    }
    morph_op = op_map.get(operation, cv2.MORPH_ERODE)
    return cv2.morphologyEx(mask, morph_op, kernel, iterations=iterations)


def _find_ray_intersection_rightward(
    contour_pts: List[Tuple[float, float]],
    from_x: float,
    from_y: float,
) -> Tuple[Optional[float], int]:
    """Cast a horizontal ray from ``(from_x, from_y)`` in the +x direction.

    Returns the x-coordinate of the nearest edge crossing with ``x > from_x``
    and the index of that edge's start vertex.

    Returns:
        ``(x_cross, edge_start_idx)`` or ``(None, -1)`` if nothing found.
    """
    best_x: Optional[float] = None
    best_idx = -1
    n = len(contour_pts)
    for i in range(n):
        p1 = contour_pts[i]
        p2 = contour_pts[(i + 1) % n]
        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])
        if y1 == y2:
            continue  # Horizontal edge — skip
        t = (from_y - y1) / (y2 - y1)
        if not (0.0 <= t <= 1.0):
            continue
        x_cross = x1 + t * (x2 - x1)
        if x_cross > from_x and (best_x is None or x_cross < best_x):
            best_x = x_cross
            best_idx = i
    return best_x, best_idx


def _merge_hole_into_outer(
    outer_pts: List[Tuple[float, float]],
    hole_pts: List[Tuple[float, float]],
) -> List[Tuple[float, float]]:
    """Merge a hole contour into an outer contour using a horizontal bridge.

    The rightmost point of the hole is connected to the outer boundary via a
    horizontal ray (0° / +x direction).  The bridge creates two coincident
    edges so that the hole interior receives an even crossing count and is
    left unfilled by even-odd fill renderers (LabelMe, most polygon tools).

    If no rightward intersection is found the hole is appended without a
    bridge (visible artefact but no crash).

    Args:
        outer_pts: Outer contour as list of ``(x, y)`` pairs.
        hole_pts:  Hole contour as list of ``(x, y)`` pairs.

    Returns:
        Merged polygon as list of ``(x, y)`` pairs.
    """
    if not hole_pts:
        return outer_pts

    # --- Bridge entry on the hole side: rightmost point ---
    h_idx = max(range(len(hole_pts)), key=lambda i: hole_pts[i][0])
    hx, hy = float(hole_pts[h_idx][0]), float(hole_pts[h_idx][1])

    # --- Bridge entry on the outer side: rightward ray intersection ---
    ox, edge_idx = _find_ray_intersection_rightward(outer_pts, hx, hy)

    if ox is None:
        # Fallback: no intersection found, append hole without bridge
        return list(outer_pts) + list(hole_pts)

    o_pt = (ox, hy)
    h_pt = (hx, hy)

    # Rotate hole so traversal starts at the rightmost point, then closes
    hole_rotated = hole_pts[h_idx:] + hole_pts[:h_idx] + [hole_pts[h_idx]]

    # Merged path:
    #   outer[0..edge_idx]  →  O  →  H  →  hole_rotated  →  H  →  O
    #   →  outer[edge_idx+1..]
    prefix = list(outer_pts[: edge_idx + 1]) + [o_pt, h_pt]
    suffix = [h_pt, o_pt] + list(outer_pts[edge_idx + 1:])
    return prefix + list(hole_rotated) + suffix


def mask_to_polygon(
    mask: np.ndarray,
    epsilon: float = 2.0,
) -> List[Tuple[float, float]]:
    """Convert a binary mask to a single polygon, handling holes with bridge technique.

    For masks with holes (e.g. annular / donut shapes) each hole is merged into
    the outer contour via :func:`_merge_hole_into_outer`, yielding a single
    closed polygon that is compatible with LabelMe and even-odd fill renderers.

    Args:
        mask: ``uint8`` array (values 0 or 255).
        epsilon: ``cv2.approxPolyDP`` simplification tolerance in pixels.
                 Pass ``0`` to keep every contour point.

    Returns:
        List of ``(x, y)`` float tuples, or empty list on failure.
    """
    binary = (mask > 0).astype(np.uint8) * 255
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours or hierarchy is None:
        return []

    h = hierarchy[0]  # shape (N, 4): [next, prev, first_child, parent]

    # Top-level (outer) contours have parent == -1
    outer_indices = [i for i in range(len(contours)) if h[i][3] == -1]
    if not outer_indices:
        return []

    # Pick the largest outer contour
    main_idx = max(outer_indices, key=lambda i: cv2.contourArea(contours[i]))
    outer_contour = contours[main_idx]
    if epsilon > 0:
        outer_contour = cv2.approxPolyDP(outer_contour, epsilon, True)
    outer_pts: List[Tuple[float, float]] = [
        (float(p[0][0]), float(p[0][1])) for p in outer_contour
    ]

    # Merge direct holes (children of main_idx)
    hole_indices = [i for i in range(len(contours)) if h[i][3] == main_idx]
    for hole_idx in hole_indices:
        hole_contour = contours[hole_idx]
        if epsilon > 0:
            hole_contour = cv2.approxPolyDP(hole_contour, epsilon, True)
        hole_pts = [(float(p[0][0]), float(p[0][1])) for p in hole_contour]
        if len(hole_pts) >= 3:
            outer_pts = _merge_hole_into_outer(outer_pts, hole_pts)

    return outer_pts


# ---------------------------------------------------------------------------
# Shared state-management mixin
# ---------------------------------------------------------------------------

class _RefineMixin:
    """Mixin: save/restore original annotation fields and shared dialog actions.

    Subclasses must set ``self._ann`` and ``self._panel`` before calling any
    mixin methods.  Call ``self._save_originals(annotation)`` in ``__init__``.
    """

    # ---- State helpers ----------------------------------------------------

    def _save_originals(self, annotation) -> None:
        self._orig_type = annotation.type
        self._orig_points = list(annotation.points)
        md = annotation.mask_data
        self._orig_mask_data = md.copy() if (md is not None and not isinstance(md, str)) else md
        self._orig_mask_shape = annotation.mask_shape

    def _restore_originals(self) -> None:
        self._ann.type = self._orig_type
        self._ann.points = self._orig_points
        self._ann.mask_data = self._orig_mask_data
        self._ann.mask_shape = self._orig_mask_shape

    def _decode_original_mask(self) -> Optional[np.ndarray]:
        """Decode the saved original mask to a ``uint8`` numpy array."""
        if self._orig_mask_data is None or self._orig_mask_shape is None:
            return None
        try:
            if not isinstance(self._orig_mask_data, str):
                return self._orig_mask_data.copy()
            compressed = base64.b64decode(self._orig_mask_data.encode("ascii"))
            raw = zlib.decompress(compressed)
            h, w = self._orig_mask_shape
            return np.frombuffer(raw, dtype=np.uint8).reshape(h, w).copy()
        except Exception as exc:
            print(f"⚠️ _decode_original_mask failed: {exc}")
            return None

    def _apply_result_preview(self, result: dict) -> None:
        """Mutate annotation with *result* for preview — no undo state saved."""
        self._ann.type = result["type"]
        self._ann.points = result["points"]
        self._ann.mask_data = result.get("mask_data")
        ms = result.get("mask_shape")
        self._ann.mask_shape = tuple(ms) if ms is not None else None

    def _commit_result(self, result: dict) -> None:
        """Apply *result* via ``annotation_manager`` so undo state is captured."""
        # Restore originals first so _save_state_to_undo captures clean state
        self._restore_originals()
        ms = result.get("mask_shape")
        update_data = {
            "type":       result["type"],
            "points":     result["points"],
            "mask_data":  result.get("mask_data"),
            "mask_shape": tuple(ms) if ms is not None else None,
        }
        self._panel.annotation_manager.update_annotation(self._ann.id, update_data)
        # select_annotation() calls _load_annotation_to_cv_panel() which updates
        # the C++ ROI layer, then sync_overlays().  Calling sync_overlays() alone
        # is not enough because the selected annotation's overlay is intentionally
        # skipped while it is loaded into the C++ ROI editor.
        self._panel.select_annotation(self._ann.id)

    # ---- Positioning -------------------------------------------------------

    def _position_near_parent(self) -> None:
        """Place dialog at the top-right of the parent window so the canvas stays visible."""
        parent = self.GetParent()
        if parent is None:
            self.Centre()
            return
        pr = parent.GetScreenRect()
        ds = self.GetBestSize()
        x = pr.GetRight() - ds.GetWidth() - 12
        y = pr.GetTop() + 44
        # Clamp to the display's client area
        try:
            disp_idx = wx.Display.GetFromWindow(parent)
            disp = wx.Display(disp_idx if disp_idx != wx.NOT_FOUND else 0).GetClientArea()
            x = max(disp.GetLeft(), min(x, disp.GetRight()  - ds.GetWidth()))
            y = max(disp.GetTop(),  min(y, disp.GetBottom() - ds.GetHeight()))
        except Exception:
            pass
        self.SetPosition(wx.Point(x, y))

    # ---- Shared button row ------------------------------------------------

    def _make_button_row(self) -> wx.BoxSizer:
        _btn_cls = wxbuttons.GenButton if platform.system() == "Darwin" else wx.Button
        self._btn_preview = _btn_cls(self, label=_("Preview"))
        self._btn_apply   = _btn_cls(self, label=_("Apply"))
        self._btn_cancel  = _btn_cls(self, label=_("Cancel"))
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self._btn_preview, 0, wx.ALL, 4)
        row.AddStretchSpacer()
        row.Add(self._btn_apply,  0, wx.ALL, 4)
        row.Add(self._btn_cancel, 0, wx.ALL, 4)
        self._btn_preview.Bind(wx.EVT_BUTTON, self._on_preview)
        self._btn_apply.Bind(wx.EVT_BUTTON,   self._on_apply)
        self._btn_cancel.Bind(wx.EVT_BUTTON,  self._on_cancel)
        return row

    # ---- Shared event handlers --------------------------------------------

    def _on_preview(self, event) -> None:
        result = self._compute()
        if result is None:
            wx.MessageBox(
                _("Operation resulted in an empty shape.\nTry reducing kernel size or iterations."),
                _("Preview"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        self._last_result = result
        self._apply_result_preview(result)
        # Use select_annotation instead of sync_overlays so the C++ ROI layer
        # is also refreshed via _load_annotation_to_cv_panel().
        self._panel.select_annotation(self._ann.id)

    def _on_apply(self, event) -> None:
        result = self._last_result if self._last_result is not None else self._compute()
        if result is None:
            wx.MessageBox(
                _("Operation resulted in an empty shape.\nTry reducing kernel size or iterations."),
                _("Apply"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        self._commit_result(result)   # internally calls select_annotation()
        self._applied = True
        if self._on_applied_cb:
            self._on_applied_cb()
        self.Close()

    def _on_cancel(self, event) -> None:
        self._restore_originals()
        self._panel.select_annotation(self._ann.id)
        self.Close()

    def _on_close_event(self, event) -> None:
        """Window X button — treat as Cancel if Apply was not clicked."""
        if not getattr(self, "_applied", False):
            self._restore_originals()
            self._panel.select_annotation(self._ann.id)
        self.Destroy()


# ---------------------------------------------------------------------------
# RefineMorphDialog
# ---------------------------------------------------------------------------

class RefineMorphDialog(_RefineMixin, wx.Dialog):
    """Apply morphological operations to a polygon or mask annotation.

    Workflow:

    * **Polygon** input → rasterize → morph → ``approxPolyDP(ε)`` → polygon
    * **Mask** input   → morph → mask  (type unchanged)

    Preview updates the canvas without saving undo state.
    Apply commits the change through ``AnnotationManager`` (undo-able).
    Cancel restores the original shape.
    """

    _OP_KEYS   = ["erosion", "dilation", "opening", "closing"]

    def __init__(self, parent, annotation, image_display_panel, img_h: int, img_w: int,
                 on_applied=None):
        wx.Dialog.__init__(
            self, parent,
            title=_("Refine Shape"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self._ann            = annotation
        self._panel          = image_display_panel
        self._img_h          = img_h
        self._img_w          = img_w
        self._last_result    = None
        self._applied        = False
        self._on_applied_cb  = on_applied
        self._save_originals(annotation)
        self._build_ui()
        self.Fit()
        self.SetMinSize(self.GetSize())
        self._position_near_parent()
        self.Bind(wx.EVT_CLOSE, self._on_close_event)

    # ---- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        # Info block
        ann_info = _("Annotation: #{id}  “{label}”  [{type}]").format(
            id=self._ann.id[:8], label=self._ann.label, type=self._orig_type
        )
        outer.Add(wx.StaticText(self, label=ann_info), 0, wx.ALL, 8)
        outer.Add(
            wx.StaticText(
                self,
                label=_("Image: {w} × {h}").format(w=self._img_w, h=self._img_h),
            ),
            0, wx.LEFT | wx.BOTTOM, 8,
        )
        outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # Operation RadioBox (2 columns)
        op_choices = [
            _("Erosion"),
            _("Dilation"),
            _("Opening"),
            _("Closing")
        ]
        self._op_radio = wx.RadioBox(
            self,
            label=_("Operation"),
            choices=op_choices,
            majorDimension=2,
            style=wx.RA_SPECIFY_COLS,
        )
        outer.Add(self._op_radio, 0, wx.EXPAND | wx.ALL, 8)

        # Parameters grid
        grid = wx.FlexGridSizer(cols=3, hgap=8, vgap=6)
        grid.AddGrowableCol(1)

        # Kernel size
        self._lbl_kernel      = wx.StaticText(self, label=_("Kernel size:"))
        self._spin_kernel     = wx.SpinCtrl(self, min=1, max=99, initial=3)
        self._lbl_kernel_unit = wx.StaticText(self, label=_("px"))
        grid.Add(self._lbl_kernel,      0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._spin_kernel,     0)
        grid.Add(self._lbl_kernel_unit, 0, wx.ALIGN_CENTER_VERTICAL)

        # Iterations
        self._lbl_iter  = wx.StaticText(self, label=_("Iterations:"))
        self._spin_iter = wx.SpinCtrl(self, min=1, max=20, initial=1)
        grid.Add(self._lbl_iter,  0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._spin_iter, 0)
        grid.Add(wx.StaticText(self, label=""), 0)

        # Epsilon (polygon output only)
        self._lbl_eps      = wx.StaticText(self, label=_("Smooth (ε):"))
        self._spin_eps     = wx.SpinCtrlDouble(self, min=0.0, max=50.0, initial=2.0, inc=0.5)
        self._spin_eps.SetDigits(1)
        self._lbl_eps_unit = wx.StaticText(self, label=_("px  (0 = keep all)"))
        grid.Add(self._lbl_eps,      0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self._spin_eps,     0)
        grid.Add(self._lbl_eps_unit, 0, wx.ALIGN_CENTER_VERTICAL)

        outer.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # Buttons
        outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        outer.Add(self._make_button_row(), 0, wx.EXPAND | wx.ALL, 6)

        self.SetSizer(outer)
        self._update_epsilon_visibility()

    def _update_epsilon_visibility(self) -> None:
        show = (self._orig_type == "polygon")
        for w in (self._lbl_eps, self._spin_eps, self._lbl_eps_unit):
            w.Show(show)
        self.Layout()

    # ---- Compute ----------------------------------------------------------

    def _compute(self) -> Optional[dict]:
        op          = self._OP_KEYS[self._op_radio.GetSelection()]
        kernel_size = self._spin_kernel.GetValue()
        iterations  = self._spin_iter.GetValue()
        epsilon     = self._spin_eps.GetValue() if self._orig_type == "polygon" else 0.0

        if self._orig_type == "polygon":
            if len(self._orig_points) < 3:
                return None
            raw_mask = polygon_to_mask(self._orig_points, self._img_h, self._img_w)
            new_mask = apply_morph_to_mask(raw_mask, op, kernel_size, iterations)
            if new_mask.max() == 0:
                return None
            new_pts = mask_to_polygon(new_mask, epsilon)
            if len(new_pts) < 3:
                return None
            return {
                "type": "polygon", "points": new_pts,
                "mask_data": None, "mask_shape": None,
            }

        elif self._orig_type == "mask":
            orig_mask = self._decode_original_mask()
            if orig_mask is None:
                return None
            new_mask = apply_morph_to_mask(orig_mask, op, kernel_size, iterations)
            if new_mask.max() == 0:
                return None
            ys, xs = np.where(new_mask > 0)
            x1, y1 = int(xs.min()), int(ys.min())
            x2, y2 = int(xs.max()), int(ys.max())
            h, w = new_mask.shape
            return {
                "type": "mask",
                "points": [(float(x1), float(y1)), (float(x2), float(y2))],
                "mask_data": new_mask,
                "mask_shape": (h, w),
            }

        return None


# ---------------------------------------------------------------------------
# MaskToPolygonDialog
# ---------------------------------------------------------------------------

class MaskToPolygonDialog(_RefineMixin, wx.Dialog):
    """Convert a mask annotation to a polygon annotation.

    Holes in the mask are handled automatically via the bridge technique —
    each hole is stitched into the outer contour with a horizontal cut,
    producing a single closed polygon that renders correctly with even-odd fill.

    After *Apply* the annotation type changes to ``"polygon"`` and the mask
    data is cleared.  The operation is undo-able via Ctrl+Z.
    """

    def __init__(self, parent, annotation, image_display_panel, img_h: int, img_w: int,
                 on_applied=None):
        wx.Dialog.__init__(
            self, parent,
            title=_("Convert Mask → Polygon"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self._ann            = annotation
        self._panel          = image_display_panel
        self._img_h          = img_h
        self._img_w          = img_w
        self._last_result    = None
        self._applied        = False
        self._on_applied_cb  = on_applied
        self._save_originals(annotation)
        self._hole_count = self._count_holes()
        self._build_ui()
        self.Fit()
        self.SetMinSize(self.GetSize())
        self._position_near_parent()
        self.Bind(wx.EVT_CLOSE, self._on_close_event)

    # ---- Hole analysis ----------------------------------------------------

    def _count_holes(self) -> int:
        mask = self._decode_original_mask()
        if mask is None:
            return 0
        binary = (mask > 0).astype(np.uint8) * 255
        contours, hierarchy = cv2.findContours(
            binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours or hierarchy is None:
            return 0
        h = hierarchy[0]
        outer_indices = [i for i in range(len(contours)) if h[i][3] == -1]
        if not outer_indices:
            return 0
        main_idx = max(outer_indices, key=lambda i: cv2.contourArea(contours[i]))
        return sum(1 for i in range(len(contours)) if h[i][3] == main_idx)

    # ---- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        # Info block
        ann_info = _("Annotation: #{id}  “{label}”  [{type}]").format(
            id=self._ann.id[:8], label=self._ann.label, type=self._orig_type
        )
        outer.Add(wx.StaticText(self, label=ann_info), 0, wx.ALL, 8)
        outer.Add(
            wx.StaticText(
                self,
                label=_("Image: {w} × {h}").format(w=self._img_w, h=self._img_h),
            ),
            0, wx.LEFT | wx.BOTTOM, 8,
        )
        outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # Epsilon row
        eps_row = wx.BoxSizer(wx.HORIZONTAL)
        eps_row.Add(
            wx.StaticText(self, label=_("Smooth (ε):")),
            0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8,
        )
        self._spin_eps = wx.SpinCtrlDouble(self, min=0.0, max=50.0, initial=2.0, inc=0.5)
        self._spin_eps.SetDigits(1)
        eps_row.Add(self._spin_eps, 0)
        eps_row.Add(
            wx.StaticText(self, label=_("px  (0 = keep all)")),
            0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8,
        )
        outer.Add(eps_row, 0, wx.ALL, 12)

        # Hole notice (only shown when holes detected)
        if self._hole_count > 0:
            outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            msg = _("Holes detected: {n}  →  Bridge technique applied").format(
                n=self._hole_count
            )
            outer.Add(
                wx.StaticText(self, label=f"\u2139  {msg}"),
                0, wx.ALL, 8,
            )

        # Buttons
        outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        outer.Add(self._make_button_row(), 0, wx.EXPAND | wx.ALL, 6)

        self.SetSizer(outer)

    # ---- Compute ----------------------------------------------------------

    def _compute(self) -> Optional[dict]:
        mask = self._decode_original_mask()
        if mask is None:
            return None
        epsilon = self._spin_eps.GetValue()
        pts = mask_to_polygon(mask, epsilon)
        if len(pts) < 3:
            return None
        return {
            "type": "polygon", "points": pts,
            "mask_data": None, "mask_shape": None,
        }


# ---------------------------------------------------------------------------
# PolygonToMaskDialog
# ---------------------------------------------------------------------------

class PolygonToMaskDialog(_RefineMixin, wx.Dialog):
    """Convert a polygon annotation to a mask annotation.

    The polygon is rasterized to a full-image binary mask via
    :func:`polygon_to_mask`.  Mask alpha (overlay transparency) can be
    adjusted before applying.

    After *Apply* the annotation type changes to ``"mask"`` and the points
    field is replaced with the mask bounding box.  The operation is
    undo-able via Ctrl+Z.
    """

    def __init__(self, parent, annotation, image_display_panel, img_h: int, img_w: int,
                 on_applied=None):
        wx.Dialog.__init__(
            self, parent,
            title=_("Convert Polygon → Mask"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self._ann            = annotation
        self._panel          = image_display_panel
        self._img_h          = img_h
        self._img_w          = img_w
        self._last_result    = None
        self._applied        = False
        self._on_applied_cb  = on_applied
        self._save_originals(annotation)
        self._build_ui()
        self.Fit()
        self.SetMinSize(self.GetSize())
        self._position_near_parent()
        self.Bind(wx.EVT_CLOSE, self._on_close_event)

    # ---- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        # Info block
        ann_info = _("Annotation: #{id}  “{label}”  [{type}]").format(
            id=self._ann.id[:8], label=self._ann.label, type=self._orig_type
        )
        outer.Add(wx.StaticText(self, label=ann_info), 0, wx.ALL, 8)
        outer.Add(
            wx.StaticText(
                self,
                label=_("Image: {w} × {h}  |  Points: {n}").format(
                    w=self._img_w, h=self._img_h, n=len(self._orig_points)
                ),
            ),
            0, wx.LEFT | wx.BOTTOM, 8,
        )
        outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # Mask alpha row
        alpha_row = wx.BoxSizer(wx.HORIZONTAL)
        alpha_row.Add(
            wx.StaticText(self, label=_("Mask alpha:")),
            0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8,
        )
        self._spin_alpha = wx.SpinCtrlDouble(self, min=0.1, max=1.0,
                                             initial=self._ann.mask_alpha
                                             if hasattr(self._ann, 'mask_alpha') else 0.5,
                                             inc=0.05)
        self._spin_alpha.SetDigits(2)
        alpha_row.Add(self._spin_alpha, 0)
        alpha_row.Add(
            wx.StaticText(self, label=_("(overlay transparency)")),
            0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8,
        )
        outer.Add(alpha_row, 0, wx.ALL, 12)

        # Buttons
        outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        outer.Add(self._make_button_row(), 0, wx.EXPAND | wx.ALL, 6)

        self.SetSizer(outer)

    # ---- Compute ----------------------------------------------------------

    def _compute(self) -> Optional[dict]:
        if len(self._orig_points) < 3:
            return None
        mask = polygon_to_mask(self._orig_points, self._img_h, self._img_w)
        if mask.max() == 0:
            return None
        ys, xs = np.where(mask > 0)
        x1, y1 = int(xs.min()), int(ys.min())
        x2, y2 = int(xs.max()), int(ys.max())
        h, w = mask.shape
        alpha = self._spin_alpha.GetValue()
        return {
            "type":       "mask",
            "points":     [(float(x1), float(y1)), (float(x2), float(y2))],
            "mask_data":  mask,
            "mask_shape": (h, w),
            "mask_alpha": alpha,
        }

    # ---- Override _apply_result_preview and _commit_result for mask_alpha --

    def _apply_result_preview(self, result: dict) -> None:
        super()._apply_result_preview(result)
        self._ann.mask_alpha = result.get("mask_alpha", 0.5)

    def _commit_result(self, result: dict) -> None:
        self._restore_originals()
        ms = result.get("mask_shape")
        update_data = {
            "type":       result["type"],
            "points":     result["points"],
            "mask_data":  result.get("mask_data"),
            "mask_shape": tuple(ms) if ms is not None else None,
            "mask_alpha": result.get("mask_alpha", 0.5),
        }
        self._panel.annotation_manager.update_annotation(self._ann.id, update_data)
        self._panel.select_annotation(self._ann.id)
