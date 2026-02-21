#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Theme Manager - Manages UI themes and color presets for wxCvAnnotator.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

@dataclass
class ThemeColors:
    name: str
    bg_main: str           # Main background
    bg_panel: str          # Sidebar/Panel background
    bg_list: str           # List control (File/Annotation) background
    bg_item_hover: str     # Item hover/selection
    fg_main: str           # Main text color
    fg_dim: str            # Dimmer text (hints, labels)
    accent: str            # Blue/Primary accent color
    divider: str           # Line/Divider color
    divider: str           # Line/Divider color
    canvas_bg: str         # Image display workspace background
    
    # [REQ-013] Typography
    font_size: int = 10    # Base font size

class ThemeManager:
    """Manages application UI themes inspired by VS Code."""
    
    THEMES = {
        "dark": ThemeColors(
            name=_("Dark (Default)"),
            bg_main="#1E1E1E",
            bg_panel="#252526",
            bg_list="#2D2D30",
            bg_item_hover="#37373D",
            fg_main="#CCCCCC",
            fg_dim="#858585",
            accent="#007ACC",
            divider="#404040",
            canvas_bg="#646469",
            font_size=10
        ),
        "light": ThemeColors(
            name=_("Light (VS)"),
            bg_main="#FFFFFF",
            bg_panel="#F3F3F3",
            bg_list="#F3F3F3",
            bg_item_hover="#E8E8E8",
            fg_main="#333333",
            fg_dim="#6F6F6F",
            accent="#007ACC",
            divider="#D4D4D4",
            canvas_bg="#A0A0A5",
            font_size=10
        ),
        "visual_studio_blue": ThemeColors(
            name=_("Visual Studio Blue"),
            bg_main="#2D2D30",
            bg_panel="#007ACC",
            bg_list="#1E1E1E",
            bg_item_hover="#3E3E42",
            fg_main="#FFFFFF",
            fg_dim="#D0D0D0",
            accent="#FFB900",
            divider="#005A9E",
            canvas_bg="#505055",
            font_size=10
        ),
        "monokai": ThemeColors(
            name=_("Monokai"),
            bg_main="#272822",
            bg_panel="#1E1F1C",
            bg_list="#272822",
            bg_item_hover="#3E3D32",
            fg_main="#F8F8F2",
            fg_dim="#75715E",
            accent="#A6E22E",
            divider="#49483E",
            canvas_bg="#3E3D32",
            font_size=10
        )
    }
    
    # Store built-in keys for reference
    BUILTIN_THEMES = list(THEMES.keys())

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize ThemeManager."""
        if config_dir:
            self.config_path = Path(config_dir) / "theme_settings.json"
        else:
            self.config_path = Path(__file__).parent.parent / "config" / "theme_settings.json"
            
        self.current_theme_name = "dark"
        self.load()

    def load(self) -> None:
        """Load theme setting from disk."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    theme = data.get("theme", "dark")
                    if theme in self.THEMES:
                        self.current_theme_name = theme
                        
                    # [REQ-013] Load Font Size Override
                    font_size = data.get("font_size", None)
                    if font_size and isinstance(font_size, int):
                        # Apply to ALL themes temporarily (or per theme if redesigned)
                        # For now, simplistic approach: Update current theme instance in memory
                        # Ideally, font size should be global, not per-theme
                        for t in self.THEMES.values():
                            t.font_size = font_size
                            
                    # [REQ-013] Load Custom Themes
                    custom_themes = data.get("custom_themes", {})
                    if custom_themes and isinstance(custom_themes, dict):
                        for c_id, c_data in custom_themes.items():
                            try:
                                # Ensure required fields exist or create default
                                # Simple validation: Convert dict to ThemeColors
                                # Note: This requires c_data to match ThemeColors fields exactly
                                # To be robust, we should fill missing with defaults from 'dark'
                                base_defaults = asdict(self.THEMES["dark"])
                                base_defaults.update(c_data)
                                
                                new_theme = ThemeColors(**base_defaults)
                                self.THEMES[c_id] = new_theme
                                print(f"🎨 Loaded custom theme: {c_id}")
                            except Exception as e:
                                print(f"Error loading custom theme '{c_id}': {e}")

            except Exception as e:
                print(f"Error loading theme settings: {e}")

    def save(self) -> bool:
        """Save current theme setting to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # [REQ-013] Save Font Size
            current_font = self.get_current_theme().font_size
            
            # [REQ-013] Collect Custom Themes
            custom_themes = {}
            for t_id, t_obj in self.THEMES.items():
                if t_id not in self.BUILTIN_THEMES:
                    custom_themes[t_id] = asdict(t_obj)
            
            data = {
                "theme": self.current_theme_name,
                "font_size": current_font,
                "custom_themes": custom_themes
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving theme settings: {e}")
            return False

    def get_current_theme(self) -> ThemeColors:
        """Get current theme color object."""
        return self.THEMES.get(self.current_theme_name, self.THEMES["dark"])

    def get_theme_colors(self, theme_name: str) -> Optional[ThemeColors]:
        """Get colors for a specific theme name."""
        return self.THEMES.get(theme_name)

    def set_theme(self, theme_name: str) -> bool:
        """Set current theme."""
        if theme_name in self.THEMES:
            self.current_theme_name = theme_name
            self.save()
            return True
        return False

    def get_all_themes(self) -> Dict[str, str]:
        """Get all theme keys and names."""
        return {k: v.name for k, v in self.THEMES.items()}

_manager = None

def get_theme_manager(config_dir: Optional[str] = None) -> ThemeManager:
    """Get singleton ThemeManager instance."""
    global _manager
    if _manager is None:
        _manager = ThemeManager(config_dir)
    return _manager
