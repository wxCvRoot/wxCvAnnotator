#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings Manager - Handles application-wide settings and persistence.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

class SettingsManager:
    """Manages application settings stored in a JSON file."""
    
    DEFAULT_SETTINGS = {
        "last_folder": "",
        "embed_base64": False, # Changed from 'false' to 'False' to match Python boolean
        "canvas_bg_color": "#808080",
        "language": "en",
        "recent_folders": [],
        "annotator_name": "",
        "annotator_quality": 100.0,
        "save_user_info": True,
        "ai_model_path": "models",
        "ai_continuous_inference": False,
        "ai_inference_throttle_ms": 100,
        "ai_auto_simplify_polygon": True,
        "ai_denoise_mask": True,
        "ai_polygon_tolerance": 0.004,
        "enable_attribute_panel": True,
        "default_flags": ["occluded", "truncated", "difficult"]
    }

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize SettingsManager.
        
        Args:
            config_dir: Directory to store settings.json. Defaults to project 'config' dir.
        """
        if config_dir:
            self.config_path = Path(config_dir) / "settings.json"
        else:
            # Default to the 'config' directory relative to this file's parent's parent
            self.config_path = Path(__file__).parent.parent / "config" / "settings.json"
            
        self.settings: Dict[str, Any] = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self) -> None:
        """Load settings from disk. Falls back to settings.default.json on first run."""
        if not self.config_path.exists():
            default_path = self.config_path.parent / "settings.default.json"
            if default_path.exists():
                try:
                    with open(default_path, 'r', encoding='utf-8') as f:
                        self.settings.update(json.load(f))
                except Exception:
                    pass
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                # Update defaults with loaded data to handle new setting keys
                self.settings.update(loaded_data)
        except Exception as e:
            print(f"Error loading settings from {self.config_path}: {e}")
            # Keep defaults on error

    def save(self) -> bool:
        """Save current settings to disk."""
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving settings to {self.config_path}: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        """
        Set a setting value and optionally save to disk.
        
        Args:
            key: Setting key.
            value: Setting value.
            save: Whether to save immediately after setting.
        """
        self.settings[key] = value
        if save:
            self.save()

    def add_recent_folder(self, folder_path: str, max_count: int = 10) -> None:
        """
        Add a folder to the recent folders list.
        
        Args:
            folder_path: Path to the folder.
            max_count: Maximum number of recent folders to keep.
        """
        recent = self.settings.get("recent_folders", [])
        
        # Remove if already exists to move it to the top
        if folder_path in recent:
            recent.remove(folder_path)
            
        recent.insert(0, folder_path)
        
        # Trim list
        if len(recent) > max_count:
            recent = recent[:max_count]
            
        self.settings["recent_folders"] = recent
        self.save()

    @property
    def last_folder(self) -> str:
        return self.get("last_folder", "")

    @last_folder.setter
    def last_folder(self, value: str):
        self.set("last_folder", value)
        if value:
            self.add_recent_folder(value)
