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

from . import __version__


def main():
    """Main function"""
    print(f"=== wxCvAnnotator {__version__} Starting ===")
    print()

    import time
    start_time = time.time()
    t_imports = {}

    try:
        # Pre-parse --lang
        pre_parser = argparse.ArgumentParser(add_help=False)
        pre_parser.add_argument("--lang", default=None)
        pre_args, _ = pre_parser.parse_known_args()

        # Measure Settings Import & Init
        t_start = time.time()
        from .utils.settings_manager import SettingsManager
        t_imports['SettingsManager'] = time.time() - t_start
        
        t_settings_start = time.time()
        settings = SettingsManager()
        saved_lang = settings.get("language", "en_US")
        t_settings = time.time() - t_settings_start

        effective_lang = pre_args.lang if pre_args.lang else saved_lang

        # Measure I18n Import & Init
        t_start = time.time()
        from .ui.i18n import get_i18n_manager
        t_imports['I18nManager'] = time.time() - t_start
        
        t_i18n_start = time.time()
        get_i18n_manager(default_lang=effective_lang)
        t_i18n = time.time() - t_i18n_start

        # Measure MainWindow Import (This is likely the bottleneck)
        t_start = time.time()
        from .ui.main_window import WxCvAnnotatorMainWindow
        t_imports['MainWindow'] = time.time() - t_start

        # Full argument parsing
        parser = argparse.ArgumentParser(description=f"wxCvAnnotator {__version__} - Image Annotation Tool")
        parser.add_argument("filename", nargs="?", help="Image file or directory path")
        parser.add_argument("--labels", help="Comma-separated list of labels or path to label file")
        parser.add_argument("--nodata", action="store_true", help="Stop storing image data in JSON")
        parser.add_argument("--embed", action="store_true", help="Force embed image data in JSON (wxCvAnnotator option)")
        parser.add_argument("--output", help="Output directory for annotations")
        parser.add_argument("--config", help="Custom settings.json path")
        parser.add_argument("--lang", metavar="LANG", help="Override display language")
        parser.add_argument("--no-help", action="store_true", dest="no_help", help="Hide Help menu")
        parser.add_argument("--model-path", dest="model_path", metavar="PATH", help="Override AI path")
        args = parser.parse_args()

        # Create wxPython app
        t_app_start = time.time()
        app = wx.App(False)
        t_app = time.time() - t_app_start

        # Check for C++ module
        t_module_start = time.time()
        try:
            import wxCvModule  # noqa: F401
            module_found = True
        except ImportError:
            module_found = False
        t_module = time.time() - t_module_start

        # Create main window
        t_window_start = time.time()
        main_window = WxCvAnnotatorMainWindow(
            path=args.filename,
            labels=args.labels,
            nodata=args.nodata,
            embed=args.embed,
            output=args.output,
            config_path=args.config,
            no_help=args.no_help,
            model_path=args.model_path,
        )
        t_window = time.time() - t_window_start

        main_window.Show()

        total_startup_time = time.time() - start_time
        print(f"✓ Main window created successfully (Total: {total_startup_time:.2f}s)")
        print(f"  - [Import] MainWindow:    {t_imports.get('MainWindow', 0):.2f}s")
        print(f"  - [Import] Others:        {(t_imports.get('SettingsManager',0) + t_imports.get('I18nManager',0)):.2f}s")
        print(f"  - [Init]   Settings:      {t_settings:.2f}s")
        print(f"  - [Init]   I18n:          {t_i18n:.2f}s")
        print(f"  - [Init]   wx.App:        {t_app:.2f}s")
        print(f"  - [Init]   C++ Mod:       {t_module:.2f}s")
        print(f"  - [Init]   Window Class:  {t_window:.2f}s")
        
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
