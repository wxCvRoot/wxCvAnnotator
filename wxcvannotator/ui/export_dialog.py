#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Dialogs for wxCvAnnotator
Contains:
1. ExportDialog: Single image export configuration
2. BatchExportDialog: Simple batch export without splitting
3. AdvancedExportDialog: Dataset splitting and advanced YOLO support
"""

import wx
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from .i18n import _

# ExportDialog removed at user request (single image export no longer needed)


class BatchExportDialog(wx.Dialog):
    """Simple batch export dialog"""
    def __init__(self, parent, export_system, image_files, image_dimensions):
        super().__init__(parent, title=_("Batch Export"), size=(450, 300))
        self.export_system = export_system
        self.image_files = image_files
        self.image_dimensions = image_dimensions
        
        self._setup_ui()
        self.CenterOnParent()

    def _setup_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        info_text = wx.StaticText(self, label=_("Export {} images to selected format.").format(len(self.image_files)))
        sizer.Add(info_text, 0, wx.ALL, 10)
        
        # Format
        fmt_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Export Format"))
        self.format_choices = [
            ("yolo_seg", _("YOLO Segmentation (Polygon)")),
            ("yolo_detect", _("YOLO Detection (BBox)")),
            ("yolo_obb", _("YOLO OBB (Rotated Rect)")),
            ("coco_1", _("MS COCO (Standard, Index=1)")),
            ("coco_0", _("MS COCO (Custom, Index=0)")),
            ("voc_2012", _("Pascal VOC 2012 (XML)")),
            ("csv", _("CSV (Generic table)"))
        ]
        self.choice_format = wx.Choice(self, choices=[c[1] for c in self.format_choices])
        self.choice_format.SetSelection(0)
        fmt_box.Add(self.choice_format, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(fmt_box, 0, wx.EXPAND | wx.ALL, 10)
        
        # Output Dir
        dir_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Output Directory"))
        self.dir_picker = wx.DirPickerCtrl(self, style=wx.DIRP_DIR_MUST_EXIST)
        dir_box.Add(self.dir_picker, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(dir_box, 0, wx.EXPAND | wx.ALL, 10)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self, wx.ID_OK, _("Start Export"))
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, _("Cancel"))
        btn_sizer.Add(self.btn_start, 0, wx.ALL, 5)
        btn_sizer.Add(self.btn_cancel, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.SetSizer(sizer)
        self.Bind(wx.EVT_BUTTON, self._on_start, id=wx.ID_OK)

    def _on_start(self, event):
        fmt = self.format_choices[self.choice_format.GetSelection()][0]
        out_dir = self.dir_picker.GetPath()
        
        if not out_dir:
            wx.MessageBox(_("Please select an output directory"), _("Error"), wx.OK | wx.ICON_ERROR)
            return

        # Show progress
        progress = wx.ProgressDialog(
            _("Exporting..."), 
            _("Processing images"), 
            maximum=len(self.image_files),
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_SMOOTH
        )
        
        results = self.export_system.batch_export(fmt, out_dir, self.image_files, self.image_dimensions)
        
        success_count = sum(1 for v in results.values() if v)
        progress.Destroy()
        
        wx.MessageBox(
            _("Batch Export Complete!\nSuccessfully exported {}/{} images.").format(success_count, len(self.image_files)),
            _("Finished"), wx.OK | wx.ICON_INFORMATION
        )
        self.EndModal(wx.ID_OK)


class AdvancedExportDialog(wx.Dialog):
    """Dataset splitting and advanced YOLO support"""
    def __init__(self, parent, image_files: List[str]):
        super().__init__(
            parent, 
            title=_("Dataset Export (Split)"), 
            size=(550, 750),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.image_files = image_files
        self.total_count = len(image_files)
        
        # Internal state
        self.fixed_counts = {"train": 0, "val": 0, "test": 0, "none": 0}
        self._analyze_dataset()
        
        self._setup_ui()
        self._update_preview()
        self.CenterOnParent()

    def _analyze_dataset(self):
        """Analyze existing .json files to count fixed statuses."""
        import json
        self.fixed_counts = {"train": 0, "val": 0, "test": 0, "none": 0}
        
        for img_path in self.image_files:
            json_path = Path(img_path).with_suffix('.json')
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        status = data.get("status", "none").lower()
                        if status in self.fixed_counts:
                            self.fixed_counts[status] += 1
                        else:
                            self.fixed_counts["none"] += 1
                except:
                    self.fixed_counts["none"] += 1
            else:
                self.fixed_counts["none"] += 1

    def _setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 1. Format Selection
        format_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Export Format"))
        formats = [
            ("yolo_detect", _("YOLO Detection (Bounding Box)")),
            ("yolo_seg", _("YOLO Segmentation (Polygon)")),
            ("yolo_obb", _("YOLO OBB (Rotated Rect)")),
            ("coco", _("MS COCO (JSON)")),
            ("voc_2012", _("Pascal VOC 2012 (XML)")),
            ("csv", _("CSV (Generic table)"))
        ]
        
        self.rb_formats = {}
        gs = wx.GridSizer(3, 2, 5, 5)
        for fmt_id, fmt_name in formats:
            rb = wx.RadioButton(self, label=fmt_name, style=wx.RB_GROUP if not self.rb_formats else 0)
            rb.Bind(wx.EVT_RADIOBUTTON, lambda e, f=fmt_id: self._on_format_changed(f))
            self.rb_formats[fmt_id] = rb
            gs.Add(rb, 0, wx.EXPAND)
            
        # Set initial selection
        self.rb_formats["yolo_seg"].SetValue(True)
        self.current_format = "yolo_seg"
        format_box.Add(gs, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(format_box, 0, wx.EXPAND | wx.ALL, 10)
        
        # 2. Dataset Splitting
        split_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Dataset Splitting"))
        
        # Honor manual toggle
        self.chk_honor_manual = wx.CheckBox(self, label=_("Honor Manual Status (fixed in File List)"))
        self.chk_honor_manual.SetValue(True)
        self.chk_honor_manual.Bind(wx.EVT_CHECKBOX, self._on_settings_dirty)
        split_box.Add(self.chk_honor_manual, 0, wx.ALL, 5)
        
        # Ratios (SpinCtrls)
        ratio_sizer = wx.FlexGridSizer(3, 3, 10, 10)
        
        ratio_sizer.Add(wx.StaticText(self, label=_("Train (%):")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_train = wx.SpinCtrlDouble(self, value="70", min=0, max=100, inc=1)
        self.spin_train.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_ratio_changed)
        ratio_sizer.Add(self.spin_train, 0, wx.EXPAND)
        self.lbl_train_fixed = wx.StaticText(self, label="(0 Fixed)")
        ratio_sizer.Add(self.lbl_train_fixed, 0, wx.ALIGN_CENTER_VERTICAL)
        
        ratio_sizer.Add(wx.StaticText(self, label=_("Val (%):")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_val = wx.SpinCtrlDouble(self, value="20", min=0, max=100, inc=1)
        self.spin_val.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_ratio_changed)
        ratio_sizer.Add(self.spin_val, 0, wx.EXPAND)
        self.lbl_val_fixed = wx.StaticText(self, label="(0 Fixed)")
        ratio_sizer.Add(self.lbl_val_fixed, 0, wx.ALIGN_CENTER_VERTICAL)
        
        ratio_sizer.Add(wx.StaticText(self, label=_("Test (%):")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_test = wx.SpinCtrlDouble(self, value="10", min=0, max=100, inc=1)
        self.spin_test.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_ratio_changed)
        ratio_sizer.Add(self.spin_test, 0, wx.EXPAND)
        self.lbl_test_fixed = wx.StaticText(self, label="(0 Fixed)")
        ratio_sizer.Add(self.lbl_test_fixed, 0, wx.ALIGN_CENTER_VERTICAL)
        
        split_box.Add(ratio_sizer, 0, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(split_box, 0, wx.EXPAND | wx.ALL, 10)
        
        # 3. Preview
        preview_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Distribution Preview"))
        self.lbl_preview = wx.StaticText(self, label=_("Analyzing..."))
        preview_box.Add(self.lbl_preview, 0, wx.ALL, 10)
        main_sizer.Add(preview_box, 0, wx.EXPAND | wx.ALL, 10)
        
        # 4. Format Specific Options (Contextual)
        self.option_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Format Specific Options"))
        self.panel_coco_opts = wx.Panel(self)
        coco_opts_sizer = wx.BoxSizer(wx.HORIZONTAL)
        coco_opts_sizer.Add(wx.StaticText(self.panel_coco_opts, label=_("Category Index Start:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.choice_coco_idx = wx.Choice(self.panel_coco_opts, choices=["1 (Standard)", "0 (Custom/YOLO-style)"])
        self.choice_coco_idx.SetSelection(0)
        coco_opts_sizer.Add(self.choice_coco_idx, 0, wx.EXPAND)
        self.panel_coco_opts.SetSizer(coco_opts_sizer)
        self.option_box.Add(self.panel_coco_opts, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(self.option_box, 0, wx.EXPAND | wx.ALL, 10)
        self.panel_coco_opts.Hide() # Initially hidden
        
        # 5. Settings & Output
        out_box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Output Settings"))
        
        self.chk_copy_images = wx.CheckBox(self, label=_("Copy Image Files (create standalone dataset)"))
        self.chk_copy_images.SetValue(True)
        out_box.Add(self.chk_copy_images, 0, wx.ALL, 5)
        
        path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        path_sizer.Add(wx.StaticText(self, label=_("Output Dir:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.path_picker = wx.DirPickerCtrl(self, style=wx.DIRP_DIR_MUST_EXIST)
        path_sizer.Add(self.path_picker, 1, wx.EXPAND | wx.ALL, 5)
        out_box.Add(path_sizer, 0, wx.EXPAND)
        
        main_sizer.Add(out_box, 0, wx.EXPAND | wx.ALL, 10)
        
        # Buttons
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_format_changed(self, fmt_id):
        self.current_format = fmt_id
        
        # Show/Hide format-specific options
        if fmt_id == "coco":
            self.panel_coco_opts.Show()
        else:
            self.panel_coco_opts.Hide()
            
        self.Layout()
        self._on_settings_dirty(None)

    def _on_ratio_changed(self, event):
        self._update_preview()

    def _on_settings_dirty(self, event):
        self._update_preview()

    def _update_preview(self):
        honor = self.chk_honor_manual.GetValue()
        
        if honor:
            fixed_train = self.fixed_counts["train"]
            fixed_val = self.fixed_counts["val"]
            fixed_test = self.fixed_counts["test"]
            unassigned = self.fixed_counts["none"]
        else:
            fixed_train = fixed_val = fixed_test = 0
            unassigned = self.total_count
            
        self.lbl_train_fixed.SetLabel(f"({fixed_train} Fixed)")
        self.lbl_val_fixed.SetLabel(f"({fixed_val} Fixed)")
        self.lbl_test_fixed.SetLabel(f"({fixed_test} Fixed)")
        
        # Calculate random split for unassigned
        t_p = self.spin_train.GetValue() / 100.0
        v_p = self.spin_val.GetValue() / 100.0
        ts_p = self.spin_test.GetValue() / 100.0
        
        total_p = t_p + v_p + ts_p
        if total_p > 0:
            rand_train = int(unassigned * (t_p / total_p))
            rand_val = int(unassigned * (v_p / total_p))
            rand_test = unassigned - rand_train - rand_val
        else:
            rand_train = rand_val = rand_test = 0
            
        final_train = fixed_train + rand_train
        final_val = fixed_val + rand_val
        final_test = fixed_test + rand_test
        
        preview_text = (
            f"{_('Total Images')}: {self.total_count}\n"
            f"{_('Train')}: {final_train} ({fixed_train} Fixed + {rand_train} Random)\n"
            f"{_('Valid')}: {final_val} ({fixed_val} Fixed + {rand_val} Random)\n"
            f"{_('Test')}: {final_test} ({fixed_test} Fixed + {rand_test} Random)"
        )
        self.lbl_preview.SetLabel(preview_text)
        self.Layout()

    def _on_ok(self, event):
        # Validate ratios
        t = self.spin_train.GetValue()
        v = self.spin_val.GetValue()
        ts = self.spin_test.GetValue()
        
        # Train/Val cannot be zero
        if t <= 0 or v <= 0:
            wx.MessageBox(_("Train and Val ratios must be greater than 0%"), _("Error"), wx.OK | wx.ICON_ERROR)
            return

        # Warning for sum not equal to 100
        total_ratio = t + v + ts
        if abs(total_ratio - 100) > 0.1:
            wx.MessageBox(
                _("Note: Ratios sum to {}%. The application will treat them as weights but it's recommended to sum to 100%.").format(total_ratio), 
                _("Warning"), 
                wx.OK | wx.ICON_WARNING
            )
            
        if not self.path_picker.GetPath():
            wx.MessageBox(_("Please select an output directory"), _("Error"), wx.OK | wx.ICON_ERROR)
            return
            
        self.EndModal(wx.ID_OK)

    def get_settings(self) -> Dict[str, Any]:
        settings = {
            "format": self.current_format,
            "honor_manual": self.chk_honor_manual.GetValue(),
            "train_ratio": self.spin_train.GetValue() / 100.0,
            "val_ratio": self.spin_val.GetValue() / 100.0,
            "test_ratio": self.spin_test.GetValue() / 100.0,
            "copy_images": self.chk_copy_images.GetValue(),
            "output_dir": self.path_picker.GetPath()
        }
        
        if self.current_format == "coco":
            settings["coco_start_index"] = 1 if self.choice_coco_idx.GetSelection() == 0 else 0
            
        return settings