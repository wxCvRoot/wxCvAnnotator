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

from . import __version__


def main():
    """Main function"""
    print(f"=== wxCvAnnotator {__version__} Starting ===")
    print()

    try:
        # Pre-parse --lang before i18n initialization so it takes effect immediately
        pre_parser = argparse.ArgumentParser(add_help=False)
        pre_parser.add_argument("--lang", default=None)
        pre_args, _ = pre_parser.parse_known_args()

        # Initialize settings early to get language
        from .utils.settings_manager import SettingsManager
        settings = SettingsManager()
        saved_lang = settings.get("language", "en_US")

        # --lang on CLI overrides saved setting (session-only, does not persist)
        effective_lang = pre_args.lang if pre_args.lang else saved_lang

        # Initialize i18n early so _() is available globally
        from .ui.i18n import get_i18n_manager
        get_i18n_manager(default_lang=effective_lang)

        from .ui.main_window import WxCvAnnotatorMainWindow

        # Full argument parsing
        parser = argparse.ArgumentParser(description=f"wxCvAnnotator {__version__} - Image Annotation Tool")
        parser.add_argument("filename", nargs="?", help="Image file or directory path")
        parser.add_argument("--labels", help="Comma-separated list of labels or path to label file")
        parser.add_argument("--nodata", action="store_true", help="Stop storing image data in JSON")
        parser.add_argument("--embed", action="store_true", help="Force embed image data in JSON (wxCvAnnotator option)")
        parser.add_argument("--output", help="Output directory for annotations")
        parser.add_argument("--config", help="Custom settings.json path")
        parser.add_argument(
            "--lang",
            metavar="LANG",
            help=(
                "Override display language for this session (does not change saved setting). "
                "Examples: en_US, zh_TW, zh_CN, ja_JP, ko_KR, fr_FR, de_DE, es_ES, ru_RU, ar_SA, "
                "it_IT, nl_NL, pt_BR, th_TH, tr_TR, vi_VN, fa_IR"
            ),
        )
        parser.add_argument(
            "--no-help",
            action="store_true",
            dest="no_help",
            help="Hide Help menu from menu bar and set app title to 'Annotation Tool'",
        )

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
            config_path=args.config,
            no_help=args.no_help,
        )

        # Show window
        main_window.Show()

        print("✓ Main window created successfully")
        if args.filename:
            print(f"✓ Target path: {args.filename}")
        if args.lang:
            print(f"✓ Language override: {args.lang}")

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
