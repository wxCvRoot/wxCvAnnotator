#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Left Annotation Toolbar - Designed based on LabelMe mode
Contains all annotation tool buttons and operation controls.
"""

import wx
import wx.lib.buttons as wxbuttons
import platform
from typing import Optional, Callable, List, Dict, Tuple
from .i18n import _

# On macOS, native NSButton ignores SetForegroundColour/SetBackgroundColour.
# Use GenButton (pure-Python drawn) there; keep native wx.Button elsewhere.
_BTN_CLS = wxbuttons.GenButton if platform.system() == 'Darwin' else wx.Button


class AnnotationToolbar(wx.Panel):
    """Left Annotation Toolbar"""
    
    def __init__(self, parent):
        """Initialize toolbar"""
        super().__init__(parent, wx.ID_ANY)
        
        # Theme state
        self.theme_colors = None
        
        # Tool state
        self.current_tool = "rectangle"
        self.selected_buttons = {}  # Record selected buttons
        
        # Callbacks
        self.on_tool_changed: Optional[Callable] = None
        self.on_operation: Optional[Callable] = None
        
        # Tool configuration
        self.TOOLS_CONFIG = {
            "select": {"label": _("🎯 Select"), "tooltip": _("Select or edit annotations (S)"), "id": "sel"},
            "polygon": {"label": _("🔷 Polygon"), "tooltip": _("Create polygon annotation (P)"), "id": "poly"},
            "rotated_rect": {"label": _("📐 Rotated Rect"), "tooltip": _("Create rotated rectangle (R)"), "id": "rotated_rect"},
            "rectangle": {"label": _("⬛ Rectangle"), "tooltip": _("Create rectangle annotation"), "id": "rect"},
            "line": {"label": _("📏 Line"), "tooltip": _("Create line annotation (L)"), "id": "line"},
            "circle": {"label": _("⭕ Circle"), "tooltip": _("Create circle annotation"), "id": "circ"},
            "annulus": {"label": _("🍩 Annulus"), "tooltip": _("Create annulus annotation"), "id": "annu"},
        }
        
        self.OPERATIONS_CONFIG = {
            "add": {"label": _("➕ Add"), "tooltip": _("Add object to list (Enter)"), "id": "add"},
            "cancel": {"label": _("🚫 Cancel"), "tooltip": _("Cancel current drawing (Esc)"), "id": "cancel"},
            "undo": {"label": _("↩️ Undo"), "tooltip": _("Undo operation (Ctrl+Z)"), "id": "undo"},
            "redo": {"label": _("↪️ Redo"), "tooltip": _("Redo operation (Ctrl+Y)"), "id": "redo"},
        }
        
        self.VIEW_CONFIG = {
            "zoom_in": {"label": _("🔍 Zoom In"), "tooltip": _("Zoom in view"), "id": "z_in"},
            "zoom_out": {"label": _("🔎 Zoom Out"), "tooltip": _("Zoom out view"), "id": "z_out"},
            "fit_view": {"label": _("🖼️ Fit View"), "tooltip": _("Fit image to window"), "id": "z_fit"},
        }
        
        self.AI_CONFIG = {
            "ai_polygon": {"label": _("🤖 AI Polygon"), "tooltip": _("AI-Assisted Polygon (SAM)"), "id": "ai_poly"},
            "ai_mask": {"label": _("🎭 AI Mask"), "tooltip": _("AI-Assisted Pixel Mask (SAM)"), "id": "ai_mask"},
        }
        
        self.AI_MODELS = [
            "Sam(speed)",
            "Sam(balanced)",
            "Sam(accuracy)",
            "Sam2(speed)",
            "Sam2(balanced)",
            "Sam2(accuracy)",
            "EfficientSAM (speed)",
            "EfficientSAM (accuracy)"
        ]
        
        # Setup UI
        self._setup_ui()
        self._bind_events()
        
        # Set default tool
        self._set_default_tool()
    
    def _setup_ui(self):
        """Setup UI layout"""
        # Main layout
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(main_sizer)
        
        # Default background (will be overridden by theme)
        self.SetBackgroundColour(wx.Colour(45, 45, 48))
        
        # Title
        self.title_text = wx.StaticText(self, wx.ID_ANY, _("Annotation Tools"))
        self.title_text.SetForegroundColour(wx.WHITE)
        title_font = self.title_text.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title_text.SetFont(title_font)
        main_sizer.Add(self.title_text, 0, wx.ALL | wx.CENTER, 5)
        
        # Divider
        self.header_line = wx.StaticLine(self, wx.ID_ANY)
        self.header_line.SetSize(wx.Size(-1, 2))
        self.header_line.SetBackgroundColour(wx.Colour(80, 80, 80))
        main_sizer.Add(self.header_line, 0, wx.EXPAND | wx.ALL, 5)
        
        # Create categories
        self._create_tool_buttons(main_sizer)
        self._create_ai_buttons(main_sizer)
        self._create_operation_buttons(main_sizer)
        self._create_view_buttons(main_sizer)
        
        # Spacer
        main_sizer.AddStretchSpacer(1)
        
        # Status display
        self.status_panel = wx.Panel(self, wx.ID_ANY)
        status_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.current_tool_label = wx.StaticText(
            self.status_panel, wx.ID_ANY, _("Tool: Select"),
            style=wx.ST_ELLIPSIZE_END
        )
        self.current_tool_label.SetForegroundColour(wx.Colour(180, 180, 180))
        status_sizer.Add(self.current_tool_label, 0, wx.ALL | wx.EXPAND, 2)
        
        self.hint_label = wx.StaticText(
            self.status_panel, wx.ID_ANY, _("Hint: Right-click for options"),
            style=wx.ST_ELLIPSIZE_END
        )
        self.hint_label.SetForegroundColour(wx.Colour(120, 120, 120))
        self.hint_label.SetFont(self.hint_label.GetFont().MakeSmaller())
        status_sizer.Add(self.hint_label, 0, wx.ALL | wx.EXPAND, 2)
        
        self.status_panel.SetSizer(status_sizer)
        main_sizer.Add(self.status_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Panel size
        self.SetMinSize(wx.Size(150, -1))
    
    def _create_tool_buttons(self, parent_sizer):
        """Create tool buttons"""
        # Header
        self.tools_title = wx.StaticText(self, wx.ID_ANY, _("Tools"))
        self.tools_title.SetForegroundColour(wx.Colour(200, 200, 200))
        tools_title_font = self.tools_title.GetFont()
        tools_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.tools_title.SetFont(tools_title_font)
        parent_sizer.Add(self.tools_title, 0, wx.ALL | wx.CENTER, 3)
        
        # Container
        tools_panel = wx.Panel(self, wx.ID_ANY)
        tools_sizer = wx.BoxSizer(wx.VERTICAL)
        tools_panel.SetSizer(tools_sizer)
        
        for tool_key, config in self.TOOLS_CONFIG.items():
            button = self._create_tool_button(
                tools_panel, config["label"], config["tooltip"], tool_key
            )
            tools_sizer.Add(button, 0, wx.EXPAND | wx.ALL, 1)
            self.selected_buttons[tool_key] = button
        
        parent_sizer.Add(tools_panel, 0, wx.EXPAND | wx.ALL, 2)
    
    def _create_ai_buttons(self, parent_sizer):
        """Create AI-assisted tool buttons"""
        # Divider
        self.ai_line = wx.StaticLine(self, wx.ID_ANY)
        self.ai_line.SetSize(wx.Size(-1, 2))
        self.ai_line.SetBackgroundColour(wx.Colour(80, 80, 80))
        parent_sizer.Add(self.ai_line, 0, wx.EXPAND | wx.ALL, 5)
        
        # Header
        self.ai_title = wx.StaticText(self, wx.ID_ANY, _("AI Assist"))
        self.ai_title.SetForegroundColour(wx.Colour(200, 200, 200))
        ai_title_font = self.ai_title.GetFont()
        ai_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.ai_title.SetFont(ai_title_font)
        parent_sizer.Add(self.ai_title, 0, wx.ALL | wx.CENTER, 3)
        
        # Container
        ai_panel = wx.Panel(self, wx.ID_ANY)
        ai_sizer = wx.BoxSizer(wx.VERTICAL)
        ai_panel.SetSizer(ai_sizer)
        
        for ai_key, config in self.AI_CONFIG.items():
            button = self._create_tool_button(
                ai_panel, config["label"], config["tooltip"], ai_key
            )
            ai_sizer.Add(button, 0, wx.EXPAND | wx.ALL, 1)
            self.selected_buttons[ai_key] = button
        
        # Model Selector (ComboBox)
        model_label = wx.StaticText(ai_panel, wx.ID_ANY, _("Model:"))
        model_label.SetForegroundColour(wx.Colour(180, 180, 180))
        model_font = model_label.GetFont()
        model_font.SetPointSize(max(8, model_font.GetPointSize() - 1))
        model_label.SetFont(model_font)
        ai_sizer.Add(model_label, 0, wx.LEFT | wx.TOP, 5)
        
        self.ai_model_selector = wx.ComboBox(
            ai_panel, wx.ID_ANY, 
            choices=self.AI_MODELS,
            style=wx.CB_READONLY
        )
        self.ai_model_selector.SetSelection(0)
        self.ai_model_selector.Enable(False) # Initial state disabled
        ai_sizer.Add(self.ai_model_selector, 0, wx.EXPAND | wx.ALL, 5)
        
        parent_sizer.Add(ai_panel, 0, wx.EXPAND | wx.ALL, 2)

    def _create_operation_buttons(self, parent_sizer):
        """Create operation buttons"""
        # Divider
        self.ops_line = wx.StaticLine(self, wx.ID_ANY)
        self.ops_line.SetSize(wx.Size(-1, 2))
        self.ops_line.SetBackgroundColour(wx.Colour(80, 80, 80))
        parent_sizer.Add(self.ops_line, 0, wx.EXPAND | wx.ALL, 5)
        
        # Header
        self.ops_title = wx.StaticText(self, wx.ID_ANY, _("Actions"))
        self.ops_title.SetForegroundColour(wx.Colour(200, 200, 200))
        ops_title_font = self.ops_title.GetFont()
        ops_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.ops_title.SetFont(ops_title_font)
        parent_sizer.Add(self.ops_title, 0, wx.ALL | wx.CENTER, 3)
        
        # Container
        ops_panel = wx.Panel(self, wx.ID_ANY)
        ops_sizer = wx.BoxSizer(wx.VERTICAL)
        ops_panel.SetSizer(ops_sizer)
        
        for op_key, config in self.OPERATIONS_CONFIG.items():
            button = _BTN_CLS(ops_panel, wx.ID_ANY, config["label"])
            button.SetToolTip(config["tooltip"])
            self._style_button(button, op_key)
            
            button.Bind(wx.EVT_BUTTON, lambda e, key=op_key: self._on_operation_clicked(key))
            ops_sizer.Add(button, 0, wx.EXPAND | wx.ALL, 1)
            self.selected_buttons[op_key] = button
        
        parent_sizer.Add(ops_panel, 0, wx.EXPAND | wx.ALL, 2)

    def _create_view_buttons(self, parent_sizer):
        """Create view control buttons (Zoom, etc.)"""
        # Divider
        self.view_line = wx.StaticLine(self, wx.ID_ANY)
        self.view_line.SetSize(wx.Size(-1, 2))
        self.view_line.SetBackgroundColour(wx.Colour(80, 80, 80))
        parent_sizer.Add(self.view_line, 0, wx.EXPAND | wx.ALL, 5)
        
        # Header
        self.view_title = wx.StaticText(self, wx.ID_ANY, _("View"))
        self.view_title.SetForegroundColour(wx.Colour(200, 200, 200))
        view_title_font = self.view_title.GetFont()
        view_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.view_title.SetFont(view_title_font)
        parent_sizer.Add(self.view_title, 0, wx.ALL | wx.CENTER, 3)
        
        # Container
        view_panel = wx.Panel(self, wx.ID_ANY)
        view_sizer = wx.BoxSizer(wx.VERTICAL)
        view_panel.SetSizer(view_sizer)
        
        for view_key, config in self.VIEW_CONFIG.items():
            button = _BTN_CLS(view_panel, wx.ID_ANY, config["label"])
            button.SetToolTip(config["tooltip"])
            self._style_button(button)
            
            button.Bind(wx.EVT_BUTTON, lambda e, key=view_key: self._on_operation_clicked(key))
            view_sizer.Add(button, 0, wx.EXPAND | wx.ALL, 1)
            self.selected_buttons[view_key] = button
        
        parent_sizer.Add(view_panel, 0, wx.EXPAND | wx.ALL, 2)
    
    def _create_tool_button(self, parent, label: str, tooltip: str, tool_key: str):
        """Create single tool button"""
        button = _BTN_CLS(parent, wx.ID_ANY, label)
        button.SetToolTip(tooltip)
        self._style_tool_button(button)
        button.Bind(wx.EVT_BUTTON, lambda e, key=tool_key: self._on_tool_clicked(key))
        button.Bind(wx.EVT_CONTEXT_MENU, lambda e, key=tool_key: self._show_context_menu(e, key))
        return button
    
    def _style_button(self, button: wx.Button, key: str = ""):
        """Set button style based on theme"""
        if not self.theme_colors:
            # Fallback for initialization before theme is applied
            if key == "add":
                button.SetBackgroundColour(wx.Colour(0, 122, 204))
                button.SetForegroundColour(wx.WHITE)
            else:
                button.SetBackgroundColour(wx.Colour(60, 60, 63))
                button.SetForegroundColour(wx.Colour(230, 230, 230))
        else:
            if key == "add":
                button.SetBackgroundColour(wx.Colour(self.theme_colors.accent))
                button.SetForegroundColour(wx.WHITE)
            else:
                button.SetBackgroundColour(wx.Colour(self.theme_colors.bg_list))
                button.SetForegroundColour(wx.Colour(self.theme_colors.fg_main))
        
        if self.theme_colors and hasattr(self.theme_colors, 'font_size'):
            font_size = self.theme_colors.font_size
        else:
            font_size = 9 # Start small if no theme loaded
            
        font = button.GetFont()
        font.SetPointSize(font_size)
        button.SetFont(font)
    
    def _style_tool_button(self, button: wx.Button):
        """Set tool button style"""
        self._style_button(button)
    
    def _bind_events(self):
        """Bind events"""
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_RIGHT_DOWN, self._on_right_down)
        
        # AI Model selector event
        self.ai_model_selector.Bind(wx.EVT_COMBOBOX, self._on_ai_model_changed)
    
    def _on_ai_model_changed(self, event):
        """Handle AI model selection change"""
        model = self.ai_model_selector.GetStringSelection()
        print(f"🤖 AI Model changed: {model}")
        # Note: In a real implementation, this might trigger pre-loading
    
    def _on_tool_clicked(self, tool_key: str):
        """Handle tool button click"""
        print(f"Tool button clicked: {tool_key}")
        
        self.current_tool = tool_key
        self._update_tool_button_states()
        
        # Enable/Disable AI Model Selector based on tool
        is_ai = tool_key.startswith("ai_")
        self.ai_model_selector.Enable(is_ai)
        
        if self.on_tool_changed:
            self.on_tool_changed(tool_key)
        
        self._update_status_display()
    
    def _on_operation_clicked(self, operation_key: str):
        """Handle operation button click"""
        print(f"Operation button clicked: {operation_key}")
        
        if self.on_operation:
            self.on_operation(operation_key)
        
        self._update_status_display()
    
    def _on_key_down(self, event):
        """Handle keyboard shortcuts"""
        # If focus is on a TextCtrl, let it handle typing normally
        focused = wx.Window.FindFocus()
        if isinstance(focused, wx.TextCtrl):
            event.Skip()
            return

        key_code = event.GetKeyCode()
        modifiers = event.GetModifiers()

        tool_shortcuts = {
            ord('S'): "select",
            ord('P'): "polygon",
            ord('R'): "rotated_rect",
            ord('L'): "line",
        }
        
        if key_code in tool_shortcuts:
            self._on_tool_clicked(tool_shortcuts[key_code])
        elif key_code == ord('Z') and modifiers == wx.MOD_CONTROL:
            self._on_operation_clicked("undo")
        elif key_code == ord('Y') and modifiers == wx.MOD_CONTROL:
            self._on_operation_clicked("redo")
        elif key_code == wx.WXK_RETURN:
            self._on_operation_clicked("add")
        elif key_code == wx.WXK_ESCAPE:
            self._on_operation_clicked("cancel")
        elif key_code == wx.WXK_DELETE:
            self._on_operation_clicked("delete")
        
        event.Skip()
    
    def _on_left_down(self, event):
        event.Skip()
    
    def _on_right_down(self, event):
        menu = self._create_context_menu()
        self.PopupMenu(menu)
        menu.Destroy()
        event.Skip()
    
    def _show_context_menu(self, event, tool_key: str):
        """Show tool-specific context menu"""
        menu = wx.Menu()
        
        if tool_key == "rectangle":
            menu.Append(wx.ID_ANY, "Square Mode")
            menu.Append(wx.ID_ANY, "Rotation Mode")
        elif tool_key == "polygon":
            menu.Append(wx.ID_ANY, "Add Point")
            menu.Append(wx.ID_ANY, "Finish Polygon")
            menu.Append(wx.ID_ANY, "Cancel Polygon")
        elif tool_key == "select":
            menu.Append(wx.ID_ANY, "Multi-select Mode")
            menu.Append(wx.ID_ANY, "Box-select Mode")
        
        menu.AppendSeparator()
        menu.Append(wx.ID_ANY, _("Tool Help"))
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def _create_context_menu(self):
        """Create global context menu"""
        menu = wx.Menu()
        menu.Append(wx.ID_ANY, _("Toolbar Settings"))
        menu.Append(wx.ID_ANY, _("Hotkey Help"))
        menu.Append(wx.ID_ANY, _("About Annotation Tools"))
        return menu
    
    def _update_tool_button_states(self):
        """Update button visual states"""
        for tool_key, button in self.selected_buttons.items():
            if tool_key in self.TOOLS_CONFIG:
                self._style_tool_button(button)
                if tool_key == self.current_tool:
                    if self.theme_colors:
                        button.SetBackgroundColour(wx.Colour(self.theme_colors.bg_item_hover))
                    else:
                        button.SetBackgroundColour(wx.Colour(80, 80, 120))  # Selection color
                    button.SetForegroundColour(wx.WHITE)
    
    def _set_default_tool(self):
        self._on_tool_clicked("select")
    
    def _update_status_display(self):
        """Update status/hint text"""
        tool_display_names = {
            "select": _("Select/Edit"),
            "polygon": _("Polygon"),
            "rotated_rect": _("Rotated Rect"),
            "rectangle": _("Rectangle"),
            "line": _("Line"),
            "circle": _("Circle"),
            "annulus": _("Annulus"),
        }
        
        tool_name = tool_display_names.get(self.current_tool, self.current_tool)
        self.current_tool_label.SetLabel(_("Tool: {}").format(tool_name))
        
        hints = {
            "select": _("Hint: Click to select/edit an annotation"),
            "polygon": _("Hint: Click to add vertex, double-click or right-click to finish"),
            "rotated_rect": _("Hint: Drag to create rotated rectangle"),
            "rectangle": _("Hint: Drag to create standard rectangle"),
            "line": _("Hint: Drag to create line"),
            "circle": _("Hint: Drag to create circle"),
            "annulus": _("Hint: Drag to create annulus"),
        }
        
        hint = hints.get(self.current_tool, _("Hint: Right-click for options"))
        self.hint_label.SetLabel(hint)
        self.Refresh()

    def apply_theme(self, theme_colors):
        """Apply theme to toolbar"""
        self.theme_colors = theme_colors
        
        bg_panel = wx.Colour(theme_colors.bg_panel)
        fg_main = wx.Colour(theme_colors.fg_main)
        fg_dim = wx.Colour(theme_colors.fg_dim)
        divider = wx.Colour(theme_colors.divider)
        
        self.SetBackgroundColour(bg_panel)
        self.title_text.SetForegroundColour(fg_main)
        self.header_line.SetBackgroundColour(divider)
        self.ai_line.SetBackgroundColour(divider)
        self.ops_line.SetBackgroundColour(divider)
        self.view_line.SetBackgroundColour(divider)
        
        self.tools_title.SetForegroundColour(fg_dim)
        self.ai_title.SetForegroundColour(fg_dim)
        self.ops_title.SetForegroundColour(fg_dim)
        self.view_title.SetForegroundColour(fg_dim)
        
        self.status_panel.SetBackgroundColour(bg_panel)
        self.current_tool_label.SetForegroundColour(fg_main)
        self.hint_label.SetForegroundColour(fg_dim)
        
        # [REQ-013] Apply Font Sizes
        font_size = getattr(theme_colors, 'font_size', 10)
        
        # Titles (Bold + Larger?)
        # Let's keep titles slightly larger or bold
        title_font = self.title_text.GetFont()
        title_font.SetPointSize(font_size + 2) 
        self.title_text.SetFont(title_font)
        
        # Section Headers
        header_font = self.tools_title.GetFont()
        header_font.SetPointSize(font_size)
        self.tools_title.SetFont(header_font)
        self.ai_title.SetFont(header_font)
        self.ops_title.SetFont(header_font)
        self.view_title.SetFont(header_font)
        
        # User might want button text to scale too
        # This is handled by _style_button, so we just iterate
        
        # Update all buttons
        for key, button in self.selected_buttons.items():
            if key in self.OPERATIONS_CONFIG:
                self._style_button(button, key)
            else:
                self._style_button(button)
                
        # Re-apply tool selection style
        self._update_tool_button_states()
        
        self.Refresh()
        self.Layout()
        self.Parent.Layout() # Request parent layout update
    
    # Public API
    
    def set_current_tool(self, tool_key: str):
        if tool_key in self.TOOLS_CONFIG:
            self._on_tool_clicked(tool_key)
    
    def get_current_tool(self) -> str:
        return self.current_tool
    
    def enable_tool(self, tool_key: str, enabled: bool = True):
        if tool_key in self.selected_buttons:
            self.selected_buttons[tool_key].Enable(enabled)
            
    def enable_all_tools(self, enabled: bool = True):
        """Enable or disable all tool buttons (Tools + AI)"""
        for tool_key in list(self.TOOLS_CONFIG.keys()) + list(self.AI_CONFIG.keys()):
            if tool_key in self.selected_buttons:
                self.selected_buttons[tool_key].Enable(enabled)
            
    def enable_operation(self, op_key: str, enabled: bool = True):
        """Enable or disable operation button"""
        if op_key in self.selected_buttons:
            self.selected_buttons[op_key].Enable(enabled)
    
    def enable_ai_section(self, enabled: bool = True):
        """Enable or disable all AI-related buttons and selectors"""
        for ai_key in self.AI_CONFIG:
            if ai_key in self.selected_buttons:
                self.selected_buttons[ai_key].Enable(enabled)
        
        if hasattr(self, 'ai_model_selector'):
            self.ai_model_selector.Enable(enabled and self.current_tool.startswith("ai_"))
            # Prevent users from seeing AI models if AI is disabled
            if not enabled:
                self.ai_model_selector.Enable(False)
    
    def set_tool_changed_callback(self, callback: Callable):
        self.on_tool_changed = callback
    
    def set_operation_callback(self, callback: Callable):
        self.on_operation = callback

    def set_operation_button_mode(self, op_key: str, is_update: bool):
        """Switch button between Add and Update mode"""
        if op_key not in self.selected_buttons:
            return
            
        button = self.selected_buttons[op_key]
        if op_key == "add":
            if is_update:
                button.SetLabel(_("🔄 Update"))
                button.SetToolTip(_("Update selected object (Enter)"))
                button.SetBackgroundColour(wx.Colour(0, 150, 100))  # Greenish for update
            else:
                button.SetLabel(_("➕ Add"))
                button.SetToolTip(_("Add object to list (Enter)"))
                if self.theme_colors:
                    button.SetBackgroundColour(wx.Colour(self.theme_colors.accent))
                else:
                    button.SetBackgroundColour(wx.Colour(0, 122, 204))  # Blue accent
            button.Refresh()

    def refresh_translations(self):
        """Update all text labels and tooltips for the current language"""
        # 1. Update configurations
        self.TOOLS_CONFIG = {
            "select": {"label": _("🎯 Select"), "tooltip": _("Select or edit annotations (S)"), "id": "sel"},
            "polygon": {"label": _("🔷 Polygon"), "tooltip": _("Create polygon annotation (P)"), "id": "poly"},
            "rotated_rect": {"label": _("📐 Rotated Rect"), "tooltip": _("Create rotated rectangle (R)"), "id": "rotated_rect"},
            "rectangle": {"label": _("⬛ Rectangle"), "tooltip": _("Create rectangle annotation"), "id": "rect"},
            "line": {"label": _("📏 Line"), "tooltip": _("Create line annotation (L)"), "id": "line"},
            "circle": {"label": _("⭕ Circle"), "tooltip": _("Create circle annotation"), "id": "circ"},
            "annulus": {"label": _("🍩 Annulus"), "tooltip": _("Create annulus annotation"), "id": "annu"},
        }
        
        self.OPERATIONS_CONFIG = {
            "add": {"label": _("➕ Add"), "tooltip": _("Add object to list (Enter)"), "id": "add"},
            "cancel": {"label": _("🚫 Cancel"), "tooltip": _("Cancel current drawing (Esc)"), "id": "cancel"},
            "undo": {"label": _("↩️ Undo"), "tooltip": _("Undo operation (Ctrl+Z)"), "id": "undo"},
            "redo": {"label": _("↪️ Redo"), "tooltip": _("Redo operation (Ctrl+Y)"), "id": "redo"},
        }
        
        self.VIEW_CONFIG = {
            "zoom_in": {"label": _("🔍 Zoom In"), "tooltip": _("Zoom in view"), "id": "z_in"},
            "zoom_out": {"label": _("🔎 Zoom Out"), "tooltip": _("Zoom out view"), "id": "z_out"},
            "fit_view": {"label": _("🖼️ Fit View"), "tooltip": _("Fit image to window"), "id": "z_fit"},
        }
        
        self.AI_CONFIG = {
            "ai_polygon": {"label": _("🤖 AI Polygon"), "tooltip": _("AI-Assisted Polygon (SAM)"), "id": "ai_poly"},
            "ai_mask": {"label": _("🎭 AI Mask"), "tooltip": _("AI-Assisted Pixel Mask (SAM)"), "id": "ai_mask"},
        }
        
        # 2. Update panel titles and labels
        self.title_text.SetLabel(_("Annotation Tools"))
        self.tools_title.SetLabel(_("Tools"))
        self.ai_title.SetLabel(_("AI Assist"))
        self.ops_title.SetLabel(_("Actions"))
        self.view_title.SetLabel(_("View"))
        
        # 3. Update all buttons
        for key, button in self.selected_buttons.items():
            if key in self.TOOLS_CONFIG:
                cfg = self.TOOLS_CONFIG[key]
                button.SetLabel(cfg["label"])
                button.SetToolTip(cfg["tooltip"])
            elif key in self.OPERATIONS_CONFIG:
                cfg = self.OPERATIONS_CONFIG[key]
                button.SetLabel(cfg["label"])
                button.SetToolTip(cfg["tooltip"])
            elif key in self.AI_CONFIG:
                cfg = self.AI_CONFIG[key]
                button.SetLabel(cfg["label"])
                button.SetToolTip(cfg["tooltip"])
            elif key in self.VIEW_CONFIG:
                cfg = self.VIEW_CONFIG[key]
                button.SetLabel(cfg["label"])
                button.SetToolTip(cfg["tooltip"])
        
        # 4. Update status display
        self._update_status_display()
        
        # Ensure correct Add/Update mode on the button
        # We need to check the current mode from a source or state
        # For now, let's assume if it's currently showing Update, it stays Update
        # This is handled by main_window calling set_operation_button_mode if needed
        
        self.Layout()
        self.Refresh()

    def get_all_tools(self) -> List[str]:
        """Return all tool keys (Tools + AI)"""
        return list(self.TOOLS_CONFIG.keys()) + list(self.AI_CONFIG.keys())
