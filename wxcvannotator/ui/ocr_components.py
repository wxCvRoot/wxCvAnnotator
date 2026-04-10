#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR-specific UI Components
Includes floating text editors, transcription widgets, and OCR result review.
"""

from typing import List

import wx

from .i18n import _


class OcrLoadingDialog(wx.Dialog):
    """Non-modal indeterminate progress dialog shown during OCR model loading or inference.

    Usage::
        dlg = OcrLoadingDialog(parent, backend_name)
        dlg.Show()
        # background thread calls ocr_service.set_status_callback(
        #     lambda msg: wx.CallAfter(dlg.update_status, msg))
        # when done:
        dlg.close()
    """

    _PULSE_MS = 60  # timer interval for gauge pulse animation

    def __init__(self, parent, backend_name: str):
        super().__init__(
            parent,
            title=_("OCR"),
            style=wx.CAPTION | wx.STAY_ON_TOP,
            size=(400, 150),
        )
        self._init_ui(backend_name)
        self.CentreOnParent()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._timer.Start(self._PULSE_MS)

    def _init_ui(self, backend_name: str):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self._lbl_status = wx.StaticText(
            panel,
            label=_("Preparing OCR engine ({})...").format(backend_name),
        )
        self._lbl_status.Wrap(360)
        sizer.Add(self._lbl_status, 0, wx.ALL | wx.EXPAND, 14)

        self._gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        sizer.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 14)

        hint = wx.StaticText(
            panel,
            label=_("First run may take longer to load the model."),
        )
        hint_font = hint.GetFont()
        hint_font.SetPointSize(max(7, hint_font.GetPointSize() - 1))
        hint.SetFont(hint_font)
        hint.SetForegroundColour(wx.Colour(140, 140, 140))
        sizer.Add(hint, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 14)

        panel.SetSizer(sizer)
        dlg_sizer = wx.BoxSizer(wx.VERTICAL)
        dlg_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dlg_sizer)

    def _on_timer(self, event):
        self._gauge.Pulse()

    def update_status(self, msg: str):
        """Update the status label.  Safe to call via wx.CallAfter from a background thread."""
        if self._lbl_status:
            self._lbl_status.SetLabel(msg)
            self._lbl_status.Wrap(360)
            self.Layout()

    def close(self):
        """Stop the pulse animation and destroy the dialog (call from the main thread)."""
        if hasattr(self, '_timer') and self._timer.IsRunning():
            self._timer.Stop()
        if self:
            self.Destroy()

class TextEditPopup(wx.Dialog):
    """
    Floating dialog for editing annotation transcription.
    Appears near the selected annotation or mouse position.
    """
    
    def __init__(self, parent, title="Edit Transcription", initial_text=""):
        super().__init__(
            parent, 
            title=title, 
            style=wx.FRAME_FLOAT_ON_PARENT | wx.BORDER_SIMPLE | wx.CAPTION
        )
        
        self.initial_text = initial_text
        self.result_text = initial_text
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize UI layout"""
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Text entry field
        self.text_ctrl = wx.TextCtrl(
            self, 
            wx.ID_ANY, 
            self.initial_text, 
            style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER
        )
        self.text_ctrl.SetMinSize(wx.Size(300, 100))
        main_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        
        # Help label
        help_text = wx.StaticText(self, wx.ID_ANY, "Press Enter to confirm, Esc to cancel")
        help_text.SetForegroundColour(wx.Colour(100, 100, 100))
        help_font = help_text.GetFont()
        help_font.SetPointSize(8)
        help_text.SetFont(help_font)
        main_sizer.Add(help_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Buttons (optional, usually Enter/Esc suffice)
        btn_sizer = wx.StdDialogButtonSizer()
        
        self.btn_ok = wx.Button(self, wx.ID_OK, "Confirm")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        
        btn_sizer.AddButton(self.btn_ok)
        btn_sizer.AddButton(self.btn_cancel)
        btn_sizer.Realize()
        
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        
        # Bind events
        self.text_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_confirm)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        
    def _on_confirm(self, event):
        """Handle Enter key in text control"""
        if not event.ShiftDown(): # Allow Shift+Enter for newlines
            self.result_text = self.text_ctrl.GetValue()
            self.EndModal(wx.ID_OK)
        else:
            event.Skip()
            
    def _on_char_hook(self, event):
        """Handle Esc key globally in dialog"""
        key = event.GetKeyCode()
        if key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        elif key == wx.WXK_RETURN and not event.ShiftDown():
            # If focus is on text_ctrl, it will be handled by EVT_TEXT_ENTER
            # This is a fallback
            if self.FindFocus() != self.text_ctrl:
                self.result_text = self.text_ctrl.GetValue()
                self.EndModal(wx.ID_OK)
            else:
                event.Skip()
        else:
            event.Skip()
            
    def get_value(self):
        """Get the edited text"""
        return self.result_text


