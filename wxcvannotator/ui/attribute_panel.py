#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attribute Panel - Editable panel for annotation attributes, flags, and transcription.
Displayed below the Annotation List when enabled in settings.
"""

import wx
import wx.lib.scrolledpanel as scrolled
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from .i18n import _


class AttributePanel(wx.Panel):
    """Panel for editing annotation attributes, flags, and transcription text.

    Args:
        parent: Parent wx window.
        default_flags: List of predefined flag names.
        on_change: Callback invoked with (annotation_id, changes_dict) when user edits a field.
    """

    def __init__(self, parent: wx.Window, default_flags: Optional[List[str]] = None,
                 on_change: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        super().__init__(parent, wx.ID_ANY)
        self._annotation = None  # Current annotation reference
        self._on_change = on_change
        self._default_flags = default_flags or ["occluded", "truncated", "difficult"]
        self._attr_rows: List[Dict[str, Any]] = []  # key_ctrl, val_ctrl, del_btn
        self._suppress_events = False  # Prevent feedback loops during set_annotation

        self._setup_ui()

    def _setup_ui(self):
        """Build the panel layout."""
        self.SetBackgroundColour(wx.Colour(50, 50, 50))

        outer_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        self.title = wx.StaticText(self, label=_("Attributes"))
        self.title.SetForegroundColour(wx.WHITE)
        title_font = self.title.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title.SetFont(title_font)
        outer_sizer.Add(self.title, 0, wx.ALL | wx.CENTER, 5)

        # Placeholder (shown when no annotation selected)
        self.placeholder = wx.StaticText(self, label=_("Select an annotation to edit attributes"))
        self.placeholder.SetForegroundColour(wx.Colour(150, 150, 150))
        outer_sizer.Add(self.placeholder, 0, wx.ALL | wx.CENTER, 10)

        # Scrollable content area — this is the key to making the panel scrollable
        self.scroll_panel = scrolled.ScrolledPanel(self, style=wx.VSCROLL)
        self.scroll_panel.SetBackgroundColour(wx.Colour(50, 50, 50))
        self.scroll_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Transcription ---
        self.lbl_transcription = wx.StaticText(self.scroll_panel, label=_("Transcription:"))
        self.lbl_transcription.SetForegroundColour(wx.Colour(200, 200, 200))
        self.content_sizer.Add(self.lbl_transcription, 0, wx.LEFT | wx.TOP, 5)

        self.txt_transcription = wx.TextCtrl(
            self.scroll_panel, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER,
            size=(-1, 50)
        )
        self.txt_transcription.SetBackgroundColour(wx.Colour(40, 40, 43))
        self.txt_transcription.SetForegroundColour(wx.WHITE)
        self.content_sizer.Add(self.txt_transcription, 0, wx.EXPAND | wx.ALL, 5)
        self.txt_transcription.Bind(wx.EVT_KILL_FOCUS, self._on_transcription_changed)

        # --- Flags ---
        self.lbl_flags = wx.StaticText(self.scroll_panel, label=_("Flags:"))
        self.lbl_flags.SetForegroundColour(wx.Colour(200, 200, 200))
        self.content_sizer.Add(self.lbl_flags, 0, wx.LEFT | wx.TOP, 5)

        self.flags_panel = wx.Panel(self.scroll_panel)
        self.flags_panel.SetBackgroundColour(wx.Colour(50, 50, 50))
        self.flags_sizer = wx.BoxSizer(wx.VERTICAL)
        self.flag_checkboxes: Dict[str, wx.CheckBox] = {}
        self._build_flag_checkboxes()
        self.flags_panel.SetSizer(self.flags_sizer)
        self.content_sizer.Add(self.flags_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        # --- Custom Attributes ---
        self.lbl_custom_attr = wx.StaticText(self.scroll_panel, label=_("Custom Attributes:"))
        self.lbl_custom_attr.SetForegroundColour(wx.Colour(200, 200, 200))
        self.content_sizer.Add(self.lbl_custom_attr, 0, wx.LEFT | wx.TOP, 5)

        # Container for attribute rows (no nested scroll — parent scroll_panel handles it)
        self.attrs_container = wx.Panel(self.scroll_panel)
        self.attrs_container.SetBackgroundColour(wx.Colour(50, 50, 50))
        self.attrs_sizer = wx.BoxSizer(wx.VERTICAL)
        self.attrs_container.SetSizer(self.attrs_sizer)
        self.content_sizer.Add(self.attrs_container, 0, wx.EXPAND | wx.ALL, 5)

        # Add button
        self.btn_add_attr = wx.Button(self.scroll_panel, label=_("+ Add"))
        self.btn_add_attr.SetBackgroundColour(wx.Colour(60, 60, 65))
        self.btn_add_attr.SetForegroundColour(wx.WHITE)
        self.content_sizer.Add(self.btn_add_attr, 0, wx.ALIGN_LEFT | wx.LEFT | wx.BOTTOM, 5)
        self.btn_add_attr.Bind(wx.EVT_BUTTON, self._on_add_attribute)

        self.scroll_panel.SetSizer(self.content_sizer)
        outer_sizer.Add(self.scroll_panel, 1, wx.EXPAND)

        self.SetSizer(outer_sizer)

        # Initially hide content, show placeholder
        self.scroll_panel.Hide()

    def refresh_translations(self):
        """Update all text labels for the current language."""
        self.title.SetLabel(_("Attributes"))
        self.placeholder.SetLabel(_("Select an annotation to edit attributes"))
        self.lbl_transcription.SetLabel(_("Transcription:"))
        self.lbl_flags.SetLabel(_("Flags:"))
        self.lbl_custom_attr.SetLabel(_("Custom Attributes:"))
        self.btn_add_attr.SetLabel(_("+ Add"))
        self.Layout()

    def _build_flag_checkboxes(self):
        """Create checkboxes for each default flag."""
        for flag_name in self._default_flags:
            cb = wx.CheckBox(self.flags_panel, label=flag_name)
            cb.SetForegroundColour(wx.WHITE)
            cb.Bind(wx.EVT_CHECKBOX, self._on_flag_changed)
            self.flags_sizer.Add(cb, 0, wx.ALL, 2)
            self.flag_checkboxes[flag_name] = cb

    def update_default_flags(self, flags: List[str]):
        """Rebuild flag checkboxes with a new list of flags."""
        self._default_flags = flags
        # Clear old
        for cb in self.flag_checkboxes.values():
            cb.Destroy()
        self.flag_checkboxes.clear()
        # Rebuild
        self._build_flag_checkboxes()
        self.flags_panel.Layout()

    def set_annotation(self, annotation) -> None:
        """Populate the panel from an annotation object.

        Args:
            annotation: An Annotation instance, or None to clear.
        """
        self._suppress_events = True
        self._annotation = annotation

        if annotation is None:
            self.scroll_panel.Hide()
            self.placeholder.Show()
            self.Layout()
            self._suppress_events = False
            return

        self.placeholder.Hide()
        self.scroll_panel.Show()

        # Transcription
        self.txt_transcription.SetValue(annotation.transcription or "")

        # Flags
        flags = getattr(annotation, 'flags', {})
        for name, cb in self.flag_checkboxes.items():
            cb.SetValue(bool(flags.get(name, False)))

        # Custom attributes — filter out internal computed keys
        self._rebuild_attr_rows(annotation.attributes)

        self.Layout()
        self.scroll_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        self._suppress_events = False

    def _rebuild_attr_rows(self, attributes: Dict[str, Any]):
        """Rebuild the custom attribute key-value rows."""
        # Clear existing rows
        for row in self._attr_rows:
            row["key"].Destroy()
            row["val"].Destroy()
            row["del"].Destroy()
        self._attr_rows.clear()
        self.attrs_sizer.Clear()

        # Internal keys that shouldn't be shown in custom attributes
        internal_keys = {"center_x", "center_y", "radius", "x", "y", "width", "height",
                         "inner_radius", "outer_radius", "angle"}

        for key, val in attributes.items():
            if key in internal_keys:
                continue
            self._add_attr_row(str(key), str(val))

        self.attrs_container.Layout()

    def _add_attr_row(self, key: str = "", val: str = ""):
        """Add a single key-value attribute row."""
        row_sizer = wx.BoxSizer(wx.HORIZONTAL)

        key_ctrl = wx.TextCtrl(self.attrs_container, value=key, size=(80, -1),
                               style=wx.TE_PROCESS_ENTER)
        key_ctrl.SetBackgroundColour(wx.Colour(40, 40, 43))
        key_ctrl.SetForegroundColour(wx.WHITE)
        key_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_attr_changed)

        val_ctrl = wx.TextCtrl(self.attrs_container, value=val,
                               style=wx.TE_PROCESS_ENTER)
        val_ctrl.SetBackgroundColour(wx.Colour(40, 40, 43))
        val_ctrl.SetForegroundColour(wx.WHITE)
        val_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_attr_changed)

        del_btn = wx.Button(self.attrs_container, label="X", size=(24, -1))
        del_btn.SetBackgroundColour(wx.Colour(80, 40, 40))
        del_btn.SetForegroundColour(wx.WHITE)

        row_sizer.Add(key_ctrl, 1, wx.RIGHT, 2)
        row_sizer.Add(val_ctrl, 2, wx.RIGHT, 2)
        row_sizer.Add(del_btn, 0)

        self.attrs_sizer.Add(row_sizer, 0, wx.EXPAND | wx.BOTTOM, 2)

        row_data = {"key": key_ctrl, "val": val_ctrl, "del": del_btn, "sizer": row_sizer}
        self._attr_rows.append(row_data)

        del_btn.Bind(wx.EVT_BUTTON, lambda evt, r=row_data: self._on_delete_attr_row(r))

    def _notify_change(self, changes: Dict[str, Any]):
        """Send changes to the callback if available."""
        if self._suppress_events or self._annotation is None:
            return
        if self._on_change:
            self._on_change(self._annotation.id, changes)

    # --- Event Handlers ---

    def _on_transcription_changed(self, event):
        """Handle transcription text change."""
        event.Skip()
        if self._annotation is None or self._suppress_events:
            return
        new_text = self.txt_transcription.GetValue()
        if new_text != (self._annotation.transcription or ""):
            self._notify_change({"transcription": new_text})

    def _on_flag_changed(self, event):
        """Handle flag checkbox toggle."""
        if self._annotation is None or self._suppress_events:
            return
        flags = {}
        for name, cb in self.flag_checkboxes.items():
            flags[name] = cb.GetValue()
        self._notify_change({"flags": flags})

    def _on_attr_changed(self, event):
        """Handle custom attribute key or value change."""
        event.Skip()
        if self._annotation is None or self._suppress_events:
            return
        self._collect_and_notify_attrs()

    def _on_add_attribute(self, event):
        """Add a new empty attribute row."""
        self._add_attr_row()
        self.attrs_container.Layout()
        self.scroll_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        self.Layout()

    def _on_delete_attr_row(self, row_data: Dict[str, Any]):
        """Delete an attribute row and notify."""
        row_data["key"].Destroy()
        row_data["val"].Destroy()
        row_data["del"].Destroy()
        self.attrs_sizer.Remove(row_data["sizer"])
        self._attr_rows.remove(row_data)
        self.attrs_container.Layout()
        self.scroll_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        self.Layout()
        self._collect_and_notify_attrs()

    def _collect_and_notify_attrs(self):
        """Collect all attribute rows and notify change."""
        if self._annotation is None or self._suppress_events:
            return
        # Preserve internal keys from current annotation
        internal_keys = {"center_x", "center_y", "radius", "x", "y", "width", "height",
                         "inner_radius", "outer_radius", "angle"}
        new_attrs = {k: v for k, v in self._annotation.attributes.items() if k in internal_keys}

        for row in self._attr_rows:
            key = row["key"].GetValue().strip()
            val = row["val"].GetValue()
            if key and key not in internal_keys:
                new_attrs[key] = val

        # For attributes, we replace entirely rather than merge
        self._annotation.attributes = new_attrs
        self._annotation.modified_time = datetime.now()
        if self._on_change:
            self._on_change(self._annotation.id, {"_attrs_replaced": True})

    def get_changes(self) -> Dict[str, Any]:
        """Return the current panel state as a dict of changes.

        Returns:
            Dict with transcription, flags, and attributes from current UI state.
        """
        result: Dict[str, Any] = {}
        if self._annotation is None:
            return result

        result["transcription"] = self.txt_transcription.GetValue()
        result["flags"] = {name: cb.GetValue() for name, cb in self.flag_checkboxes.items()}

        internal_keys = {"center_x", "center_y", "radius", "x", "y", "width", "height",
                         "inner_radius", "outer_radius", "angle"}
        attrs = {k: v for k, v in self._annotation.attributes.items() if k in internal_keys}
        for row in self._attr_rows:
            key = row["key"].GetValue().strip()
            val = row["val"].GetValue()
            if key and key not in internal_keys:
                attrs[key] = val
        result["attributes"] = attrs

        return result

    def apply_theme(self, bg_color: str, fg_color: str, bg_list: str):
        """Apply theme colors to the panel.

        Args:
            bg_color: Background color hex string.
            fg_color: Foreground color hex string.
            bg_list: List/input background color hex string.
        """
        bg = wx.Colour(bg_color)
        fg = wx.Colour(fg_color)
        bg_l = wx.Colour(bg_list)

        self.SetBackgroundColour(bg)
        self.scroll_panel.SetBackgroundColour(bg)
        self.flags_panel.SetBackgroundColour(bg)
        self.attrs_container.SetBackgroundColour(bg)
        self.title.SetForegroundColour(fg)
        self.placeholder.SetForegroundColour(wx.Colour(150, 150, 150))

        self.txt_transcription.SetBackgroundColour(bg_l)
        self.txt_transcription.SetForegroundColour(fg)

        for cb in self.flag_checkboxes.values():
            cb.SetForegroundColour(fg)

        for row in self._attr_rows:
            row["key"].SetBackgroundColour(bg_l)
            row["key"].SetForegroundColour(fg)
            row["val"].SetBackgroundColour(bg_l)
            row["val"].SetForegroundColour(fg)

        self.Refresh()
