#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR-specific UI Components
Includes floating text editors and transcription widgets.
"""

import wx

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