class OCRResultReviewDialog(wx.Dialog):
    """
    Review dialog for full-image OCR results.

    Presents detected text regions as a checklist so the user can accept or
    reject individual items before annotation objects are created.
    """

    def __init__(self, parent, results: List, title: str = ""):
        """
        Args:
            parent:  Parent window.
            results: List of ``OCRResult`` objects from ``OCRService.recognize_full()``.
            title:   Dialog title.  Auto-generated from result count when empty.
        """
        if not title:
            title = _("OCR Results — {} region(s) detected").format(len(results))
        super().__init__(
            parent, title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._results = results
        self._init_ui()
        self.SetMinSize(wx.Size(500, 340))
        self.Fit()
        self.Centre()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Info label ---
        n = len(self._results)
        has_bbox = any(r.bbox for r in self._results)
        if has_bbox:
            info_text = _(
                "{} text region(s) detected with location data.\n"
                "Checked items will become rectangle annotations."
            ).format(n)
        else:
            info_text = _(
                "{} text block(s) detected (no location — full-image rectangle will be created)."
            ).format(n)
        info_label = wx.StaticText(self, wx.ID_ANY, info_text)
        info_label.Wrap(460)
        main_sizer.Add(info_label, 0, wx.ALL, 10)

        # --- CheckListBox ---
        entries = []
        for r in self._results:
            text = r.text.replace('\n', ' ').strip()
            if len(text) > 78:
                text = text[:75] + "..."
            if r.bbox:
                xs = [p[0] for p in r.bbox]
                ys = [p[1] for p in r.bbox]
                coord = "  [{:.0f},{:.0f}–{:.0f},{:.0f}]".format(
                    min(xs), min(ys), max(xs), max(ys)
                )
            else:
                coord = "  [full image]"
            entries.append(text + coord)

        self._check_list = wx.CheckListBox(self, wx.ID_ANY, choices=entries)
        for i in range(len(entries)):
            self._check_list.Check(i, True)
        self._check_list.SetMinSize(wx.Size(460, 200))
        main_sizer.Add(self._check_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # --- Select All / Deselect All ---
        sel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_all = wx.Button(self, wx.ID_ANY, _("Select All"))
        btn_none = wx.Button(self, wx.ID_ANY, _("Deselect All"))
        btn_all.Bind(wx.EVT_BUTTON, lambda e: self._check_all(True))
        btn_none.Bind(wx.EVT_BUTTON, lambda e: self._check_all(False))
        sel_sizer.Add(btn_all, 0, wx.RIGHT, 6)
        sel_sizer.Add(btn_none, 0)
        main_sizer.Add(sel_sizer, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # --- OK / Cancel ---
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK, _("Create Annotations"))
        cancel_btn = wx.Button(self, wx.ID_CANCEL, _("Cancel"))
        ok_btn.SetDefault()
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_all(self, state: bool):
        for i in range(self._check_list.GetCount()):
            self._check_list.Check(i, state)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_accepted_results(self) -> List:
        """Return OCRResult objects whose checkboxes are ticked."""
        return [
            self._results[i]
            for i in range(self._check_list.GetCount())
            if self._check_list.IsChecked(i)
        ]
