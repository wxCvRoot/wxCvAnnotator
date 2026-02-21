import wx
import gettext
import json
import os
from pathlib import Path
from typing import Dict, Tuple, List


class I18nManager:
    """I18n Manager with dynamic language discovery"""
    
    def __init__(self, default_lang='en'):
        """Initialize I18n Manager
        
        Args:
            default_lang: Default language code
        """
        self.current_language = default_lang
        self.i18n = None
        self.supported_languages: Dict[str, Tuple[str, str, Path]] = {}
        
        # Paths to scan
        self.root_dir = Path(__file__).parent.parent
        self.builtin_dir = self.root_dir / 'i18n' / 'translations'
        self.user_dir = self.root_dir / 'config' / 'translations'
        
        self._discover_languages()
        self._setup_translation()
    
    def _discover_languages(self):
        """Scan directories for available language packs"""
        # Dictionary to store discovered languages: {code: (name, local_name, path)}
        discovered = {}
        
        # Directories to scan in order (Built-in first, then User overrides)
        scan_dirs = [self.builtin_dir, self.user_dir]
        
        for base_dir in scan_dirs:
            if not base_dir.exists():
                continue
                
            for lang_dir in base_dir.iterdir():
                if lang_dir.is_dir():
                    lang_code = lang_dir.name
                    
                    # Look for metadata.json
                    metadata_path = lang_dir / "metadata.json"
                    name = lang_code
                    local_name = lang_code
                    
                    if metadata_path.exists():
                        try:
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                meta = json.load(f)
                                name = meta.get("name", lang_code)
                                local_name = meta.get("local_name", name)
                        except Exception as e:
                            print(f"Error loading metadata for {lang_code}: {e}")
                    
                    # Store discovery info (user_dir overrides builtin if same code)
                    discovered[lang_code] = (name, local_name, base_dir)
        
        # Ensure en is always present if not found
        if 'en' not in discovered:
            discovered['en'] = ('English', 'English', self.builtin_dir)
            
        self.supported_languages = discovered

    def _setup_translation(self):
        """Setup translation using gettext"""
        try:
            # Get path for current language
            lang_info = self.supported_languages.get(self.current_language)
            if not lang_info:
                # Fallback to default
                self.current_language = 'en'
                lang_info = self.supported_languages.get('en')
            
            locale_dir = lang_info[2]
            
            # Install gettext
            gettext.install('wxCvAnnotator', localedir=str(locale_dir))
            
            # Special case for English (often no .mo file needed if strings in code are English)
            if self.current_language == 'en':
                self.i18n = gettext.NullTranslations()
            else:
                self.i18n = gettext.translation(
                    'wxCvAnnotator',
                    localedir=str(locale_dir),
                    languages=[self.current_language],
                    fallback=True
                )
            
            self.i18n.install()
            
        except Exception as e:
            print(f"Translation setup failed: {e}")
            self.current_language = 'en'
            gettext.install('wxCvAnnotator', localedir=None)
            self.i18n = gettext.NullTranslations()
            self.i18n.install()
    
    def set_language(self, lang_code):
        """Set language
        
        Args:
            lang_code: Language code (zh_TW, en, etc.)
        """
        if lang_code in self.supported_languages:
            self.current_language = lang_code
            self._setup_translation()
            return True
        return False
        
    def refresh_discovery(self):
        """Re-scan metadata and update available languages"""
        self._discover_languages()
        # Re-setup if current language might have new metadata
        self._setup_translation()
    
    def get_current_language(self):
        """Get current language"""
        return self.current_language
    
    def get_language_list(self):
        """Get supported languages list {code: (name, local_name)}"""
        return {code: (info[0], info[1]) for code, info in self.supported_languages.items()}
    
    def get_language_display_name(self, lang_code=None):
        """Get language display name"""
        if lang_code is None:
            lang_code = self.current_language
            
        info = self.supported_languages.get(lang_code)
        if info:
            return info[0], info[1]
        return (_('Unknown'), _('Unknown'))
    
    def create_language_menu(self, parent, callback):
        """Create language menu dynamically based on discovered locales"""
        menu = wx.Menu()
        
        # Sort by display name for better UX
        sorted_langs = sorted(
            self.supported_languages.items(), 
            key=lambda x: x[1][0] # Sort by English name
        )
        
        for lang_code, (english_name, local_name, lang_path) in sorted_langs:
            checked = lang_code == self.current_language
            
            item = menu.AppendRadioItem(
                wx.ID_ANY,
                f"{english_name} ({local_name})",
                _("Switch to {}").format(local_name)
            )
            
            if checked:
                item.Check()
            
            # Bind event
            parent.Bind(
                wx.EVT_MENU,
                lambda event, lang=lang_code: callback(lang),
                id=item.GetId()
            )
        
        return menu


_manager = None

# Factory function for creating I18nManager instance
def get_i18n_manager(default_lang='en') -> I18nManager:
    """Factory function for creating I18nManager instance"""
    global _manager
    if _manager is None:
        _manager = I18nManager(default_lang=default_lang)
    return _manager

# Define _ globally in this module and export it
def _(text: str) -> str:
    """Translation function proxy"""
    if _manager and _manager.i18n:
        return _manager.i18n.gettext(text)
    return gettext.gettext(text)