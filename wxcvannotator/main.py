#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wxCvAnnotator v2.0 Main Program
Using redesigned annotation interface, integrated with wxCvROIAdvPanel
"""

import sys
import os
import argparse
import wx
from pathlib import Path

# Initialize settings early to get language
from .utils.settings_manager import SettingsManager
settings = SettingsManager()
saved_lang = settings.get("language", "en_US")

# Initialize i18n early so _() is available globally
from .ui.i18n import get_i18n_manager
get_i18n_manager(default_lang=saved_lang)

from . import __version__
from .ui.main_window import WxCvAnnotatorMainWindow


def main():
    """Main function"""
    print(f"=== wxCvAnnotator {__version__} Starting ===")
    print("Redesigned annotation tool interface")
    print("Designed based on LabelMe mode, integrated with wxCvROIAdvPanel")
    print("Key features: onCrop event handling, annotation data management")
    print()

    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description=f"wxCvAnnotator {__version__} - Image Annotation Tool")
        parser.add_argument("filename", nargs="?", help="Image file or directory path")
        parser.add_argument("--labels", help="Comma-separated list of labels or path to label file")
        parser.add_argument("--nodata", action="store_true", help="Stop storing image data in JSON")
        parser.add_argument("--embed", action="store_true", help="Force embed image data in JSON (wxCvAnnotator option)")
        parser.add_argument("--output", help="Output directory for annotations")
        parser.add_argument("--config", help="Custom settings.json path")

        args = parser.parse_args()

        # Create wxPython app
        app = wx.App(False)

        # Check for C++ module (dev lib override in package dir)
        lib_path = Path(__file__).parent / "lib"
        module_found = any(lib_path.glob("wxCvModule.*"))

        if not module_found:
            print(f"⚠️  Warning: Cannot find wxCvModule lib in: {lib_path}")
            print("   Running in mock mode...")

        # Create main window with CLI arguments
        main_window = WxCvAnnotatorMainWindow(
            path=args.filename,
            labels=args.labels,
            nodata=args.nodata,
            embed=args.embed,
            output=args.output,
            config_path=args.config
        )

        # Show window
        main_window.Show()

        print("✓ Main window created successfully")
        if args.filename:
            print(f"✓ Target path: {args.filename}")

        # Enter main loop
        app.MainLoop()

    except Exception as e:
        print(f"✗ Launch failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
