#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings Dialog - A professional categorized settings interface for wxCvAnnotator.
"""

import wx
import wx.lib.buttons as wxbuttons
import os
import platform
from typing import Dict, Any, List
from .i18n import _, get_i18n_manager
from .theme_manager import get_theme_manager


class _ThemedChoice(wx.Panel):
    """macOS-compatible themed dropdown replacement for wx.Choice.

    wx.Choice on macOS wraps NSPopUpButton which ignores custom colours set
    via SetForegroundColour/SetBackgroundColour.  This control draws itself
    with a wx DC and shows a wx.Menu popup on click, giving full colour
    control without native rendering interference.

    Public API is a compatible subset of wx.Choice:
        GetSelection() / SetSelection(n)
        SetItems(items)
    Emits wx.EVT_CHOICE on selection change so existing Bind() calls work.
    """

    _ARROW = "▾"
    _H_PAD = 6

    def __init__(self, parent, choices=None, **kwargs):
        super().__init__(parent, style=wx.BORDER_SIMPLE, **kwargs)
        self._choices = list(choices) if choices else []
        self._sel = 0
        self.SetMinSize((-1, 26))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)
        self.Bind(wx.EVT_SIZE, lambda e: self.Refresh())

    # --- wx.Choice-compatible API ---

    def GetSelection(self):
        return self._sel

    def SetSelection(self, n):
        if 0 <= n < len(self._choices):
            self._sel = n
            self.Refresh()

    def SetItems(self, items):
        self._choices = list(items)
        if self._sel >= len(self._choices):
            self._sel = 0
        self.Refresh()

    # --- Drawing ---

    def _on_paint(self, event):
        dc = wx.BufferedPaintDC(self)
        w, h = self.GetClientSize()
        bg = self.GetBackgroundColour()
        fg = self.GetForegroundColour()

        dc.SetBackground(wx.Brush(bg))
        dc.Clear()
        dc.SetFont(self.GetFont())
        dc.SetTextForeground(fg)

        # Current selection text
        text = self._choices[self._sel] if 0 <= self._sel < len(self._choices) else ""
        _, th = dc.GetTextExtent(text)
        dc.DrawText(text, self._H_PAD, (h - th) // 2)

        # Dropdown arrow on the right
        aw, ah = dc.GetTextExtent(self._ARROW)
        dc.DrawText(self._ARROW, w - aw - self._H_PAD, (h - ah) // 2)

    def _on_click(self, event):
        menu = wx.Menu()
        for i, label in enumerate(self._choices):
            item = menu.AppendRadioItem(wx.ID_ANY, label)
            if i == self._sel:
                item.Check(True)
            menu.Bind(wx.EVT_MENU, lambda e, idx=i: self._select(idx), item)
        self.PopupMenu(menu, wx.Point(0, self.GetSize().height))
        menu.Destroy()

    def _select(self, idx):
        self._sel = idx
        self.Refresh()
        evt = wx.CommandEvent(wx.wxEVT_CHOICE, self.GetId())
        evt.SetInt(idx)
        evt.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(evt)


# macOS: use _ThemedChoice; Windows/Linux: use native wx.Choice
_CHOICE_CLS = _ThemedChoice if platform.system() == 'Darwin' else wx.Choice

# macOS: use GenButton; Windows/Linux: use native wx.Button
_BTN_CLS = wxbuttons.GenButton if platform.system() == 'Darwin' else wx.Button


class SettingsDialog(wx.Dialog):
    """Categorized settings dialog using a Listbook layout."""
    
    def __init__(self, parent, settings_manager):
        super().__init__(
            parent, 
            title=_("Settings"), 
            size=(700, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.settings_manager = settings_manager
        self.theme_manager = get_theme_manager()
        
        # Center on parent
        self.CenterOnParent()
        
        # Apply theme colors to the dialog itself
        self.theme = self.theme_manager.get_current_theme()
        self.SetBackgroundColour(wx.Colour(self.theme.bg_main))
        self.SetForegroundColour(wx.Colour(self.theme.fg_main))
        
        self._setup_ui()
        self._apply_current_theme()
        self._load_current_settings()
        
    def _setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Use Listbook for left-side navigation
        self.listbook = wx.Listbook(self, wx.ID_ANY, style=wx.LB_LEFT)
        self.listbook.SetBackgroundColour(wx.Colour(self.theme.bg_panel))
        self.listbook.GetListView().SetBackgroundColour(wx.Colour(self.theme.bg_list))
        self.listbook.GetListView().SetForegroundColour(wx.Colour(self.theme.fg_main))

        # 1. Language Panel
        self.lang_panel = self._create_lang_panel(self.listbook)
        self.listbook.AddPage(self.lang_panel, _("Language"))

        # 2. Theme Panel
        self.theme_panel = self._create_theme_panel(self.listbook)
        self.listbook.AddPage(self.theme_panel, _("Theme"))

        # 3. User Panel
        self.user_panel = self._create_user_panel(self.listbook)
        self.listbook.AddPage(self.user_panel, _("User Settings"))

        # 4. Annotation Panel
        self.anno_panel = self._create_anno_panel(self.listbook)
        self.listbook.AddPage(self.anno_panel, _("Annotation"))

        # 5. AI Panel
        self.ai_panel = self._create_ai_panel(self.listbook)
        self.listbook.AddPage(self.ai_panel, _("AI Annotation"))

        # Fix sidebar width — SetMinSize reserves space in the sizer;
        # SetColumnWidth prevents the ListCtrl from collapsing the column.
        # On macOS and Linux, the column isn't ready until the dialog is actually shown
        # (EVT_SHOW), so we defer it there. On Windows it can be set
        # immediately after AddPage.
        lv = self.listbook.GetListView()
        lv.SetMinSize((160, -1))
        if platform.system() == 'Windows':
            try:
                lv.SetColumnWidth(0, 155)
            except Exception:
                pass
        else:
            self.Bind(wx.EVT_SHOW, self._on_first_show)
        
        main_sizer.Add(self.listbook, 1, wx.EXPAND | wx.ALL, 10)
        
        # Buttons — on macOS, native NSButton with standard IDs ignores
        # SetForegroundColour/SetBackgroundColour entirely, so we use
        # GenButton (pure-Python drawn) there.  On Windows/Linux wx.Button
        # already responds correctly to colour changes.
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_ok = _BTN_CLS(self, wx.ID_OK, _("OK"))
        self.btn_cancel = _BTN_CLS(self, wx.ID_CANCEL, _("Cancel"))
        self.btn_apply = _BTN_CLS(self, wx.ID_APPLY, _("Apply"))
        
        btn_sizer.Add(self.btn_apply, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_ok, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.btn_cancel, 0)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        
        # Events
        self.btn_apply.Bind(wx.EVT_BUTTON, self._on_apply)
        self.btn_ok.Bind(wx.EVT_BUTTON, self._on_ok)
        
    def _on_first_show(self, event):
        """macOS/Linux: finalize UI after the dialog is first rendered.

        On macOS, native controls (NSButton, NSPopUpButton, etc.) override
        colours set during __init__ when they first paint.  EVT_SHOW fires
        after the native render pass, so re-applying the theme here ensures
        our custom colours win.  The Listbook column also isn't ready until
        this point on macOS and Linux, so we set its width here too.
        """
        event.Skip()
        if not event.IsShown():
            return
        self.Unbind(wx.EVT_SHOW)
        try:
            self.listbook.GetListView().SetColumnWidth(0, 155)
        except Exception:
            pass  # Defensive — column may still be absent in edge cases
        # Re-apply theme so native controls pick up our custom colours.
        self._apply_current_theme()

    def refresh_translations(self):
        """Update all labels in the dialog with current language."""
        self.SetTitle(_("Settings"))
        
        # Listbook page titles
        self.listbook.SetPageText(0, _("Language"))
        self.listbook.SetPageText(1, _("Theme"))
        self.listbook.SetPageText(2, _("User Settings"))
        self.listbook.SetPageText(3, _("Annotation"))
        self.listbook.SetPageText(4, _("AI Annotation"))
        
        # Panel StaticBoxes
        self.lang_box.GetStaticBox().SetLabel(_("Language Selection"))
        self.theme_box.GetStaticBox().SetLabel(_("UI Appearance"))
        self.user_box.GetStaticBox().SetLabel(_("Annotator Information"))
        self.anno_box.GetStaticBox().SetLabel(_("LabelMe Storage Format"))
        self.attr_box.GetStaticBox().SetLabel(_("Attribute Panel"))
        self.ai_box.GetStaticBox().SetLabel(_("AI Assisted Labeling Settings"))
        
        # Individual Labels/Checkboxes
        self.lbl_select_lang.SetLabel(_("Select Interface Language:"))
        self.lbl_color_theme.SetLabel(_("Color Theme:"))
        self.lbl_font_size.SetLabel(_("Font Size:"))
        
        self.chk_save_user_info.SetLabel(_("Enable User Information (Save to JSON)"))
        self.lbl_user_name.SetLabel(_("Name:"))
        self.lbl_user_quality.SetLabel(_("Quality Score (0-100):"))
        self.lbl_user_note.SetLabel(_("Note: User info will only be added to JSON when enabled above."))
        
        self.chk_embed.SetLabel(_("Embed Image Data (Base64) in JSON"))
        self.lbl_embed_note.SetLabel(_("Note: Enabling this will significantly increase JSON file size."))
        self.chk_attr_panel.SetLabel(_("Enable Attribute Panel (show below annotation list)"))
        self.lbl_default_flags.SetLabel(_("Default Flags:"))
        self.lbl_flags_note.SetLabel(_("Comma-separated flag names, e.g.: occluded, truncated, difficult"))
        
        self.lbl_ai_model_dir.SetLabel(_("AI Model Directory:"))
        self.chk_continuous.SetLabel(_("Enable Continuous Inference (Real-time)"))
        self.lbl_ai_interval.SetLabel(_("Inference Interval (ms):"))
        self.chk_auto_simplify.SetLabel(_("Auto-simplify Polygon (0.004 Tolerance)"))
        self.chk_denoise.SetLabel(_("Denoise Mask (Filter small fragments)"))
        
        # Buttons
        self.btn_ok.SetLabel(_("OK"))
        self.btn_cancel.SetLabel(_("Cancel"))
        self.btn_apply.SetLabel(_("Apply"))
        
        # Update language selector choices
        i18n_mgr = get_i18n_manager()
        i18n_mgr.refresh_discovery()
        languages = i18n_mgr.get_language_list()
        
        self.lang_choices = []
        self.lang_codes = []
        for code, (eng, local) in languages.items():
            self.lang_codes.append(code)
            self.lang_choices.append(f"{local} ({eng})")
            
        current_lang = self.settings_manager.get("language", "en")
        self.lang_selector.SetItems(self.lang_choices)
        if current_lang in self.lang_codes:
            self.lang_selector.SetSelection(self.lang_codes.index(current_lang))
            
        # Update theme choices (they might have translated names)
        all_themes = self.theme_manager.get_all_themes()
        self.theme_ids = list(all_themes.keys())
        self.theme_names = [_(name) for name in all_themes.values()]
        theme_sel_idx = self.theme_selector.GetSelection()
        self.theme_selector.SetItems(self.theme_names)
        self.theme_selector.SetSelection(theme_sel_idx)
        
        # Re-layout because labels might have changed size
        self.Layout()
        # Force repaint — necessary because a paint event from the language-change
        # MessageBox (inside _on_settings_applied) may have redrawn the dialog with
        # old label values just before refresh_translations() was called.
        self.listbook.GetListView().Refresh()
        self.Refresh()
        self.Update()

    def _create_lang_panel(self, parent):
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(self.theme.bg_main))
        self.lang_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("Language Selection"))
        
        from .i18n import get_i18n_manager
        i18n = get_i18n_manager()
        languages = i18n.get_language_list() # Returns dict {code: (name, local_name)}
        
        self.lang_choices = []
        self.lang_codes = []
        for code, (eng, local) in languages.items():
            self.lang_codes.append(code)
            self.lang_choices.append(f"{local} ({eng})")
            
        self.lang_selector = _CHOICE_CLS(panel, choices=self.lang_choices)
        self.lang_selector.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.lang_selector.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        
        self.lbl_select_lang = wx.StaticText(panel, label=_("Select Interface Language:"))
        self.lang_box.Add(self.lbl_select_lang, 0, wx.ALL, 5)
        self.lang_box.Add(self.lang_selector, 0, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(self.lang_box)
        return panel
        
    def _create_theme_panel(self, parent):
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(self.theme.bg_main))
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Theme section
        self.theme_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("UI Appearance"))
        
        all_themes = self.theme_manager.get_all_themes()
        self.theme_ids = list(all_themes.keys())
        self.theme_names = [_(name) for name in all_themes.values()]
        
        self.theme_selector = _CHOICE_CLS(panel, choices=self.theme_names)
        self.theme_selector.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.theme_selector.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        
        self.lbl_color_theme = wx.StaticText(panel, label=_("Color Theme:"))
        self.theme_box.Add(self.lbl_color_theme, 0, wx.ALL, 5)
        self.theme_box.Add(self.theme_selector, 0, wx.EXPAND | wx.ALL, 5)
        
        # Bind theme selection for live preview
        self.theme_selector.Bind(wx.EVT_CHOICE, self._on_theme_changed)
        
        # Font size section
        font_box = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_font_size = wx.StaticText(panel, label=_("Font Size:"))
        font_box.Add(self.lbl_font_size, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.font_spinner = wx.SpinCtrl(panel, value="10", min=8, max=30)
        self.font_spinner.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.font_spinner.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        font_box.Add(self.font_spinner, 0, wx.ALL, 5)
        
        self.theme_box.Add(font_box, 0, wx.EXPAND)
        
        sizer.Add(self.theme_box, 0, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
        return panel
        
    def _create_user_panel(self, parent):
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(self.theme.bg_main))
        self.user_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("Annotator Information"))
        
        # Enable toggle
        self.chk_save_user_info = wx.CheckBox(panel, label=_("Enable User Information (Save to JSON)"))
        self.chk_save_user_info.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.user_box.Add(self.chk_save_user_info, 0, wx.ALL, 10)
        
        grid = wx.FlexGridSizer(2, 2, 10, 10)
        grid.AddGrowableCol(1)
        
        self.lbl_user_name = wx.StaticText(panel, label=_("Name:"))
        grid.Add(self.lbl_user_name, 0, wx.ALIGN_CENTER_VERTICAL)
        self.user_name = wx.TextCtrl(panel)
        self.user_name.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.user_name.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        grid.Add(self.user_name, 1, wx.EXPAND)
        
        self.lbl_user_quality = wx.StaticText(panel, label=_("Quality Score (0-100):"))
        grid.Add(self.lbl_user_quality, 0, wx.ALIGN_CENTER_VERTICAL)
        self.user_quality = wx.SpinCtrlDouble(panel, value="100.0", min=0.0, max=100.0, inc=0.1)
        self.user_quality.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.user_quality.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        grid.Add(self.user_quality, 0)
        
        self.user_box.Add(grid, 1, wx.EXPAND | wx.ALL, 10)
        
        self.lbl_user_note = wx.StaticText(panel, label=_("Note: User info will only be added to JSON when enabled above."))
        self.lbl_user_note.SetForegroundColour(wx.Colour(self.theme.fg_dim))
        self.lbl_user_note.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        self.user_box.Add(self.lbl_user_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        panel.SetSizer(self.user_box)
        return panel
        
    def _create_anno_panel(self, parent):
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(self.theme.bg_main))
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Storage format section
        self.anno_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("LabelMe Storage Format"))

        self.chk_embed = wx.CheckBox(panel, label=_("Embed Image Data (Base64) in JSON"))
        self.chk_embed.SetForegroundColour(wx.Colour(self.theme.fg_main))

        self.anno_box.Add(self.chk_embed, 0, wx.ALL, 10)

        self.lbl_embed_note = wx.StaticText(panel, label=_("Note: Enabling this will significantly increase JSON file size."))
        self.lbl_embed_note.SetForegroundColour(wx.Colour(self.theme.fg_dim))
        self.lbl_embed_note.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        self.anno_box.Add(self.lbl_embed_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        main_sizer.Add(self.anno_box, 0, wx.EXPAND | wx.ALL, 5)

        # Attribute Panel section
        self.attr_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("Attribute Panel"))

        self.chk_attr_panel = wx.CheckBox(panel, label=_("Enable Attribute Panel (show below annotation list)"))
        self.chk_attr_panel.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.attr_box.Add(self.chk_attr_panel, 0, wx.ALL, 10)

        flags_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_default_flags = wx.StaticText(panel, label=_("Default Flags:"))
        self.lbl_default_flags.SetForegroundColour(wx.Colour(self.theme.fg_main))
        flags_sizer.Add(self.lbl_default_flags, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.txt_default_flags = wx.TextCtrl(panel)
        self.txt_default_flags.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.txt_default_flags.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        flags_sizer.Add(self.txt_default_flags, 1, wx.EXPAND)
        self.attr_box.Add(flags_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.lbl_flags_note = wx.StaticText(panel, label=_("Comma-separated flag names, e.g.: occluded, truncated, difficult"))
        self.lbl_flags_note.SetForegroundColour(wx.Colour(self.theme.fg_dim))
        self.lbl_flags_note.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        self.attr_box.Add(self.lbl_flags_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        main_sizer.Add(self.attr_box, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)
        return panel
        
    def _create_ai_panel(self, parent):
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(self.theme.bg_main))
        self.ai_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("AI Assisted Labeling Settings"))
        
        # Model path
        self.lbl_ai_model_dir = wx.StaticText(panel, label=_("AI Model Directory:"))
        self.ai_box.Add(self.lbl_ai_model_dir, 0, wx.TOP | wx.LEFT, 10)
        self.ai_path_picker = wx.DirPickerCtrl(panel, style=wx.DIRP_DIR_MUST_EXIST | wx.DIRP_SMALL | wx.DIRP_USE_TEXTCTRL)
        txt_ctrl = self.ai_path_picker.GetTextCtrl()
        if txt_ctrl:
            txt_ctrl.SetForegroundColour(wx.Colour(self.theme.fg_main))
            txt_ctrl.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        self.ai_box.Add(self.ai_path_picker, 0, wx.EXPAND | wx.ALL, 10)
        
        # Continuous Inference
        self.chk_continuous = wx.CheckBox(panel, label=_("Enable Continuous Inference (Real-time)"))
        self.chk_continuous.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.ai_box.Add(self.chk_continuous, 0, wx.ALL, 10)
        
        # Throttle
        throttle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_ai_interval = wx.StaticText(panel, label=_("Inference Interval (ms):"))
        throttle_sizer.Add(self.lbl_ai_interval, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.ai_throttle = wx.SpinCtrl(panel, value="100", min=10, max=5000)
        self.ai_throttle.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.ai_throttle.SetBackgroundColour(wx.Colour(self.theme.bg_list))
        throttle_sizer.Add(self.ai_throttle, 0, wx.ALL, 5)
        self.ai_box.Add(throttle_sizer, 0, wx.LEFT, 5)
        
        # Options
        self.chk_auto_simplify = wx.CheckBox(panel, label=_("Auto-simplify Polygon (0.004 Tolerance)"))
        self.chk_auto_simplify.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.ai_box.Add(self.chk_auto_simplify, 0, wx.ALL, 10)
        
        self.chk_denoise = wx.CheckBox(panel, label=_("Denoise Mask (Filter small fragments)"))
        self.chk_denoise.SetForegroundColour(wx.Colour(self.theme.fg_main))
        self.ai_box.Add(self.chk_denoise, 0, wx.ALL, 10)
        
        panel.SetSizer(self.ai_box)
        return panel
        
    def _load_current_settings(self):
        """Load values from settings manager into UI."""
        # Language
        current_lang = self.settings_manager.get("language", "zh_TW")
        if current_lang in self.lang_codes:
            self.lang_selector.SetSelection(self.lang_codes.index(current_lang))
            
        # Theme
        current_theme = self.theme_manager.current_theme_name
        if current_theme in self.theme_ids:
            self.theme_selector.SetSelection(self.theme_ids.index(current_theme))
            
        # Font size (from current theme)
        self.font_spinner.SetValue(self.theme_manager.get_current_theme().font_size)
        
        # User
        self.user_name.SetValue(self.settings_manager.get("annotator_name", ""))
        self.user_quality.SetValue(self.settings_manager.get("annotator_quality", 100.0))
        self.chk_save_user_info.SetValue(self.settings_manager.get("save_user_info", True))
        
        # Annotation
        self.chk_embed.SetValue(self.settings_manager.get("embed_base64", False))
        self.chk_attr_panel.SetValue(self.settings_manager.get("enable_attribute_panel", False))
        default_flags = self.settings_manager.get("default_flags", ["occluded", "truncated", "difficult"])
        self.txt_default_flags.SetValue(", ".join(default_flags))
        
        # AI
        self.ai_path_picker.SetPath(self.settings_manager.get("ai_model_path", "models"))
        self.chk_continuous.SetValue(self.settings_manager.get("ai_continuous_inference", False))
        self.ai_throttle.SetValue(self.settings_manager.get("ai_inference_throttle_ms", 100))
        self.chk_auto_simplify.SetValue(self.settings_manager.get("ai_auto_simplify_polygon", True))
        self.chk_denoise.SetValue(self.settings_manager.get("ai_denoise_mask", True))
        
    def _on_apply(self, event):
        """Save settings and apply changes immediately."""
        # 1. Save language
        new_lang = self.lang_codes[self.lang_selector.GetSelection()]
        self.settings_manager.set("language", new_lang, save=False)
        
        # 2. Save Theme & Font
        new_theme_id = self.theme_ids[self.theme_selector.GetSelection()]
        new_font_size = self.font_spinner.GetValue()
        
        # Update theme manager memory structure before saving
        theme_obj = self.theme_manager.get_theme_colors(new_theme_id)
        if theme_obj:
            theme_obj.font_size = new_font_size
        self.theme_manager.set_theme(new_theme_id) # This calls save() which includes font_size
        
        # 3. Save User metadata
        self.settings_manager.set("annotator_name", self.user_name.GetValue(), save=False)
        self.settings_manager.set("annotator_quality", self.user_quality.GetValue(), save=False)
        self.settings_manager.set("save_user_info", self.chk_save_user_info.GetValue(), save=False)
        
        # 4. Save Annotation settings
        self.settings_manager.set("embed_base64", self.chk_embed.GetValue(), save=False)
        self.settings_manager.set("enable_attribute_panel", self.chk_attr_panel.GetValue(), save=False)
        flags_text = self.txt_default_flags.GetValue().strip()
        flags_list = [f.strip() for f in flags_text.split(",") if f.strip()]
        self.settings_manager.set("default_flags", flags_list, save=False)
        
        # 5. Save AI path
        self.settings_manager.set("ai_model_path", self.ai_path_picker.GetPath(), save=False)
        self.settings_manager.set("ai_continuous_inference", self.chk_continuous.GetValue(), save=False)
        self.settings_manager.set("ai_inference_throttle_ms", self.ai_throttle.GetValue(), save=False)
        self.settings_manager.set("ai_auto_simplify_polygon", self.chk_auto_simplify.GetValue(), save=False)
        self.settings_manager.set("ai_denoise_mask", self.chk_denoise.GetValue(), save=False)
        
        # Final save for settings_manager
        self.settings_manager.save()
        
        # Notify parent to refresh if needed (MainWindow will handle this)
        if hasattr(self.GetParent(), "_on_settings_applied"):
            self.GetParent()._on_settings_applied(new_lang, new_theme_id)
            
        # Refresh own labels immediately
        self.refresh_translations()

    def get_settings(self) -> Dict[str, Any]:
        """Return dict of current UI settings (for direct OK handling)."""
        return {
            "language": self.lang_codes[self.lang_selector.GetSelection()],
            "theme": self.theme_ids[self.theme_selector.GetSelection()],
            "font_size": self.font_spinner.GetValue(),
            "annotator_name": self.user_name.GetValue(),
            "annotator_quality": self.user_quality.GetValue(),
            "save_user_info": self.chk_save_user_info.GetValue(),
            "embed_base64": self.chk_embed.GetValue(),
            "enable_attribute_panel": self.chk_attr_panel.GetValue(),
            "default_flags": [f.strip() for f in self.txt_default_flags.GetValue().split(",") if f.strip()],
            "ai_model_path": self.ai_path_picker.GetPath(),
            "ai_continuous_inference": self.chk_continuous.GetValue(),
            "ai_inference_throttle_ms": self.ai_throttle.GetValue(),
            "ai_auto_simplify_polygon": self.chk_auto_simplify.GetValue(),
            "ai_denoise_mask": self.chk_denoise.GetValue()
        }

    def _on_ok(self, event):
        """Apply changes and close dialog."""
        self._on_apply(event)
        self.EndModal(wx.ID_OK)

    def _on_theme_changed(self, event):
        """Handle theme change for live preview."""
        theme_id = self.theme_ids[self.theme_selector.GetSelection()]
        self.theme_manager.set_theme(theme_id)
        
        # Apply theme to self
        self._apply_current_theme()
        
        # Notify MainWindow to apply theme globally
        if hasattr(self.GetParent(), "_apply_theme"):
            theme_colors = self.theme_manager.get_current_theme()
            self.GetParent()._apply_theme(theme_colors)

    def _apply_current_theme(self):
        """Apply current theme colors to SettingsDialog components."""
        self.theme = self.theme_manager.get_current_theme()
        bg_color = wx.Colour(self.theme.bg_main)
        fg_color = wx.Colour(self.theme.fg_main)
        bg_list = wx.Colour(self.theme.bg_list)
        bg_panel = wx.Colour(self.theme.bg_panel)
        
        self.SetBackgroundColour(bg_color)
        self.SetForegroundColour(fg_color)
        
        # Update panels
        for panel in [self.lang_panel, self.theme_panel, self.user_panel, self.anno_panel, self.ai_panel]:
            panel.SetBackgroundColour(bg_color)
            for child in panel.GetChildren():
                if isinstance(child, (wx.StaticText, wx.CheckBox, wx.StaticBox)):
                    child.SetForegroundColour(fg_color)
                    child.Refresh()
                elif isinstance(child, (wx.Choice, wx.ComboBox, _ThemedChoice, wx.SpinCtrl, wx.SpinCtrlDouble, wx.TextCtrl)):
                    child.SetBackgroundColour(bg_list)
                    child.SetForegroundColour(fg_color)
                    child.Refresh()
            panel.Refresh()
            
        # Update Listbook
        self.listbook.SetBackgroundColour(bg_panel)
        lv = self.listbook.GetListView()
        lv.SetBackgroundColour(bg_list)
        lv.SetForegroundColour(fg_color)

        # Update bottom buttons (direct children of dialog, not inside any panel)
        for btn in [self.btn_ok, self.btn_cancel, self.btn_apply]:
            btn.SetForegroundColour(fg_color)
            btn.SetBackgroundColour(wx.Colour(self.theme.bg_panel))
            btn.Refresh()

        self.Refresh()
