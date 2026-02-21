"""
wxCvAnnotator Main Window v2 - Redesigned based on LabelMe mode
New annotation tool interface, integrating all core features.
"""

import wx
import wx.adv
import wx.lib.buttons as wxbuttons
import platform
from pathlib import Path
import os
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

# Package root: wxcvannotator/ (parent of this file's parent ui/)
PACKAGE_ROOT = Path(__file__).parent.parent
# Project root (where resources/ is located)
PROJECT_ROOT = PACKAGE_ROOT.parent

import ctypes
try:
    # Set AppUserModelID to show the correct icon on Windows taskbar
    myappid = u'wxCvRoot.wxCvAnnotator.0.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# Import custom modules
from .annotation_toolbar import AnnotationToolbar
from .image_display_panel import ImageDisplayPanel
from .annotation_system import Annotation, DEFAULT_CATEGORY_COLORS, AnnotationManager, CategoryManager
from .export_system import ExportSystem
from . export_dialog import BatchExportDialog, AdvancedExportDialog
from .i18n import get_i18n_manager, _
from ..utils.settings_manager import SettingsManager
from ..utils.ai_service import AIService
from .theme_manager import get_theme_manager
from .ocr_components import TextEditPopup
from .settings_dialog import SettingsDialog
from .attribute_panel import AttributePanel
from .. import __version__



class WxCvAnnotatorMainWindow(wx.Frame):
    """wxCvAnnotator Main Window - Designed based on LabelMe mode"""
    
    def __init__(self, path=None, labels=None, nodata=False, embed=False, output=None, config_path=None):
        """Initialize main window"""
        super().__init__(
            None,
            title=f"wxCvAnnotator {__version__} - Image Annotation Tool",
            size=wx.Size(1400, 900),
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL
        )
        
        # 加載設置 (CLI config_path 優先)
        config_dir = os.path.dirname(config_path) if config_path else None
        self.settings_manager = SettingsManager(config_dir=config_dir)
        
        # 獲取保存的語言
        saved_lang = self.settings_manager.get("language", "en_US")
        
        # 國際化管理器 (傳入初始語言)
        self.i18n_manager = get_i18n_manager(default_lang=saved_lang)
        
        # 處理 CLI 覆蓋
        if nodata:
            self.settings_manager.set("embed_base64", False, save=False)
        elif embed:
            self.settings_manager.set("embed_base64", True, save=False)
            
        # 主題管理器
        self.theme_manager = get_theme_manager(config_dir=config_dir)
            
        if output:
            self.output_dir = output
        else:
            self.output_dir = None
            
        # 當前項目信息
        self.current_project = None
        self.current_image_path = None
        self.project_folder = None
        self.file_navigation_enabled = False
        self.current_image_index = 0
        self.image_files = []
        
        # 窗口組件
        self.image_display_panel = None
        self.toolbar = None
        self.right_panel = None
        self.label_list_panel = None
        self.annotation_list_panel = None
        self.file_list_panel = None
        
        # Export system
        self.export_system = None
        
        # Category manager
        self.category_manager = CategoryManager()
        
        # Setup window properties
        self._setup_window_properties()
        
        # Create UI
        self._setup_ui()
        
        # Create custom IDs (must be before menu creation)
        self.id_open_folder = wx.NewId()
        self.id_tool_rectangle = wx.NewId()
        self.id_tool_polygon = wx.NewId()
        self.id_tool_circle = wx.NewId()
        self.id_tool_annulus = wx.NewId()
        self.id_tool_point = wx.NewId()
        self.id_tool_line = wx.NewId()
        self.id_tool_select = wx.NewId()
        self.id_batch_export = wx.NewId()
        self.id_export_formats = wx.NewId()
        self.id_export_dataset_split = wx.NewId()
        self.id_save_labels_to_project = wx.NewId()
        self.id_load_labels_from_project = wx.NewId()
        self.id_settings = wx.NewId()
        self.id_about = wx.NewId()
        
        # 創建菜單並設置到窗口
        menu_bar = self._create_menu()
        if menu_bar:
            self.SetMenuBar(menu_bar)
            
        # Apply initial theme
        self._apply_theme(self.theme_manager.get_current_theme())
        
        # 創建狀態欄
        self._create_status_bar()
        
        # 綁定事件
        self._bind_events()
        
        # 初始化標註系統
        self._init_annotation_system()
        
        # Initialize export system
        self._init_export_system()
        
        # 處理初始標籤 (CLI --labels 優先)
        if labels:
            self._load_labels_from_cli(labels)
        
        # 處理初始載入路徑 (CLI path 優先)
        if path:
            self._handle_initial_path(path)
        
        print(f"✓ wxCvAnnotator {__version__} Main window created")

    def _handle_initial_path(self, path: str):
        """處理啟動時傳入的路徑"""
        path_obj = Path(path)
        if path_obj.is_dir():
            # 使用 CallAfter 確保 UI 初始化完成後再載入
            wx.CallAfter(self._load_folder_images, str(path_obj))
        elif path_obj.is_file():
            if self.image_display_panel:
                wx.CallAfter(self.image_display_panel.load_image, str(path_obj))

    def _load_labels_from_cli(self, labels: str):
        """從 CLI 載入標籤列表"""
        try:
            label_list = []
            if os.path.exists(labels):
                # 如果是文件路徑
                with open(labels, 'r', encoding='utf-8') as f:
                    label_list = [line.strip() for line in f if line.strip()]
            else:
                # 如果是逗號分隔字符串
                label_list = [l.strip() for l in labels.split(',') if l.strip()]
            
            if label_list:
                for label in label_list:
                    self.category_manager.add_category(label)
                print(f"✓ Loaded {len(label_list)} labels from CLI")
        except Exception as e:
            print(f"⚠ Failed to load labels from CLI: {e}")
    
    def _setup_window_properties(self):
        """設置窗口屬性"""
        # 設置最小尺寸
        self.SetMinSize(wx.Size(1000, 700))
        
        # 設置圖標（如果存在）
        try:
            # Try loading .ico first, then .png
            icon_path_ico = PACKAGE_ROOT / "assets" / "icon.ico"
            icon_path_png = PACKAGE_ROOT / "assets" / "logo.png"
            
            if icon_path_ico.exists():
                icon = wx.Icon(str(icon_path_ico))
                self.SetIcon(icon)
            elif icon_path_png.exists():
                # On some platforms wx.Icon can load PNG directly, 
                # but CopyFromBitmap is safer for cross-platform PNG to Icon conversion
                bitmap = wx.Bitmap(str(icon_path_png), wx.BITMAP_TYPE_PNG)
                icon = wx.Icon()
                icon.CopyFromBitmap(bitmap)
                self.SetIcon(icon)
        except Exception as e:
            print(f"設置圖標失敗: {e}")
        
        # 設置窗口居中並最大化
        self.Centre()
        self.Maximize(True)
        
        # Bind Close event
        self.Bind(wx.EVT_CLOSE, self._on_close)
    
    def _setup_ui(self):
        """設置用戶界面 (使用 SplitterWindow 實現可調整大小)"""
        # 創建主面板 (作為 Splitter 的容器)
        self.main_panel = wx.Panel(self, wx.ID_ANY)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.main_panel.SetSizer(main_sizer)

        # 1. 創建主 Splitter (左右分割：工具列 vs 內容區)
        self.main_splitter = wx.SplitterWindow(self.main_panel, wx.ID_ANY, style=wx.SP_LIVE_UPDATE | wx.SP_BORDER)
        self.main_splitter.SetMinimumPaneSize(50) # 工具列最小寬度

        # 2. 創建左側工具欄 (父層為 main_splitter)
        self.toolbar = AnnotationToolbar(self.main_splitter)

        # 3. 創建右側內容 Splitter (左右分割：圖像區 vs 列表區)
        # 這是 main_splitter 的右側面板
        self.content_splitter = wx.SplitterWindow(self.main_splitter, wx.ID_ANY, style=wx.SP_LIVE_UPDATE | wx.SP_BORDER)
        self.content_splitter.SetMinimumPaneSize(100) # 圖像區/列表區最小寬度

        # 4. 創建中央圖像顯示區域 (父層為 content_splitter)
        self.image_display_panel = ImageDisplayPanel(self.content_splitter, settings_manager=self.settings_manager)

        # 4.1 Check AI availability and disable tools if backend missing
        if not AIService.is_available():
            print("⚠️ AIService: onnxruntime not found. Disabling AI features.")
            self.toolbar.enable_ai_section(False)
        
        # 5. 創建右側面板 (父層為 content_splitter)
        # 注意：_create_right_panel 原本接受 sizer，現在我們需要它接受父層窗口
        # 我們將修改 _create_right_panel 以返回面板，而不是添加到 sizer
        self.right_panel = self._create_right_panel_content(self.content_splitter)

        # 6. 設置 Splitter 分割
        # 主分割：工具列在左，內容區在右
        splitter_left_pos = self.settings_manager.get("splitter_left_pos", 60)
        self.main_splitter.SplitVertically(self.toolbar, self.content_splitter, splitter_left_pos)
        self.main_splitter.SetSashGravity(0.0) # 左側工具列固定寬度
        
        # 內容區分割：圖像在左，列表在右
        splitter_right_pos = self.settings_manager.get("splitter_right_pos", -300)
        self.content_splitter.SplitVertically(self.image_display_panel, self.right_panel, splitter_right_pos)
        self.content_splitter.SetSashGravity(1.0) # 右側列表固定寬度

        # 添加到主佈局
        main_sizer.Add(self.main_splitter, 1, wx.EXPAND | wx.ALL, 0)
        
        self.Layout()

    def _on_close(self, event):
        """Handle window close event"""
        # Save splitter positions
        if hasattr(self, 'main_splitter'):
            self.settings_manager.set("splitter_left_pos", self.main_splitter.GetSashPosition())
            
        if hasattr(self, 'content_splitter'):
            self.settings_manager.set("splitter_right_pos", self.content_splitter.GetSashPosition())
            
        # Clean up
        if self.image_display_panel:
            self.image_display_panel.Destroy()
            
        event.Skip()
    
    def _create_right_panel_content(self, parent_window):
        """Create right panel content (for SplitterWindow)"""
        panel = wx.Panel(parent_window, wx.ID_ANY)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(right_sizer)
        
        # Set right panel background color
        panel.SetBackgroundColour(wx.Colour(50, 50, 50))
        
        # 这里需要暂存 self.right_panel 供其他方法使用 (如 _create_label_list_panel)
        # 但 _create_label_list_panel 使用 self.right_panel 作為父層
        # 所以我們先把 panel 賦值給 self.right_panel
        self.right_panel = panel

        # Upper: Label List (Category Selection)
        self.label_list_panel = self._create_label_list_panel()
        right_sizer.Add(self.label_list_panel, 1, wx.EXPAND | wx.ALL, 2)
        
        # Middle: Annotation List
        self.annotation_list_panel = self._create_annotation_list_panel()
        right_sizer.Add(self.annotation_list_panel, 2, wx.EXPAND | wx.ALL, 2)

        # Attribute Panel (conditional)
        self.attribute_panel = None
        if self.settings_manager.get("enable_attribute_panel", False):
            default_flags = self.settings_manager.get("default_flags", ["occluded", "truncated", "difficult"])
            self.attribute_panel = AttributePanel(
                panel, default_flags=default_flags,
                on_change=self._on_attribute_panel_changed
            )
            right_sizer.Add(self.attribute_panel, 1, wx.EXPAND | wx.ALL, 2)

        # Lower: File List
        self.file_list_panel = self._create_file_list_panel()
        right_sizer.Add(self.file_list_panel, 2, wx.EXPAND | wx.ALL, 2)
        
        # Set min width
        panel.SetMinSize(wx.Size(200, -1))
        
        return panel

    def _create_right_panel(self, parent_sizer):
        """Deprecated: Old sizer-based creation, kept for reference or legacy calls checked"""
        # Check if this enters recursive loop if called unexpectedly.
        # Ideally remove this method, but replacing it safely.
        pass
    
    def _create_label_list_panel(self):
        """Create label list panel (Category selection)"""
        panel = wx.Panel(self.right_panel, wx.ID_ANY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetBackgroundColour(wx.Colour(40, 40, 43))
        
        # Title
        self.label_list_title = wx.StaticText(panel, wx.ID_ANY, _("Label List"))
        self.label_list_title.SetForegroundColour(wx.WHITE)
        title_font = self.label_list_title.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.label_list_title.SetFont(title_font)
        sizer.Add(self.label_list_title, 0, wx.ALL | wx.CENTER, 5)
        
        # Search box (optional, but LabelMe has a small filter)
        # self.label_search = wx.TextCtrl(panel, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
        # sizer.Add(self.label_search, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        # Label selection list (ListBox)
        self.label_list = wx.ListBox(
            panel, wx.ID_ANY,
            style=wx.LB_SINGLE | wx.LB_NEEDED_SB
        )
        self.label_list.SetBackgroundColour(wx.Colour(30, 30, 33))
        self.label_list.SetForegroundColour(wx.WHITE)
        
        # Initial labels
        categories = self.category_manager.get_ordered_categories()
        self.label_list.Set(categories)
        if categories:
            self.label_list.SetSelection(0)
            # Set initial category in image panel
            wx.CallAfter(lambda: self.image_display_panel.set_current_category(categories[0]))
            
        sizer.Add(self.label_list, 1, wx.EXPAND | wx.ALL, 2)
        
        # Bind events
        self.label_list.Bind(wx.EVT_LISTBOX, self._on_label_selected_in_list)
        self.label_list.Bind(wx.EVT_CONTEXT_MENU, self._on_label_list_right_click)
        
        panel.SetSizer(sizer)
        return panel

    def _on_label_selected_in_list(self, event):
        """Handle label selection in the list"""
        selection = self.label_list.GetStringSelection()
        if selection:
            print(f"🏷️  Selected Label: {selection}")
            # Update the drawing label in image display panel
            if self.image_display_panel:
                self.image_display_panel.set_current_category(selection)
            
            if hasattr(self, 'category_manager'):
                self.category_manager.use_category(selection)
                
            self._update_status(_("Label set to: {}").format(selection))

    def _create_annotation_list_panel(self):
        """Create annotation list panel"""
        panel = wx.Panel(self.right_panel, wx.ID_ANY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        self.annotation_list_title = wx.StaticText(panel, wx.ID_ANY, _("Annotation List"))
        self.annotation_list_title.SetForegroundColour(wx.WHITE)
        title_font = self.annotation_list_title.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.annotation_list_title.SetFont(title_font)
        sizer.Add(self.annotation_list_title, 0, wx.ALL | wx.CENTER, 5)
        
        # List control
        self.annotation_list = wx.ListCtrl(
            panel, wx.ID_ANY,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES
        )
        
        # Add columns
        self.annotation_list.AppendColumn(_("ID"), width=30)
        self.annotation_list.AppendColumn(_("Label"), width=80)
        self.annotation_list.AppendColumn(_("Type"), width=60)
        self.annotation_list.AppendColumn(_("Vis"), width=40)
        
        # Set colors
        self.annotation_list.SetBackgroundColour(wx.Colour(40, 40, 43))
        self.annotation_list.SetForegroundColour(wx.WHITE)
        
        sizer.Add(self.annotation_list, 1, wx.EXPAND | wx.ALL, 2)
        
        # Control buttons
        control_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        _btn_cls = wxbuttons.GenButton if platform.system() == 'Darwin' else wx.Button
        self.btn_edit = _btn_cls(panel, wx.ID_ANY, _("Edit"))
        self.btn_delete = _btn_cls(panel, wx.ID_ANY, _("Delete"))
        self.btn_visibility = _btn_cls(panel, wx.ID_ANY, _("Visibility"))
        
        # Style buttons
        for btn in [self.btn_edit, self.btn_delete, self.btn_visibility]:
            self._style_side_button(btn)
        
        control_sizer.Add(self.btn_edit, 0, wx.ALL, 2)
        control_sizer.Add(self.btn_delete, 0, wx.ALL, 2)
        control_sizer.Add(self.btn_visibility, 0, wx.ALL, 2)
        
        sizer.Add(control_sizer, 0, wx.EXPAND | wx.ALL, 2)
        
        # Bind events
        self.annotation_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_annotation_selected)
        self.btn_edit.Bind(wx.EVT_BUTTON, self._on_edit_annotation)
        self.btn_delete.Bind(wx.EVT_BUTTON, self._on_delete_annotation)
        self.btn_visibility.Bind(wx.EVT_BUTTON, self._on_toggle_visibility)
        
        panel.SetSizer(sizer)
        return panel
    
    def _create_file_list_panel(self):
        """Create file list panel"""
        panel = wx.Panel(self.right_panel, wx.ID_ANY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        self.file_list_title = wx.StaticText(panel, wx.ID_ANY, _("File List"))
        self.file_list_title.SetForegroundColour(wx.WHITE)
        title_font = self.file_list_title.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.file_list_title.SetFont(title_font)
        sizer.Add(self.file_list_title, 0, wx.ALL | wx.CENTER, 5)
        
        # List control
        self.file_list = wx.ListCtrl(
            panel, wx.ID_ANY,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES
        )
        
        # Add columns
        self.file_list.AppendColumn(_("Filename"), width=120)
        self.file_list.AppendColumn(_("Count"), width=60)
        self.file_list.AppendColumn(_("Status"), width=60)
        
        # Set colors
        self.file_list.SetBackgroundColour(wx.Colour(40, 40, 43))
        self.file_list.SetForegroundColour(wx.WHITE)
        
        sizer.Add(self.file_list, 1, wx.EXPAND | wx.ALL, 2)
        
        # Navigation
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        _btn_cls = wxbuttons.GenButton if platform.system() == 'Darwin' else wx.Button
        self.btn_prev = _btn_cls(panel, wx.ID_ANY, _("Prev"))
        self.btn_next = _btn_cls(panel, wx.ID_ANY, _("Next"))
        
        # Style buttons
        self._style_side_button(self.btn_prev)
        self._style_side_button(self.btn_next)
        
        nav_sizer.Add(self.btn_prev, 0, wx.ALL, 2)
        nav_sizer.Add(self.btn_next, 0, wx.ALL, 2)
        
        sizer.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 2)
        
        # Bind events
        self.btn_prev.Bind(wx.EVT_BUTTON, self._on_prev_image)
        self.btn_next.Bind(wx.EVT_BUTTON, self._on_next_image)
        self.file_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_file_selected)
        self.file_list.Bind(wx.EVT_LIST_KEY_DOWN, self._on_file_list_key_down)
        self.file_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_file_list_right_click)
        
        panel.SetSizer(sizer)
        return panel
    
    def _create_menu(self):
        """創建菜單（簡化版）"""
        # 菜單欄
        menu_bar = wx.MenuBar()
        
        # 文件菜單
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, _("Open Image") + "\tCtrl+O")
        file_menu.Append(self.id_open_folder, _("Open Folder") + "\tCtrl+Shift+O")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_SAVE, _("Save") + "\tCtrl+S")
        file_menu.Append(wx.ID_SAVEAS, _("Save As..."))
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, _("Exit") + "\tCtrl+Q")
        
        menu_bar.Append(file_menu, _("File"))
        
        # Project/Labels Menu
        project_menu = wx.Menu()
        project_menu.Append(self.id_save_labels_to_project, _("Save Labels to Project Folder") + "\tCtrl+L")
        project_menu.Append(self.id_load_labels_from_project, _("Reload Labels from Project"))
        project_menu.AppendSeparator()
        project_menu.Append(wx.ID_ANY, _("Manage Categories..."), _("Open category manager dialog")) # Re-using ID_ANY for now or specific ID
        
        menu_bar.Append(project_menu, _("Project"))
        
        # 編輯菜單
        edit_menu = wx.Menu()
        edit_menu.Append(wx.ID_UNDO, _("Undo") + "\tCtrl+Z")
        edit_menu.Append(wx.ID_REDO, _("Redo") + "\tCtrl+Y")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_DELETE, _("Delete Annotation") + "\tDelete")
        
        menu_bar.Append(edit_menu, _("Edit"))
        
        # 標註菜單
        annotate_menu = wx.Menu()
        annotate_menu.Append(self.id_tool_rectangle, _("Rectangle") + "\tR")
        annotate_menu.Append(self.id_tool_line, _("Line") + "\tL")
        annotate_menu.Append(self.id_tool_polygon, _("Polygon") + "\tP")
        annotate_menu.Append(self.id_tool_circle, _("Circle") + "\tC")
        annotate_menu.Append(self.id_tool_annulus, _("Annulus") + "\tA")
        annotate_menu.Append(self.id_tool_point, _("Point") + "\tD")
        annotate_menu.AppendSeparator()
        annotate_menu.Append(self.id_tool_select, _("Select Tool") + "\tS")
        
        menu_bar.Append(annotate_menu, _("Annotate"))
        
        # 視圖菜單
        view_menu = wx.Menu()
        # Use Ctrl+= as the primary accelerator for Zoom In to handle common keyboard layouts
        view_menu.Append(wx.ID_ZOOM_IN, _("Zoom In") + "\tCtrl+=")
        view_menu.Append(wx.ID_ZOOM_OUT, _("Zoom Out") + "\tCtrl+-")
        view_menu.Append(wx.ID_ZOOM_FIT, _("Fit Window") + "\tCtrl+0")
        
        menu_bar.Append(view_menu, _("View"))
        
        # Export Menu
        export_menu = wx.Menu()
        export_menu.Append(self.id_batch_export, _("Batch Export..."))
        export_menu.Append(self.id_export_dataset_split, _("Export Dataset (Split)..."))
        export_menu.AppendSeparator()
        export_menu.Append(self.id_export_formats, _("Supported Formats"))
        
        menu_bar.Append(export_menu, _("Export"))
        
        # Settings Menu (Consolidated)
        settings_menu = wx.Menu()
        settings_menu.Append(self.id_settings, _("Settings...") + "\tCtrl+,")
        
        menu_bar.Append(settings_menu, _("Settings"))
        
        # Help Menu
        help_menu = wx.Menu()
        help_menu.Append(self.id_about, _("About") + " wxCvAnnotator")
        
        menu_bar.Append(help_menu, _("Help"))
        
        return menu_bar
    
    def _create_menu_bar(self) -> Optional[wx.MenuBar]:
        """Create menu bar (alternative method)"""
        return None  # Use _create_menu instead
    
    def _create_status_bar(self):
        """Create or update status bar"""
        if not hasattr(self, 'status_bar') or not self.status_bar:
            self.status_bar = self.CreateStatusBar(5)
            # Fields: [0] main message, [1] tool, [2] count, [3] cursor pos + RGB, [4] image size
            self.status_bar.SetStatusWidths([-1, 110, 80, 240, 130])

        # 初始化狀態 (及更新翻譯)
        self.status_bar.SetStatusText(_("Ready"), 0)
        self.status_bar.SetStatusText(_("Tool: Select"), 1)
        self.status_bar.SetStatusText(_("Count: 0"), 2)
        self.status_bar.SetStatusText("", 3)
        self.status_bar.SetStatusText("", 4)
    
    def _bind_events(self):
        """Bind event handlers"""
        # Menu events
        self.Bind(wx.EVT_MENU, self._on_file_open, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self._on_open_folder, id=self.id_open_folder)
        self.Bind(wx.EVT_MENU, self._on_file_save, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self._on_file_save_as, id=wx.ID_SAVEAS)
        self.Bind(wx.EVT_MENU, self._on_exit, id=wx.ID_EXIT)
        
        self.Bind(wx.EVT_MENU, self._on_undo, id=wx.ID_UNDO)
        self.Bind(wx.EVT_MENU, self._on_redo, id=wx.ID_REDO)
        self.Bind(wx.EVT_MENU, self._on_delete_annotation, id=wx.ID_DELETE)
        
        self.Bind(wx.EVT_MENU, self._on_tool_rectangle, id=self.id_tool_rectangle)
        self.Bind(wx.EVT_MENU, self._on_tool_line, id=self.id_tool_line)
        self.Bind(wx.EVT_MENU, self._on_tool_polygon, id=self.id_tool_polygon)
        self.Bind(wx.EVT_MENU, self._on_tool_circle, id=self.id_tool_circle)
        self.Bind(wx.EVT_MENU, self._on_tool_annulus, id=self.id_tool_annulus)
        self.Bind(wx.EVT_MENU, self._on_tool_point, id=self.id_tool_point)
        self.Bind(wx.EVT_MENU, self._on_tool_select, id=self.id_tool_select)
        
        self.Bind(wx.EVT_MENU, self._on_zoom_in, id=wx.ID_ZOOM_IN)
        self.Bind(wx.EVT_MENU, self._on_zoom_out, id=wx.ID_ZOOM_OUT)
        self.Bind(wx.EVT_MENU, self._on_zoom_fit, id=wx.ID_ZOOM_FIT)
        
        # 導出菜單事件
        self.Bind(wx.EVT_MENU, self._on_batch_export, id=self.id_batch_export)
        self.Bind(wx.EVT_MENU, self._on_export_dataset_split, id=self.id_export_dataset_split)
        self.Bind(wx.EVT_MENU, self._on_export_formats, id=self.id_export_formats)
        self.Bind(wx.EVT_MENU, self._on_about, id=self.id_about)
        
        # 窗口事件
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        
        # List events
        self.annotation_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_annotation_selected)
        self.file_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_file_selected)

        # Project Menu events
        self.Bind(wx.EVT_MENU, self._on_save_labels_to_project, id=self.id_save_labels_to_project)
        self.Bind(wx.EVT_MENU, self._on_load_labels_from_project, id=self.id_load_labels_from_project)
        
        # Settings events
        self.Bind(wx.EVT_MENU, self._on_open_settings, id=self.id_settings)
        
        # Toolbar events
        self.toolbar.set_tool_changed_callback(self._on_tool_changed)
        self.toolbar.set_operation_callback(self._on_operation_clicked)
        
        # New: AI Model Change callback
        if hasattr(self.toolbar, 'ai_model_selector'):
            self.toolbar.ai_model_selector.Bind(wx.EVT_COMBOBOX, self._on_ai_model_ui_changed)
        
        # Image panel events
        self.image_display_panel.set_annotation_changed_callback(self._on_annotation_changed)
        self.image_display_panel.set_selection_changed_callback(self._on_selection_changed)
        self.image_display_panel.set_status_update_callback(self._on_status_update)
        self.image_display_panel.set_pos_update_callback(self._on_pos_update)
    
    def _init_annotation_system(self):
        """Initialize annotation system"""
        # Connect category manager
        self.image_display_panel.set_category_manager(self.category_manager)
        
        # Set tool callback
        self.image_display_panel.set_tool(self.toolbar.get_current_tool())
        
        # [REQ-010] Connect UI lock callback
        self.image_display_panel.set_ui_lock_callback(self.lock_ui_for_ai)
        
        # Update annotation list
        self._update_annotation_list()
        
        print("✓ Annotation system initialized")
    
    def _on_open_settings(self, event):
        """Open settings dialog"""
        dialog = SettingsDialog(self, self.settings_manager)
        dialog.ShowModal()
        dialog.Destroy()
        
    def _on_ai_model_ui_changed(self, event):
        """Handle AI model change from toolbar ComboBox"""
        model = self.toolbar.ai_model_selector.GetStringSelection()
        if self.image_display_panel:
            self.image_display_panel.set_ai_model(model)
        
    def _on_settings_applied(self, lang_code, theme_id):
        """Apply settings changes globally"""
        # Re-apply theme
        self._apply_theme(self.theme_manager.get_current_theme())
        
        # Handle language change if needed
        if self.i18n_manager.get_current_language() != lang_code:
            self._on_language_selected(lang_code)
            
        # Refresh drawing tool (in case something changed)
        if self.image_display_panel:
            self.image_display_panel.set_tool(self.toolbar.get_current_tool())
            self.image_display_panel.Refresh()

    def _on_language_selected(self, lang_code):
        """Internal language selection logic (called from settings applied)"""
        print(f"🌐 Switching language to: {lang_code}")
        if self.i18n_manager.set_language(lang_code):
            # Save setting
            self.settings_manager.set("language", lang_code)
            
            # Get display names
            unused_name, local_name = self.i18n_manager.get_language_display_name(lang_code)
            
            # 1. Update window title
            self.SetTitle("wxCvAnnotator")
            
            # 2. Refresh menu bar immediately
            menu_bar = self._create_menu()
            if menu_bar:
                old_mb = self.GetMenuBar()
                self.SetMenuBar(menu_bar)
                if old_mb:
                    wx.CallAfter(old_mb.Destroy)
            
            # 3. Refresh status bar
            self._create_status_bar()
            
            # 4. Refresh internal panel labels
            self._update_ui_labels()
            
            # Notify user
            wx.MessageBox(
                _("Language changed to {}. Interface elements have been updated.").format(local_name),
                _("Language Changed"),
                wx.OK | wx.ICON_INFORMATION
            )

    def _update_ui_labels(self):
        """Update all UI labels that are not part of menus/status bar"""
        # Tell sub-components to refresh if they have the method
        for component in [self.toolbar, self.image_display_panel, getattr(self, 'attribute_panel', None)]:
            if component and hasattr(component, 'refresh_translations'):
                component.refresh_translations()
        
        # Update our own right panel titles
        if hasattr(self, 'label_list_title'):
            self.label_list_title.SetLabel(_("Label List"))
        if hasattr(self, 'annotation_list_title'):
            self.annotation_list_title.SetLabel(_("Annotation List"))
        if hasattr(self, 'file_list_title'):
            self.file_list_title.SetLabel(_("File List"))
            
        # Update ListCtrl column headers
        if hasattr(self, 'annotation_list'):
            item = self.annotation_list.GetColumn(0)
            item.SetText(_("ID"))
            self.annotation_list.SetColumn(0, item)
            
            item = self.annotation_list.GetColumn(1)
            item.SetText(_("Label"))
            self.annotation_list.SetColumn(1, item)
            
            item = self.annotation_list.GetColumn(2)
            item.SetText(_("Type"))
            self.annotation_list.SetColumn(2, item)
            
            item = self.annotation_list.GetColumn(3)
            item.SetText(_("Vis"))
            self.annotation_list.SetColumn(3, item)
            
        if hasattr(self, 'file_list'):
            item = self.file_list.GetColumn(0)
            item.SetText(_("Filename"))
            self.file_list.SetColumn(0, item)
            
            item = self.file_list.GetColumn(1)
            item.SetText(_("Count"))
            self.file_list.SetColumn(1, item)
            
            item = self.file_list.GetColumn(2)
            item.SetText(_("Status"))
            self.file_list.SetColumn(2, item)
            
        # Update buttons
        if hasattr(self, 'btn_edit'):
            self.btn_edit.SetLabel(_("Edit"))
        if hasattr(self, 'btn_delete'):
            self.btn_delete.SetLabel(_("Delete"))
        if hasattr(self, 'btn_visibility'):
            self.btn_visibility.SetLabel(_("Visibility"))
        if hasattr(self, 'btn_prev'):
            self.btn_prev.SetLabel(_("Prev"))
        if hasattr(self, 'btn_next'):
            self.btn_next.SetLabel(_("Next"))
            
        self.Layout()

    def _style_side_button(self, button: wx.Button):
        """Apply uniform styling to side buttons"""
        if not button: return
        
        # Determine font size
        font_size = 9
        if hasattr(self, 'theme_manager'):
            theme = self.theme_manager.get_current_theme()
            if theme and hasattr(theme, 'font_size'):
                font_size = theme.font_size

        # Default font
        font = button.GetFont()
        font.SetPointSize(font_size)
        button.SetFont(font)
        
        # Initial call before theme is fully active (fallback)
        if not hasattr(self, 'theme_manager'):
            button.SetBackgroundColour(wx.Colour(60, 60, 63))
            button.SetForegroundColour(wx.WHITE)
            return

        # Apply current theme colors if available
        theme = self.theme_manager.get_current_theme()
        if theme:
            button.SetBackgroundColour(wx.Colour(theme.bg_list))
            button.SetForegroundColour(wx.Colour(theme.fg_main))

    def _apply_theme(self, theme_colors):
        """Apply theme to all UI components"""
        # Main background
        bg_main = wx.Colour(theme_colors.bg_main)
        fg_main = wx.Colour(theme_colors.fg_main)
        bg_panel = wx.Colour(theme_colors.bg_panel)
        bg_list = wx.Colour(theme_colors.bg_list)
        
        # Update Main Frame/Panels
        self.main_panel.SetBackgroundColour(bg_main)
        self.right_panel.SetBackgroundColour(bg_panel)
        self.label_list_panel.SetBackgroundColour(bg_panel)
        self.annotation_list_panel.SetBackgroundColour(bg_panel)
        self.file_list_panel.SetBackgroundColour(bg_panel)
        
        # Update Right Panel Titles
        for title_attr in ['label_list_title', 'annotation_list_title', 'file_list_title']:
            if hasattr(self, title_attr):
                title = getattr(self, title_attr)
                if title:
                    title.SetForegroundColour(fg_main)
                    # Also update title font
                    title_font = title.GetFont()
                    title_font.SetPointSize(getattr(theme_colors, 'font_size', 10) + 1)
                    title_font.SetWeight(wx.FONTWEIGHT_BOLD)
                    title.SetFont(title_font)
        
        # Update List controls
        font_size = getattr(theme_colors, 'font_size', 10)
        print(f"DEBUG: Applying font size {font_size} to ListCtrls")
        
        # Use a standard font face (e.g., system default)
        list_font = wx.Font(font_size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        for list_ctrl in [self.label_list, self.annotation_list, self.file_list]:
            list_ctrl.SetBackgroundColour(bg_list)
            list_ctrl.SetForegroundColour(fg_main)
            list_ctrl.SetFont(list_font)
            
            # Force update on items?
            # On Linux/GTK, ListCtrl row height might not update automatically.
            # A trick is to refresh or even toggle a style flag if needed.
            if isinstance(list_ctrl, wx.ListCtrl):
                count = list_ctrl.GetItemCount()
                for i in range(count):
                    list_ctrl.SetItemFont(i, list_font)
            else:
                # ListBox and others
                pass
                
            list_ctrl.Refresh()
            list_ctrl.Update()
            
        # Update Right Panel Buttons
        for btn_attr in ['btn_edit', 'btn_delete', 'btn_visibility', 'btn_prev', 'btn_next']:
            if hasattr(self, btn_attr):
                btn = getattr(self, btn_attr)
                if btn:
                    btn.SetFont(list_font)
                    self._style_side_button(btn)

        # Update Toolbar
        if hasattr(self, 'toolbar') and self.toolbar:
            if hasattr(self.toolbar, 'apply_theme'):
                self.toolbar.apply_theme(theme_colors)
                
        # Update Image Panel
        if hasattr(self, 'image_display_panel') and self.image_display_panel:
            if hasattr(self.image_display_panel, 'apply_theme'):
                self.image_display_panel.apply_theme(theme_colors)
        
        # Update Attribute Panel
        if self.attribute_panel:
            self.attribute_panel.apply_theme(
                theme_colors.bg_panel, theme_colors.fg_main, theme_colors.bg_list
            )

        # Force refresh
        self.Layout()
        self.Refresh()
        self.Update()

    def _init_export_system(self):
        """Initialize export system"""
        try:
            # Get annotation manager from display panel
            if hasattr(self.image_display_panel, 'get_annotation_manager'):
                annotation_manager = self.image_display_panel.get_annotation_manager()
                
                self.export_system = ExportSystem(annotation_manager, self.category_manager)
                print("✓ Export system initialized")
            else:
                print("⚠ Cannot get AnnotationManager, export system init failed")
                self.export_system = None
        except Exception as e:
            print(f"Export system init failed: {e}")
            self.export_system = None
    
    # Event Handlers
    def _on_file_open(self, event):
        """Open image file"""
        print("📂 Opening image file...")
        
        dialog = wx.FileDialog(
            self,
            _("Select Image File"),
            wildcard=_("Image Files") + "|*.jpg;*.jpeg;*.png;*.bmp;*.tiff;*.tif;*.webp;*.j2k;*.jp2;*.heic;*.jxl|" + _("All Files") + "|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            file_path = dialog.GetPath()
            print(f"📁 選擇的文件: {file_path}")
            
            if self.image_display_panel:
                print("🔄 Loading image...")
                success = self.image_display_panel.load_image(file_path)
                print(f"📊 Load result: {success}")
                
                if success:
                    self.current_image_path = file_path
                    self._update_status(_("Opened: {}").format(Path(file_path).name))
                    self._update_image_info(file_path)
                    print(f"✅ Image loaded: {file_path}")
                else:
                    print(f"❌ Failed to load image: {file_path}")
                    wx.MessageBox(_("Cannot load image: {}").format(file_path), _("Error"), wx.OK | wx.ICON_ERROR)
            else:
                print("❌ image_display_panel is None")
                wx.MessageBox(_("Image Panel not initialized"), _("Error"), wx.OK | wx.ICON_ERROR)
        else:
            print("📂 用戶取消了文件選擇")
        
        dialog.Destroy()
    
    def _on_open_folder(self, event):
        """打開文件夾"""
        dialog = wx.DirDialog(
            self,
            _("Select Folder containing images"),
            defaultPath=self.settings_manager.last_folder,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            folder_path = dialog.GetPath()
            self._load_folder_images(folder_path)
        
        dialog.Destroy()
    
    def _on_file_save(self, event):
        """保存標註"""
        if self.current_image_path:
            embed = self.settings_manager.get("embed_base64", False)
            user_info = {
                "annotator_name": self.settings_manager.get("annotator_name", ""),
                "annotator_quality": self.settings_manager.get("annotator_quality", 100.0),
                "save_user_info": self.settings_manager.get("save_user_info", True)
            }
            annotation_path = Path(self.current_image_path).with_suffix('.json')
            if self.image_display_panel.save_annotations(str(annotation_path), embed_data=embed, user_info=user_info):
                self._update_status(_("Annotations Saved (Base64: {})").format(embed))
            else:
                wx.MessageBox(_("Failed to save annotations"), _("Error"), wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox(_("No current image"), _("Hint"), wx.OK | wx.ICON_INFORMATION)
    
    def _on_file_save_as(self, event):
        """Save As"""
        if not self.current_image_path:
            wx.MessageBox("No current image", "Hint", wx.OK | wx.ICON_INFORMATION)
            return
            
        default_path = Path(self.current_image_path).with_suffix('.json')
        dialog = wx.FileDialog(
            self,
            "Save Annotation File",
            defaultDir=str(default_path.parent),
            defaultFile=default_path.name,
            wildcard="JSON Files|*.json|All Files|*.*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            file_path = dialog.GetPath()
            embed = self.settings_manager.get("embed_base64", False)
            user_info = {
                "annotator_name": self.settings_manager.get("annotator_name", ""),
                "annotator_quality": self.settings_manager.get("annotator_quality", 100.0),
                "save_user_info": self.settings_manager.get("save_user_info", True)
            }
            if self.image_display_panel.save_annotations(file_path, embed_data=embed, user_info=user_info):
                self._update_status(_("Annotations saved as... (Base64: {})").format(embed))
            else:
                wx.MessageBox(_("Save failed"), _("Error"), wx.OK | wx.ICON_ERROR)
        
        dialog.Destroy()
    
    def _on_undo(self, event):
        """Undo"""
        if self.image_display_panel.undo():
            self._update_annotation_list()
            self._update_status("Undone")
    
    def _on_redo(self, event):
        """Redo"""
        if self.image_display_panel.redo():
            self._update_annotation_list()
            self._update_status("Redone")
    
    def _on_delete_annotation(self, event):
        """Delete selected annotation"""
        if self.image_display_panel.delete_selected_annotation():
            self._update_annotation_list()
            self._update_status("Annotation Deleted")
    
    # [REQ-010] UI Locking Logic
    def lock_ui_for_ai(self, locked: bool):
        """Lock/Unlock UI elements during AI annotation"""
        # 1. Disable Lists
        if hasattr(self, 'label_list') and self.label_list:
            self.label_list.Enable(not locked)
        if hasattr(self, 'annotation_list') and self.annotation_list:
            self.annotation_list.Enable(not locked)
        # if hasattr(self, 'file_list') and self.file_list:
        #     self.file_list.Enable(not locked)
            
        # 2. Disable buttons in panels
        for attr in ['btn_edit', 'btn_delete', 'btn_visibility', 'btn_prev', 'btn_next']:
            if hasattr(self, attr):
                btn = getattr(self, attr)
                if btn:
                    btn.Enable(not locked)
                    
        # 3. Handle Toolbar Tool Selection
        if self.toolbar:
            # When locked, we only allow the current (AI) tool and finish/cancel buttons
            if locked:
                all_tools = self.toolbar.get_all_tools()
                self.toolbar.enable_all_tools(False)
                # But re-enable the ACTIVE AI tool and Add/Cancel
                current_tool = self.toolbar.get_current_tool()
                for tool in all_tools:
                    if tool.startswith("ai_"):
                        # Only enable the current AI tool being used
                        self.toolbar.enable_tool(tool, tool == current_tool)
                self.toolbar.enable_operation("add", True)
                self.toolbar.enable_operation("cancel", True)
            else:
                self.toolbar.enable_all_tools(True)

        # 4. Update Status
        if locked:
            self._update_status(_("AI Mode: UI locked. Use Enter/Esc to finish."))
        else:
            self._update_status(_("UI Unlocked"))

    def _on_tool_changed(self, tool_type: str):
        """Tool changed"""
        self.image_display_panel.set_tool(tool_type)
        tool_names = {
            "rectangle": _("Rectangle"),
            "polygon": _("Polygon"),
            "circle": _("Circle"), 
            "annulus": _("Annulus"),
            "point": _("Point"),
            "rotated_rect": _("Rotated Rect"),
            "select": _("Select"),
            "ai_polygon": _("🤖 AI Polygon"),
            "ai_mask": _("🎭 AI Mask")
        }
        self._update_status(_("Tool: {}").format(tool_names.get(tool_type, tool_type)))
    
    def _on_operation_clicked(self, operation: str):
        """Operation button clicked"""
        if operation == "undo":
            self._on_undo(None)
        elif operation == "redo":
            self._on_redo(None)
        elif operation == "add":
            self.image_display_panel.add_active_roi()
        elif operation == "cancel":
            self.image_display_panel.cancel_active_roi()
            # Sync toolbar visual state after AI-mode exit
            if self.toolbar and not self.image_display_panel.current_tool.startswith("ai_"):
                self.toolbar.set_current_tool(self.image_display_panel.current_tool)
        elif operation == "delete":
            self._on_delete_annotation(None)
        elif operation == "zoom_in":
            self.image_display_panel.zoom_in()
        elif operation == "zoom_out":
            self.image_display_panel.zoom_out()
        elif operation == "fit_view":
            self.image_display_panel.zoom_fit()
    
    def _on_annotation_changed(self, action: str, annotation_id):
        """Annotation Changed"""
        self._update_annotation_list()
        action_map = {
            "added": _("added"),
            "deleted": _("deleted"),
            "updated": _("updated"),
            "loaded": _("loaded"),
            "undone": _("undone"),
            "redone": _("redone")
        }
        self._update_status(_("Annotation {}").format(action_map.get(action, action)))

        # Refresh attribute panel on annotation changes
        if self.attribute_panel and action in ("undone", "redone", "loaded", "deleted"):
            mgr = self.image_display_panel.annotation_manager
            sel_id = mgr.selected_annotation
            if sel_id:
                ann = mgr.get_annotation(sel_id)
                self.attribute_panel.set_annotation(ann)
            else:
                self.attribute_panel.set_annotation(None)

    def _on_attribute_panel_changed(self, annotation_id: str, changes: Dict[str, Any]):
        """Handle changes from the AttributePanel.

        Args:
            annotation_id: The ID of the annotation being edited.
            changes: Dict of changed fields (transcription, flags, or _attrs_replaced marker).
        """
        mgr = self.image_display_panel.annotation_manager
        if "_attrs_replaced" in changes:
            # Attributes were directly replaced on the annotation object by the panel
            pass
        else:
            mgr.update_annotation(annotation_id, changes)

        self._save_annotation_for_current_image()

        # Refresh annotation list if transcription changed (affects display label)
        if "transcription" in changes:
            self._update_annotation_list()

    def _on_selection_changed(self, annotation_id: Optional[str]):
        """Selection changed Callback"""
        # Find index of annotation
        index = -1
        if annotation_id:
            annotations = self.image_display_panel.get_annotations()
            for i, ann in enumerate(annotations):
                if ann.id == annotation_id:
                    index = i
                    break
        
        
        # Update selection state in list (prevent recursion)
        self._suppress_selection_event = True
        try:
            if index != -1:
                # Check if already selected to avoid redundant event even without suppression
                if not self.annotation_list.IsSelected(index):
                    self.annotation_list.Select(index)
                    self.annotation_list.EnsureVisible(index)
                
                # Deselect others
                count = self.annotation_list.GetItemCount()
                for i in range(count):
                    if i != index and self.annotation_list.IsSelected(i):
                        self.annotation_list.Select(i, False)
            else:
                # Deselect all
                curr_sel = self.annotation_list.GetFirstSelected()
                while curr_sel != -1:
                    self.annotation_list.Select(curr_sel, False)
                    curr_sel = self.annotation_list.GetNextSelected(curr_sel)
        finally:
            self._suppress_selection_event = False
            
        # Update attribute panel
        if self.attribute_panel:
            if annotation_id:
                ann = self.image_display_panel.annotation_manager.get_annotation(annotation_id)
                self.attribute_panel.set_annotation(ann)
            else:
                self.attribute_panel.set_annotation(None)

        # Update toolbar button state
        if self.toolbar:
            is_editing = (annotation_id is not None)
            self.toolbar.set_operation_button_mode("add", is_editing)
            
            # Disable Undo/Redo AND all tools during editing
            self.toolbar.enable_operation("undo", not is_editing)
            self.toolbar.enable_operation("redo", not is_editing)
            self.toolbar.enable_all_tools(not is_editing)
            
            # Also sync menu bar state
            menu_bar = self.GetMenuBar()
            if menu_bar:
                menu_bar.Enable(wx.ID_UNDO, not is_editing)
                menu_bar.Enable(wx.ID_REDO, not is_editing)
                
                # Disable individual tool menu items
                menu_bar.Enable(self.id_tool_rectangle, not is_editing)
                menu_bar.Enable(self.id_tool_line, not is_editing)
                menu_bar.Enable(self.id_tool_polygon, not is_editing)
                menu_bar.Enable(self.id_tool_circle, not is_editing)
                menu_bar.Enable(self.id_tool_annulus, not is_editing)
                menu_bar.Enable(self.id_tool_point, not is_editing)
                menu_bar.Enable(self.id_tool_select, not is_editing)
    
    def _on_status_update(self, message: str):
        """Status update"""
        self._update_status(message)
    
    def _on_tool_rectangle(self, event):
        """矩形工具菜單"""
        self.toolbar.set_current_tool("rectangle")

    def _on_tool_line(self, event):
        """直線工具菜單"""
        self.toolbar.set_current_tool("line")
    
    def _on_tool_polygon(self, event):
        """多邊形工具菜單"""
        self.toolbar.set_current_tool("polygon")
    
    def _on_tool_circle(self, event):
        """圓形工具菜單"""
        self.toolbar.set_current_tool("circle")
    
    def _on_tool_annulus(self, event):
        """環形工具菜單"""
        self.toolbar.set_current_tool("annulus")
    
    def _on_tool_point(self, event):
        """點標註工具菜單"""
        self.toolbar.set_current_tool("point")
    
    def _on_tool_select(self, event):
        """選擇工具菜單"""
        self.toolbar.set_current_tool("select")
    
    def _on_zoom_in(self, event):
        """放大"""
        self.image_display_panel._on_zoom_in(event)
    
    def _on_zoom_out(self, event):
        """縮小"""
        self.image_display_panel._on_zoom_out(event)
    
    def _on_zoom_fit(self, event):
        """適合視窗"""
        self.image_display_panel._on_zoom_fit(event)
    
    def _on_prev_image(self, event):
        """Previous image"""
        try:
            if self.current_image_index > 0:
                self.current_image_index -= 1
                self._load_current_image()
                self._update_status(_("Switched to image {}").format(self.current_image_index + 1))
            else:
                self._update_status(_("Already at the first image"))
        except Exception as e:
            wx.MessageBox(_("Failed to switch image: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"切換圖片失敗: {e}")
    
    def _on_next_image(self, event):
        """Next image"""
        try:
            if hasattr(self, 'image_files') and hasattr(self, 'current_image_index'):
                if self.current_image_index < len(self.image_files) - 1:
                    self.current_image_index += 1
                    self._load_current_image()
                    self._update_status(_("Switched to image {}").format(self.current_image_index + 1))
                else:
                    self._update_status(_("Already at the last image"))
            else:
                self._update_status(_("No images loaded"))
        except Exception as e:
            wx.MessageBox(_("Failed to switch image: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"切換圖片失敗: {e}")
    
    def _load_current_image(self):
        """Load currently selected image"""
        print(f"🔄 _load_current_image called")
        print(f"📍 Current image index: {getattr(self, 'current_image_index', 'N/A')}")
        print(f"📁 Image files: {len(getattr(self, 'image_files', []))} files")
        
        if hasattr(self, 'image_files') and hasattr(self, 'current_image_index'):
            if 0 <= self.current_image_index < len(self.image_files):
                image_path = self.image_files[self.current_image_index]
                print(f"🖼️  Preparing to load image: {image_path}")
                
                # [Safety] Disable auto-save on switch for now to avoid overwriting original data during debugging
                # if self.current_image_path and self.current_image_path != image_path:
                #     print("💾 Saving current annotations...")
                #     self._save_annotation_for_current_image()
                
                # Load new image
                print(f"🔄 Calling image_display_panel.load_image...")
                if self.image_display_panel:
                    success = self.image_display_panel.load_image(image_path)
                    print(f"📊 Load result: {success}")
                else:
                    print("❌ image_display_panel is None")
                    success = False
                    
                self.current_image_path = image_path
                
                # Load corresponding annotation file
                if success:
                    print("📋 Loading annotation file...")
                    self._load_annotation_for_current_image()

                    # Update display
                    print("🔄 Updating annotation and file lists...")
                    self._update_annotation_list()
                    self._update_file_list()
                    self._update_image_info(image_path, self.current_image_index, len(self.image_files))
                    print("✅ Image load complete")
                else:
                    print("❌ Image load failed")
            else:
                print(f"❌ Invalid image index: {self.current_image_index}")
        else:
            print("❌ Missing required attributes")
    
    def _on_edit_annotation(self, event):
        """編輯標註"""
        try:
            # 獲取選中的標註
            selected_annotation_id = self.image_display_panel.selected_annotation_id
            if not selected_annotation_id:
                wx.MessageBox(_("Please select an annotation to edit"), _("Hint"), wx.OK | wx.ICON_INFORMATION)
                return
            
            # 獲取標註管理器
            annotation_manager = self.image_display_panel.get_annotation_manager()
            annotations = annotation_manager.get_all_annotations()
            

            selected_annotation = None
            for ann in annotations:
                if ann.id == selected_annotation_id:
                    selected_annotation = ann
                    break
            
            if not selected_annotation:
                wx.MessageBox(_("Selected annotation not found"), _("Error"), wx.OK | wx.ICON_ERROR)
                return
            
            # 創建編輯對話框
            dialog = wx.Dialog(self, title=_("Edit Annotation"), size=(300, 200))
            sizer = wx.BoxSizer(wx.VERTICAL)
            
            # 類別選擇
            category_label = wx.StaticText(dialog, wx.ID_ANY, _("Category:"))
            sizer.Add(category_label, 0, wx.ALL, 5)
            
            categories = self.category_manager.get_ordered_categories()
            category_choice = wx.Choice(dialog, wx.ID_ANY, choices=categories)
            category_choice.SetStringSelection(selected_annotation.label)
            sizer.Add(category_choice, 0, wx.ALL | wx.EXPAND, 5)
            
            # 按鈕
            button_sizer = wx.BoxSizer(wx.HORIZONTAL)
            btn_ok = wx.Button(dialog, wx.ID_OK, _("OK"))
            btn_cancel = wx.Button(dialog, wx.ID_CANCEL, _("Cancel"))
            button_sizer.Add(btn_ok, 0, wx.ALL, 5)
            button_sizer.Add(btn_cancel, 0, wx.ALL, 5)
            
            sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 10)
            dialog.SetSizer(sizer)
            
            # 顯示對話框
            if dialog.ShowModal() == wx.ID_OK:
                # 更新標註類別
                new_category = category_choice.GetStringSelection()
                selected_annotation.label = new_category
                selected_annotation.category = new_category
                selected_annotation.color = self.category_manager.get_color(new_category)
                
                # 更新顯示
                self._update_annotation_list()
                self.image_display_panel.Refresh()
                
                self._update_status(_("Label updated to: {}").format(new_category))
            
            dialog.Destroy()
            
        except Exception as e:
            wx.MessageBox(_("Failed to edit annotation: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"Failed to edit annotation: {e}")
    
    def _on_delete_annotation(self, event):
        """刪除標註按鈕"""
        try:
            selected_annotation_id = self.image_display_panel.selected_annotation_id
            if not selected_annotation_id:
                wx.MessageBox(_("Please select an annotation to delete"), _("Hint"), wx.OK | wx.ICON_INFORMATION)
                return
            
            result = wx.MessageBox(_("Are you sure you want to delete the selected annotation?"), _("Confirm"), wx.YES_NO | wx.ICON_QUESTION)
            if result == wx.YES:
                success = self.image_display_panel.delete_selected_annotation()
                if success:
                    self._update_annotation_list()
                    self._update_status(_("Annotation Deleted"))
                else:
                    wx.MessageBox(_("Failed to delete annotation"), _("Error"), wx.OK | wx.ICON_ERROR)
            
        except Exception as e:
            wx.MessageBox(_("Failed to delete annotation: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"Failed to delete annotation: {e}")
    
    def _on_toggle_visibility(self, event):
        """Toggle annotation visibility"""
        try:
            selected_annotation_id = self.image_display_panel.selected_annotation_id
            if not selected_annotation_id:
                wx.MessageBox(_("Please select an annotation to toggle visibility"), _("Hint"), wx.OK | wx.ICON_INFORMATION)
                return
            
            annotation_manager = self.image_display_panel.get_annotation_manager()
            annotations = annotation_manager.get_all_annotations()
            
            for ann in annotations:
                if ann.id == selected_annotation_id:
                    ann.visible = not ann.visible
                    status_text = _("Shown") if ann.visible else _("Hidden")
                    self._update_status(_("Annotation {}").format(status_text))
                    break
            
            self._update_annotation_list()
            self.image_display_panel.sync_overlays()
            self.image_display_panel.Refresh()
            
            status_text = _("Shown") if ann.visible else _("Hidden")
            self._update_status(_("Annotation {}").format(status_text))
            
        except Exception as e:
            wx.MessageBox(_("Failed to toggle visibility: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"Failed to toggle visibility: {e}")
    
    def _on_annotation_selected(self, event):
        """Annotation list item selected"""
        if getattr(self, '_suppress_selection_event', False):
            return

        item_index = event.GetIndex()
        annotations = self.image_display_panel.get_annotations()
        
        if 0 <= item_index < len(annotations):
            annotation = annotations[item_index]
            print(f"📌 List selection: index={item_index}, id={annotation.id}")
            self.image_display_panel.select_annotation(annotation.id)
        else:
            print(f"⚠️ Invalid selection index: {item_index}")
    
    def _on_file_selected(self, event):
        """File selected in list"""
        try:
            print(f"📋 File list click event triggered")
            
            # Anti-reentry check
            if getattr(self, '_processing_file_selection', False):
                print("⚠️  Already processing selection, skipping duplicate event")
                return
            
            if not self.file_navigation_enabled:
                print("⚠️  File navigation not enabled")
                return
                
            # Set processing state
            self._processing_file_selection = True
            
            try:
                item_index = event.GetIndex()
                print(f"📍 Selected item index: {item_index}")
                
                # 獲取選中的文件信息
                if hasattr(self, 'image_files') and 0 <= item_index < len(self.image_files):
                    selected_file_path = self.image_files[item_index]
                    print(f"📁 選中文件: {selected_file_path}")
                    
                    # 檢查是否與當前文件相同
                    if hasattr(self, 'current_image_path') and self.current_image_path == selected_file_path:
                        print(f"ℹ️  選擇的是當前圖片，跳過重複載入")
                        return
                    
                    print(f"🔄 切換到圖片: {Path(selected_file_path).name}")
                    
                    # 保存當前圖片的標註
                    if self.current_image_path:
                        print("💾 保存當前圖片標註...")
                        self._save_annotation_for_current_image()
                    
                    # 設置新的當前圖片索引
                    self.current_image_index = item_index
                    print(f"📍 更新圖片索引: {item_index}")
                    
                    # 載入新圖片
                    print(f"🖼️  載入新圖片...")
                    self._load_current_image()
                    
                    # Update status
                    self._update_status(f"Switched to: {Path(selected_file_path).name}")
                    
                    print(f"✓ File switch success: {selected_file_path}")
                else:
                    print(f"❌ Invalid file index or empty list")
                    if not hasattr(self, 'image_files'):
                        print("❌ image_files attribute missing")
                    elif item_index >= len(self.image_files):
                        print(f"❌ Index out of range: {item_index} >= {len(self.image_files)}")
            
            finally:
                # 確保處理狀態被清除
                self._processing_file_selection = False
            
        except Exception as e:
            print(f"文件列表選擇失敗: {e}")
            import traceback
            traceback.print_exc()
            # 確保即使出錯也清除處理狀態
            self._processing_file_selection = False
            wx.MessageBox(f"切換圖片失敗: {e}", "錯誤", wx.OK | wx.ICON_ERROR)
    
    def _on_key_down(self, event):
        """鍵盤按下事件"""
        # If focus is on a TextCtrl, let it handle typing normally
        focused = wx.Window.FindFocus()
        if isinstance(focused, wx.TextCtrl):
            event.Skip()
            return

        key_code = event.GetKeyCode()
        modifiers = event.GetModifiers()

        # 處理特殊快捷鍵
        if key_code == ord('Q') and modifiers == wx.MOD_CONTROL:
            self._on_exit(None)
        elif key_code == ord('S') and modifiers == wx.MOD_CONTROL:
            self._on_file_save(None)
        elif key_code == ord('O') and modifiers == wx.MOD_CONTROL:
            self._on_file_open(None)
        elif key_code == wx.WXK_DELETE:
            self._on_delete_annotation(None)
        elif key_code == wx.WXK_RETURN:
            # If in AI mode or creating ROI, Enter confirms the action
            if self.toolbar.get_current_tool().startswith("ai_") or \
               self.image_display_panel.is_creating_annotation:
                self.image_display_panel.add_active_roi()
            else:
                # Normal mode: Edit transcription on Enter
                self._on_edit_transcription(None)

        
        event.Skip()
    
    def _on_close(self, event):
        """窗口關閉事件"""
        print("🚪 Closing wxCvAnnotator...")
        
        # 進行清理
        if self.image_display_panel:
            self.image_display_panel.cleanup()
            
        # 銷毀窗口
        self.Destroy()
        
        # 確保進程結束 (在某些包含 C++ 組件的情況下可能需要)
        print("✅ Cleanup complete, exiting.")
        # event.Skip()  # 如果手動 Destroy 且想結束進程，通常不需要 Skip 除非有其他 handler
    
    def _on_toggle_embed_base64(self, event):
        """Toggle Base64 embedding setting"""
        is_checked = event.IsChecked()
        self.settings_manager.set("embed_base64", is_checked)
        status = _("Enabled") if is_checked else _("Disabled")
        self._update_status(_("Base64 Embedding: {}").format(status))

    def _on_exit(self, event):
        """退出程序"""
        self.Close()
    
    # 輔助方法
    def _load_folder_images(self, folder_path: str):
        """Load images from folder"""
        try:
            from pathlib import Path
            
            # Supported image formats
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp', '.j2k', '.jp2', '.heic', '.jxl'}
            
            # Scan folder for images (using a set to avoid duplicates on case-insensitive systems)
            image_files_set = set()
            folder = Path(folder_path)
            
            for ext in image_extensions:
                # On Windows, glob is case-insensitive, so we collect and unique
                image_files_set.update(folder.glob(f'*{ext}'))
                image_files_set.update(folder.glob(f'*{ext.upper()}'))
            
            if not image_files_set:
                wx.MessageBox(_("No image files found in folder\n{}").format(folder_path), _("Hint"), wx.OK | wx.ICON_INFORMATION)
                return
            
            # Convert to list and sort
            image_files = sorted(list(image_files_set))
            
            # Set navigation state
            self.project_folder = folder_path
            self.settings_manager.last_folder = folder_path
            self.image_files = [str(f) for f in image_files]
            self.current_image_index = 0
            self.file_navigation_enabled = True
            
            # Load first image
            if self.image_files:
                # 1. Try to load labels for the folder
                self._load_labels_for_folder(folder_path)
                
                self._load_current_image()
                self._update_status(_("Loaded folder: {} ({} images)").format(folder.name, len(image_files)))
                self._update_file_list()
            
        except Exception as e:
            wx.MessageBox(_("Failed to load folder: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"載入文件夾失敗: {e}")
    
    def _update_file_list(self):
        """更新文件列表"""
        if not self.file_list or not self.file_navigation_enabled:
            return
        
        try:
            if not getattr(self, 'image_files', None):
                self.file_list.DeleteAllItems()
                self._update_navigation_buttons()
                return
            
            # Get theme colors
            theme = self.theme_manager.get_current_theme()
            bg_normal = wx.NullColour
            bg_selected = wx.Colour(100, 100, 200) # Default blue
            
            if theme:
                bg_normal = wx.Colour(theme.bg_list)
                bg_selected = wx.Colour(theme.bg_item_hover)
            
            # Use incremental update if list count matches
            curr_count = self.file_list.GetItemCount()
            img_count = len(self.image_files)
            
            if curr_count == img_count:
                for i in range(img_count):
                    # Only update current index and others that might have changed
                    # For simplicity, update all visible text/status
                    image_path = self.image_files[i]
                    annotation_count, status = self._peek_annotation_info(image_path)
                    
                    self.file_list.SetItem(i, 1, str(annotation_count))
                    self.file_list.SetItem(i, 2, status)
                    
                    # Highlight current
                    if i == self.current_image_index:
                        self.file_list.SetItemBackgroundColour(i, bg_selected)
                        self.file_list.SetItemState(i, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, 
                                                   wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
                    else:
                        # Reset background for others
                        self.file_list.SetItemBackgroundColour(i, bg_normal)
                        self.file_list.SetItemState(i, 0, wx.LIST_STATE_SELECTED)
                
                self.file_list.EnsureVisible(self.current_image_index)
                self.file_list.Refresh()
                self._update_navigation_buttons()
                return

            # Fallback: Full rebuild only if count differs
            self.file_list.DeleteAllItems()
            
            for i, image_path in enumerate(self.image_files):
                path = Path(image_path)
                annotation_count, status = self._peek_annotation_info(image_path)
                
                index = self.file_list.InsertItem(i, path.name)
                self.file_list.SetItem(index, 1, str(annotation_count))
                self.file_list.SetItem(index, 2, status)
                
                if i == self.current_image_index:
                    self.file_list.SetItemBackgroundColour(index, bg_selected)
                    self.file_list.SetItemState(index, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, 
                                               wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
                else:
                    self.file_list.SetItemBackgroundColour(index, bg_normal)
            self.file_list.EnsureVisible(self.current_image_index)
            self.file_list.Refresh()
            self._update_navigation_buttons()
            
        except Exception as e:
            print(f"更新文件列表失敗: {e}")
            import traceback
            traceback.print_exc()

    def _peek_annotation_info(self, image_path: str) -> Tuple[int, str]:
        """快速獲取標註數量與狀態 (不影響當前 manager)"""
        import json
        from typing import Tuple
        try:
            path = Path(image_path)
            json_path = path.with_suffix('.json')
            if not json_path.exists():
                return 0, _("None")
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            count = 0
            if "annotations" in data:
                count = len(data["annotations"])
            elif "shapes" in data:
                count = len(data["shapes"])
                
            status = data.get("status", "None")
            return count, status
        except:
            return 0, "Error"

    def _on_label_list_right_click(self, event):
        """Handle label list context menu"""
        menu = wx.Menu()
        add_item = menu.Append(wx.ID_ANY, _("Add Category..."))
        edit_item = menu.Append(wx.ID_ANY, _("Edit Category..."))
        del_item = menu.Append(wx.ID_ANY, _("Delete Selected Category"))
        
        self.Bind(wx.EVT_MENU, self._on_add_category_dialog, add_item)
        self.Bind(wx.EVT_MENU, self._on_edit_category_action, edit_item)
        self.Bind(wx.EVT_MENU, self._on_delete_category_action, del_item)
        
        self.label_list.PopupMenu(menu)
        menu.Destroy()

    def _on_add_category_dialog(self, event):
        """Show dialog to add new category with color selection"""
        dlg = CategoryEditDialog(self, _("Add Category"), is_edit=False)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.get_category_name()
            color = dlg.get_category_color()
            
            if name:
                success = self.category_manager.add_category(name, color)
                if success:
                    self._refresh_label_list_ui()
                    self._update_status(_("Category added: {}").format(name))
                else:
                    wx.MessageBox(_("Category '{}' already exists").format(name), _("Error"), wx.OK | wx.ICON_ERROR)
        dlg.Destroy()

    def _on_edit_category_action(self, event):
        """Edit category name and color with batch rename option"""
        old_name = self.label_list.GetStringSelection()
        if not old_name:
            wx.MessageBox(_("Please select a category to edit"), _("Hint"), wx.OK | wx.ICON_INFORMATION)
            return
            
        old_color = self.category_manager.get_color(old_name)
        dlg = CategoryEditDialog(self, _("Edit Category"), is_edit=True, 
                               category_name=old_name, color=old_color)
        
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.get_category_name()
            new_color = dlg.get_category_color()
            
            if not new_name:
                wx.MessageBox(_("Category name cannot be empty"), _("Error"), wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return

            # Update Category Manager (Always, even if only color changed)
            self.category_manager.update_category(old_name, new_name, new_color)

            # If name changed, handle batch rename
            if new_name != old_name:
                msg = _("You are renaming category '{}' to '{}'.\n\n"
                        "Do you want to update all existing annotation files in this folder?\n\n"
                        "Yes: Update ALL files in folder\n"
                        "No: Update only the category list\n"
                        "Cancel: Abort changes").format(old_name, new_name)
                
                choice_dlg = wx.MessageDialog(self, msg, _("Rename Confirmation"), 
                                            wx.YES_NO | wx.CANCEL | wx.ICON_WARNING | wx.CENTRE)
                choice_dlg.SetYesNoCancelLabels(_("Update All"), _("List Only"), _("Cancel"))
                
                result = choice_dlg.ShowModal()
                choice_dlg.Destroy()
                
                if result == wx.ID_CANCEL:
                    dlg.Destroy()
                    return
                
                # Handled already relative to batch rename dialog
                if result == wx.ID_YES:
                    count = self._batch_rename_category(old_name, new_name)
                    self._update_status(_("Renamed '{}' to '{}' in {} files").format(old_name, new_name, count))
                else:
                    self._update_status(_("Renamed '{}' to '{}' in list only").format(old_name, new_name))
            else:
                # Color changed only
                self._update_status(_("Updated color for Category: {}").format(new_name))
            
            # Update current memory annotations (IMPORTANT: Sync both label and color)
            annotation_manager = self.image_display_panel.get_annotation_manager()
            for ann in annotation_manager.get_all_annotations():
                # If name changed, old_name items must become new_name. 
                # If name didn't change, we still update color.
                if ann.category == old_name:
                    ann.category = new_name
                    ann.label = new_name
                    ann.color = new_color
                elif ann.category == new_name:
                    # In case it was already new_name but color changed
                    ann.color = new_color
            
            self._refresh_label_list_ui()
            self._update_annotation_list() # Sync color/labels in list
            self.image_display_panel.Refresh()
            
        dlg.Destroy()

    def _batch_rename_category(self, old_name: str, new_name: str) -> int:
        """Batch rename category in use in all JSON files in the current folder"""
        if not self.project_folder:
            return 0
            
        count = 0
        import json
        folder = Path(self.project_folder)
        
        for json_file in folder.glob("*.json"):
            if json_file.name == "labels.json": continue # Skip config file
            
            try:
                changed = False
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle internal format
                if "annotations" in data:
                    for ann in data["annotations"]:
                        if ann.get("category") == old_name:
                            ann["category"] = new_name
                            changed = True
                
                # Handle LabelMe format
                if "shapes" in data:
                    for shape in data["shapes"]:
                        if shape.get("label") == old_name:
                            shape["label"] = new_name
                            changed = True
                            
                if changed:
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    count += 1
            except Exception as e:
                print(f"Failed to process {json_file.name}: {e}")
                
        return count

    def _on_delete_category_action(self, event):
        selection = self.label_list.GetStringSelection()
        if not selection:
            return
            
        if wx.MessageBox(_("Are you sure you want to delete category '{}'?").format(selection), 
                        _("Confirm Delete"), wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            if self.category_manager.remove_category(selection):
                self._refresh_label_list_ui()
                self._update_status(_("Category deleted: {}").format(selection))
            else:
                wx.MessageBox(_("Cannot delete default category '{}'").format(selection), 
                             _("Constraint"), wx.OK | wx.ICON_WARNING)

    def _on_file_list_key_down(self, event):
        """Handle keyboard navigation in file list"""
        # Let default ListCtrl handle UP/DOWN navigation
        # We respond to EVT_LIST_ITEM_SELECTED to load the image
        event.Skip()

    def _on_file_list_right_click(self, event):
        """文件列表右鍵菜單 (設置 Status)"""
        item_index = event.GetIndex()
        if item_index == -1:
            return
            
        menu = wx.Menu()
        statuses = ["None", "train", "val", "test"]
        
        for status in statuses:
            item = menu.Append(wx.ID_ANY, f"Set Status: {status}")
            self.Bind(wx.EVT_MENU, lambda evt, s=status, idx=item_index: self._set_image_status(idx, s), item)
            
        menu.AppendSeparator()
        del_item = menu.Append(wx.ID_ANY, _("Delete Annotation File"))
        self.Bind(wx.EVT_MENU, lambda evt, idx=item_index: self._on_delete_annotation_file(idx), del_item)
            
        self.PopupMenu(menu)
        menu.Destroy()

    def _on_delete_annotation_file(self, item_index):
        """刪除選定圖片的 .json 標註文件並更新介面"""
        if item_index < 0 or item_index >= len(self.image_files):
            return
            
        image_path = self.image_files[item_index]
        json_path = Path(image_path).with_suffix('.json')
        
        if not json_path.exists():
            # wx.MessageBox(_("No annotation file found for this image."), _("Info"), wx.OK | wx.ICON_INFORMATION)
            return
            
        confirm = wx.MessageBox(
            _("Are you sure you want to delete the annotation file for '{}'?\nThis action cannot be undone.").format(json_path.name),
            _("Confirm Deletion"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
        )
        
        if confirm != wx.YES:
            return
            
        try:
            # 1. 物理刪除檔案
            os.remove(json_path)
            print(f"🗑️ Deleted annotation file: {json_path}")
            
            # 2. 如果刪除的是「當前」顯示的圖片，需要重置顯示面板
            if item_index == self.current_image_index:
                if self.image_display_panel:
                    # 清空目前的標註管理器
                    self.image_display_panel.get_annotation_manager().clear_all()
                    # 重置 C++ ROI 編輯器狀態
                    self.image_display_panel.select_annotation(None)
                    # 同步 UI 顯示
                    self.image_display_panel.sync_overlays()
                    self._update_annotation_list()
            
            # 3. 更新文件列表中的 Count 與 Status
            self._update_file_list()
            
            self._update_status(_("Deleted annotation file for: {}").format(Path(image_path).name))
            
        except Exception as e:
            print(f"❌ Failed to delete annotation file: {e}")
            wx.MessageBox(_("Failed to delete annotation file: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)

    def _set_image_status(self, item_index, status):
        """設置圖片標註狀態並保存"""
        import json
        if item_index < 0 or item_index >= len(self.image_files):
            return
            
        image_path = self.image_files[item_index]
        json_path = Path(image_path).with_suffix('.json')
        
        # 如果是當前編輯的圖片，直接更新 manager
        if item_index == self.current_image_index:
            if self.image_display_panel:
                manager = self.image_display_panel.get_annotation_manager()
                manager.current_status = status
                # 自動保存一次以確保狀態持久化
                self._on_file_save(None)
                self._update_file_list()
                return

        # 否則，讀取、修改、保存
        try:
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data["status"] = status
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            else:
                # 建立空的標註文件僅包含 status
                data = {
                    "version": "2.0",
                    "shapes": [],
                    "status": status,
                    "imagePath": Path(image_path).name,
                    "imageData": None
                }
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            
            self._update_file_list()
            self._update_status(f"Updated status for {Path(image_path).name} to {status}")
        except Exception as e:
            wx.MessageBox(f"Failed to update status: {e}", "Error", wx.OK | wx.ICON_ERROR)
    
    def _update_navigation_buttons(self):
        """更新導航按鈕狀態"""
        if hasattr(self, 'btn_prev') and hasattr(self, 'btn_next'):
            # 啟用/禁用導航按鈕
            if self.btn_prev:
                self.btn_prev.Enable(self.current_image_index > 0)
            if self.btn_next:
                self.btn_next.Enable(self.current_image_index < len(self.image_files) - 1)
    
    def _load_annotation_for_current_image(self):
        """載入當前圖片的標註"""
        if not self.image_files or self.current_image_index >= len(self.image_files):
            return
        
        current_image = self.image_files[self.current_image_index]
        annotation_path = Path(current_image).with_suffix('.json')
        
        if annotation_path.exists():
            try:
                # 載入標註文件
                success = self.image_display_panel.load_annotations(str(annotation_path))
                if success:
                    # Sync colors with current category manager
                    annotations = self.image_display_panel.get_annotations()
                    for ann in annotations:
                        ann.color = self.category_manager.get_color(ann.category)
                        
                    self._update_status(f"已載入標註: {annotation_path.name}")
                else:
                    self._update_status("標註載入失敗")
            except Exception as e:
                print(f"載入標註失敗: {e}")
                self._update_status("標註載入失敗")
    
    def _save_annotation_for_current_image(self):
        """保存當前圖片的標註"""
        if not self.image_files or self.current_image_index >= len(self.image_files):
            return
        
        current_image = self.image_files[self.current_image_index]
        annotation_path = Path(current_image).with_suffix('.json')
        
        try:
            success = self.image_display_panel.save_annotations(str(annotation_path))
            if success:
                self._update_status(f"已保存標註: {annotation_path.name}")
            else:
                self._update_status("標註保存失敗")
        except Exception as e:
            print(f"保存標註失敗: {e}")
            self._update_status("標註保存失敗")
    
    def _update_annotation_list(self):
        """Update annotation list"""
        # Clear list
        self.annotation_list.DeleteAllItems()
        
        # Get annotations
        annotations = self.image_display_panel.get_annotations()
        
        # Add to list
        for i, annotation in enumerate(annotations):
            index = self.annotation_list.InsertItem(i, str(i + 1))
            
            # Show transcription if available, otherwise category
            display_label = annotation.category
            if annotation.transcription:
                display_label = f"{annotation.category}: {annotation.transcription}"
                
                
            self.annotation_list.SetItem(index, 1, display_label)
            self.annotation_list.SetItem(index, 2, annotation.type)
            
            # Visibility emoji
            vis_text = "👁️" if annotation.visible else "❌"
            self.annotation_list.SetItem(index, 3, vis_text)

        
        # Update status bar
        self.status_bar.SetStatusText(f"Count: {len(annotations)}", 2)

    def _on_edit_transcription(self, event):
        """Open floating editor for transcription"""
        # Get selected annotation
        if not self.image_display_panel:
            return
            
        selected_id = self.image_display_panel.get_selected_annotation_id()
        if not selected_id:
            # If nothing selected, maybe check list
            list_idx = self.annotation_list.GetFirstSelected()
            if list_idx != -1:
                annotations = self.image_display_panel.get_annotations()
                if list_idx < len(annotations):
                    selected_id = annotations[list_idx].id
        
        if not selected_id:
            return
            
        # Get annotation object
        anno = self.image_display_panel.get_annotation_by_id(selected_id)
        if not anno:
            return
            
        # Show popup
        popup = TextEditPopup(self, initial_text=anno.transcription)
        popup.CenterOnParent()
        
        if popup.ShowModal() == wx.ID_OK:
            new_text = popup.get_value()
            if new_text != anno.transcription:
                print(f"📝 Updating transcription: {new_text}")
                anno.transcription = new_text
                anno.source = "manual"
                anno.modified_time = datetime.now()

                # Notify panel to refresh
                self.image_display_panel.Refresh()
                self._update_annotation_list()
                self._save_annotation_for_current_image()
                self._update_status(f"Updated transcription: {new_text}")

                # Sync attribute panel if active
                if self.attribute_panel:
                    self.attribute_panel.set_annotation(anno)

        popup.Destroy()

    
    def _on_pos_update(self, x: float, y: float):
        """Update cursor position + RGB pixel value in status bar (field 3)."""
        ix, iy = int(x), int(y)
        text = f"X:{ix}  Y:{iy}"
        mat = self.image_display_panel.current_image_mat
        if mat is not None:
            h, w = mat.shape[:2]
            if 0 <= iy < h and 0 <= ix < w:
                px = mat[iy, ix]  # always BGR after normalisation
                b, g, r = int(px[0]), int(px[1]), int(px[2])
                text += f"  R:{r} G:{g} B:{b}"
        self.status_bar.SetStatusText(text, 3)

    def _update_image_info(self, image_path: str, image_index: int = -1, total_images: int = 0):
        """Update window title and image-size field after a successful image load.

        Args:
            image_path: Path to the loaded image.
            image_index: 0-based index within the folder (omit for single-file mode).
            total_images: Total images in the folder (omit for single-file mode).
        """
        abs_path = str(Path(image_path).resolve())
        if image_index >= 0 and total_images > 0:
            self.SetTitle(f"wxCvAnnotator - {abs_path} [{image_index + 1}/{total_images}]")
        else:
            self.SetTitle(f"wxCvAnnotator - {abs_path}")
        # Field 4 → W × H × C (use original channel count before BGR normalisation)
        mat = self.image_display_panel.current_image_mat
        if mat is not None:
            h, w = mat.shape[:2]
            c = self.image_display_panel.current_image_channels or 3
            self.status_bar.SetStatusText(f"{w}×{h}×{c}", 4)
        else:
            self.status_bar.SetStatusText("", 4)

    def _update_status(self, message: str):
        """Update status bar"""
        self.status_bar.SetStatusText(message, 0)
        
        # Update tool state
        tool = self.toolbar.get_current_tool()
        tool_names = {
            "rectangle": "Rect", "polygon": "Poly", "circle": "Circle",
            "point": "Point", "brush": "Brush", "select": "Select"
        }
        tool_name = tool_names.get(tool, tool)
        self.status_bar.SetStatusText(f"Tool: {tool_name}", 1)
    
    def _on_manage_categories(self, event):
        """Manage categories"""
        try:
            from .annotation_system import CategoryManager
            
            # Create category manager
            if not hasattr(self, 'category_manager'):
                self.category_manager = CategoryManager()
            
            # Create dialog
            dialog = CategoryManagementDialog(self, self.category_manager)
            
            if dialog.ShowModal() == wx.ID_OK:
                # Update current categories
                categories = self.category_manager.get_all_categories()
                
                # Update colors for existing annotations
                annotations = self.image_display_panel.get_annotations()
                for ann in annotations:
                    ann.color = self.category_manager.get_color(ann.category)
                
                # Refresh display
                self._refresh_label_list_ui()
                self._update_annotation_list()
                self.image_display_panel.Refresh()
                
                self._update_status(_("Categories updated"))
            
            dialog.Destroy()
            
        except Exception as e:
            wx.MessageBox(f"類別管理失敗: {e}", "錯誤", wx.OK | wx.ICON_ERROR)
            print(f"類別管理失敗: {e}")
    
    # Removed _on_export_current at user request (single image export no longer used)
    
    def _on_batch_export(self, event):
        """批量導出"""
        if not self.export_system:
            wx.MessageBox("導出系統未初始化", "錯誤", wx.OK | wx.ICON_ERROR)
            return
        
        if not self.image_files:
            wx.MessageBox("沒有圖像文件可以導出", "提示", wx.OK | wx.ICON_INFORMATION)
            return
        
        # Prepare image dimensions (0,0 triggers auto-detection in ExportSystem)
        image_dimensions = [(0, 0)] * len(self.image_files)
        
        # 創建批量導出對話框
        dialog = BatchExportDialog(self, self.export_system, self.image_files, image_dimensions)
        
        if dialog.ShowModal() == wx.ID_OK:
            # 批量導出在對話框內處理
            pass
        
    def _on_export_dataset_split(self, event):
        """Advanced dataset splitting and export"""
        if not self.image_files:
            wx.MessageBox(_("No images loaded to export"), _("Information"), wx.OK | wx.ICON_INFORMATION)
            return
            
        dialog = AdvancedExportDialog(self, self.image_files)
        if dialog.ShowModal() == wx.ID_OK:
            settings = dialog.get_settings()
            
            # Show progress
            progress = wx.ProgressDialog(
                _("Generating Dataset..."),
                _("Processing splitting and export formats"),
                maximum=len(self.image_files),
                parent=self,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_SMOOTH
            )
            
            try:
                # Prepare image dimensions
                image_dimensions = [(0, 0)] * len(self.image_files)
                
                # Execute in ExportSystem
                results = self.export_system.batch_export_advanced(
                    settings, 
                    self.image_files, 
                    image_dimensions,
                    progress_callback=lambda idx, msg: progress.Update(idx, msg)
                )
                
                success_count = sum(1 for v in results.values() if v)
                wx.MessageBox(
                    _("Dataset Export Complete!\nTarget: {}\nSuccessfully exported {}/{} images.").format(
                        settings["output_dir"], success_count, len(self.image_files)),
                    _("Success"), wx.OK | wx.ICON_INFORMATION
                )
            except Exception as e:
                wx.MessageBox(f"Export failed: {e}", _("Error"), wx.OK | wx.ICON_ERROR)
            finally:
                progress.Destroy()
                
        dialog.Destroy()
    
    def _on_export_formats(self, event):
        """Show supported export formats"""
        if not self.export_system:
            wx.MessageBox("Export system not initialized", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        formats = self.export_system.get_supported_formats()
        
        # Create info dialog
        info = _("Supported Export Formats:") + "\n\n"
        info += f"• YOLO: {_('Detection (BBox), Segmentation (Polygon), and OBB (Rotated Rect)')}\n"
        info += f"• MS COCO: {_('Industry standard JSON, configurable Index=0 (Custom) or 1 (Standard)')}\n"
        info += f"• Pascal VOC: {_('Standardized to VOC 2012 XML with 1-based pixel precision')}\n"
        info += f"• CSV: {_('Generic coordinate table for custom analysis')}\n\n"
        
        info += _("Features:") + "\n"
        info += f"• {_('Batch export to directory')}\n"
        info += f"• {_('Dataset splitting (Train/Val/Test)')}\n"
        info += f"• {_('Automated directory structure generation')}\n"
        info += f"• {_('Preview of split distribution')}"
        
        wx.MessageBox(info, _("Export Format Info"), wx.OK | wx.ICON_INFORMATION)

    def _on_about(self, event):
        """顯示關於對話框"""
        info = wx.adv.AboutDialogInfo()
        info.SetName("wxCvAnnotator")
        info.SetVersion(__version__)
        info.SetDescription(_(
            "A professional computer vision annotation tool.\n\n"
            "Key Features:\n"
            "• Advanced Export: YOLO (Detect/Seg/OBB), MS COCO, Pascal VOC 2012, CSV.\n"
            "• Integrated AI: SAM, SAM2, EfficientSAM, and various detection models.\n"
            "• Cross-platform support with industrial-grade precision.\n\n"
            "Designed for professional computer vision research and dataset preparation."
        ))
        info.SetCopyright("(C) 2026 wxCvRoot")
        info.SetWebSite("https://github.com/wxCvRoot/wxCvAnnotator")
        info.AddDeveloper("wxCvRoot")
        
        # Add Icon to About box
        icon_path_ico = PACKAGE_ROOT / "assets" / "icon.ico"
        icon_path_png = PACKAGE_ROOT / "assets" / "logo.png"
        
        if icon_path_ico.exists():
            info.SetIcon(wx.Icon(str(icon_path_ico)))
        elif icon_path_png.exists():
            bitmap = wx.Bitmap(str(icon_path_png), wx.BITMAP_TYPE_PNG)
            icon = wx.Icon()
            icon.CopyFromBitmap(bitmap)
            info.SetIcon(icon)
            
        wx.adv.AboutBox(info)

    def _load_labels_for_folder(self, folder_path: str):
        """三步標籤載入邏輯: Project -> Global -> Default"""
        loaded = False
        project_label_file = Path(folder_path) / "labels.json"
        global_label_file = PROJECT_ROOT / "config" / "default_labels.json"
        
        # 1. 嘗試載入專案標籤 (Project Level)
        if project_label_file.exists():
            print(f"📁 Found project labels: {project_label_file}")
            loaded = self.category_manager.load_labels(str(project_label_file))
            if loaded:
                self._update_status(f"Loaded labels from project: {project_label_file.name}")
        
        # 2. 嘗試載入全域預設 (Global Level)
        if not loaded and global_label_file.exists():
            print(f"🌍 Loading global default labels: {global_label_file}")
            loaded = self.category_manager.load_labels(str(global_label_file))
            if loaded:
                self._update_status("Loaded global default labels")
        
        # Sync colors for existing annotations based on newly loaded categories
        if self.image_display_panel:
            annotations = self.image_display_panel.get_annotations()
            for ann in annotations:
                ann.color = self.category_manager.get_color(ann.category)
            
        # 更新 UI
        self._refresh_label_list_ui()
        self._update_annotation_list()
        if self.image_display_panel:
            self.image_display_panel.Refresh()

    def _refresh_label_list_ui(self):
        """Refresh the label ListBox with current category manager state"""
        if not hasattr(self, 'label_list'):
            return
            
        current_selection = self.label_list.GetStringSelection()
        categories = self.category_manager.get_ordered_categories()
        
        # Update ListBox
        self.label_list.Clear()
        if categories:
            self.label_list.Set(categories)
            
            if current_selection in categories:
                self.label_list.SetStringSelection(current_selection)
            else:
                self.label_list.SetSelection(0)
                # Sync current category to image panel
                selection = self.label_list.GetStringSelection()
                if selection and self.image_display_panel:
                    self.image_display_panel.set_current_category(selection)

    def _on_save_labels_to_project(self, event):
        """Save current labels to project folder as labels.json"""
        if not self.project_folder:
            wx.MessageBox("Please open a folder first", "Hint", wx.OK | wx.ICON_INFORMATION)
            return
            
        label_file = Path(self.project_folder) / "labels.json"
        
        # Confirm overwrite if exists
        if label_file.exists():
            res = wx.MessageBox(f"labels.json already exists in project folder.\nOverwrite?", 
                               "Confirm Overwrite", wx.YES_NO | wx.ICON_QUESTION)
            if res != wx.YES:
                return
                
        if self.category_manager.save_labels(str(label_file)):
            wx.MessageBox(f"Labels saved to:\n{label_file}", "Success", wx.OK | wx.ICON_INFORMATION)
            self._update_status(f"Saved labels to {label_file.name}")
        else:
            wx.MessageBox("Failed to save labels", "Error", wx.OK | wx.ICON_ERROR)

    def _on_load_labels_from_project(self, event):
        """Reload labels from project labels.json"""
        if not self.project_folder:
            wx.MessageBox("Please open a folder first", "Hint", wx.OK | wx.ICON_INFORMATION)
            return
            
        self._load_labels_for_folder(self.project_folder)


class CategoryManagementDialog(wx.Dialog):
    """Category management dialog"""
    
    def __init__(self, parent, category_manager):
        super().__init__(parent, title="Category Management", size=(500, 400))
        
        self.category_manager = category_manager
        self.selected_category = None
        
        self._setup_ui()
        self._load_categories()
    
    def _setup_ui(self):
        """Setup UI"""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Category list
        list_label = wx.StaticText(self, wx.ID_ANY, "Category List:")
        sizer.Add(list_label, 0, wx.ALL, 5)
        
        self.category_list = wx.ListCtrl(
            self, wx.ID_ANY,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES
        )
        self.category_list.AppendColumn("Category", width=120)
        self.category_list.AppendColumn("Color", width=80)
        self.category_list.AppendColumn("Default", width=50)
        
        self.category_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_category_selected)
        sizer.Add(self.category_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # 控制按鈕
        control_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        btn_add = wx.Button(self, wx.ID_ANY, "Add")
        btn_edit = wx.Button(self, wx.ID_ANY, "Edit")
        btn_delete = wx.Button(self, wx.ID_ANY, "Delete")
        btn_reset = wx.Button(self, wx.ID_ANY, "Reset")
        
        btn_add.Bind(wx.EVT_BUTTON, self._on_add_category)
        btn_edit.Bind(wx.EVT_BUTTON, self._on_edit_category)
        btn_delete.Bind(wx.EVT_BUTTON, self._on_delete_category)
        btn_reset.Bind(wx.EVT_BUTTON, self._on_reset_categories)
        
        control_sizer.Add(btn_add, 0, wx.ALL, 5)
        control_sizer.Add(btn_edit, 0, wx.ALL, 5)
        control_sizer.Add(btn_delete, 0, wx.ALL, 5)
        control_sizer.Add(btn_reset, 0, wx.ALL, 5)
        
        sizer.Add(control_sizer, 0, wx.CENTER | wx.ALL, 5)
        
        # 確定/取消按鈕
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_ok = wx.Button(self, wx.ID_OK, "OK")
        btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(btn_ok, 0, wx.ALL, 5)
        button_sizer.Add(btn_cancel, 0, wx.ALL, 5)
        
        sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 10)
        
        self.SetSizer(sizer)
    
    def _load_categories(self):
        """Load categories"""
        self.category_list.DeleteAllItems()
        
        categories = self.category_manager.get_all_categories()
        for category, color in categories.items():
            index = self.category_list.InsertItem(0, category)
            self.category_list.SetItem(index, 1, color)
            is_default = "★" if category in DEFAULT_CATEGORY_COLORS else ""
            self.category_list.SetItem(index, 2, is_default)
    
    def _on_category_selected(self, event):
        """Category selected"""
        self.selected_category = self.category_list.GetItemText(event.GetIndex(), 0)
    
    def _on_add_category(self, event):
        """Add Category"""
        dialog = CategoryEditDialog(self, "Add Category", is_edit=False)
        
        if dialog.ShowModal() == wx.ID_OK:
            name = dialog.get_category_name()
            color = dialog.get_category_color()
            
            if name and color:
                success = self.category_manager.add_category(name, color)
                if success:
                    self._load_categories()
                    self._update_status(f"Added Category: {name}")
                else:
                    wx.MessageBox("Category name already exists or invalid", "Error", wx.OK | wx.ICON_ERROR)
            
            dialog.Destroy()
    
    def _on_edit_category(self, event):
        """Edit Category"""
        if not self.selected_category:
            wx.MessageBox("Please select a category to edit", "Hint", wx.OK | wx.ICON_INFORMATION)
            return
        
        current_color = self.category_manager.get_color(self.selected_category)
        dialog = CategoryEditDialog(self, "Edit Category", is_edit=True, 
                                  category_name=self.selected_category, color=current_color)
        
        if dialog.ShowModal() == wx.ID_OK:
            new_name = dialog.get_category_name()
            new_color = dialog.get_category_color()
            
            if new_name and new_color:
                success = self.category_manager.update_category(self.selected_category, new_name, new_color)
                if success:
                    self._load_categories()
                    self._update_status(f"Updated category: {self.selected_category} -> {new_name}")
                else:
                    wx.MessageBox("Update failed", "Error", wx.OK | wx.ICON_ERROR)
            
            dialog.Destroy()
    
    def _on_delete_category(self, event):
        """Delete Category"""
        if not self.selected_category:
            wx.MessageBox("Please select a category to delete", "Hint", wx.OK | wx.ICON_INFORMATION)
            return
        
        # Check if default category
        if self.selected_category in DEFAULT_CATEGORY_COLORS:
            wx.MessageBox("Cannot delete default category", "Hint", wx.OK | wx.ICON_WARNING)
            return
        
        result = wx.MessageBox(f"Are you sure you want to delete category '{self.selected_category}'?", "Confirm", 
                             wx.YES_NO | wx.ICON_QUESTION)
        
        if result == wx.YES:
            success = self.category_manager.remove_category(self.selected_category)
            if success:
                self._load_categories()
                self._update_status(f"Deleted category: {self.selected_category}")
                self.selected_category = None
            else:
                wx.MessageBox("Delete failed", "Error", wx.OK | wx.ICON_ERROR)
    
    def _on_reset_categories(self, event):
        """Reset Categories"""
        result = wx.MessageBox("Are you sure you want to reset all categories to defaults? This will delete all custom categories.", "Confirm",
                             wx.YES_NO | wx.ICON_WARNING)
        
        if result == wx.YES:
            self.category_manager.reset_to_default()
            self._load_categories()
            self._update_status("Categories reset to default")
    
    def _update_status(self, message):
        """Update status"""
        self.status_bar.SetStatusText(message, 0)


class CategoryEditDialog(wx.Dialog):
    """Category edit dialog"""
    
    def __init__(self, parent, title, is_edit=False, category_name="", color="#FF0000"):
        super().__init__(parent, title=title, size=(350, 250))
        
        self.is_edit = is_edit
        self.category_name = category_name
        self.selected_color = color
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI"""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Category Name
        name_label = wx.StaticText(self, wx.ID_ANY, "Category Name:")
        self.name_text = wx.TextCtrl(self, wx.ID_ANY, value=self.category_name)
        sizer.Add(name_label, 0, wx.ALL, 5)
        sizer.Add(self.name_text, 0, wx.EXPAND | wx.ALL, 5)
        
        # Color selection
        color_label = wx.StaticText(self, wx.ID_ANY, "Color:")
        color_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.color_panel = wx.Panel(self, wx.ID_ANY, size=(50, 25))
        self.color_panel.SetBackgroundColour(wx.Colour(self._hex_to_rgb(self.selected_color)))
        color_sizer.Add(self.color_panel, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        btn_color = wx.Button(self, wx.ID_ANY, "Select Color")
        btn_color.Bind(wx.EVT_BUTTON, self._on_choose_color)
        color_sizer.Add(btn_color, 0, wx.ALL, 5)
        
        sizer.Add(color_label, 0, wx.ALL, 5)
        sizer.Add(color_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_ok = wx.Button(self, wx.ID_OK, "OK")
        btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(btn_ok, 0, wx.ALL, 5)
        button_sizer.Add(btn_cancel, 0, wx.ALL, 5)
        
        sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 10)
        
        self.SetSizer(sizer)
    
    def _on_choose_color(self, event):
        """Choose color"""
        color_data = wx.ColourData()
        color_data.SetColour(wx.Colour(self._hex_to_rgb(self.selected_color)))
        
        dialog = wx.ColourDialog(self, color_data)
        if dialog.ShowModal() == wx.ID_OK:
            selected_color = dialog.GetColourData().GetColour()
            self.selected_color = self._rgb_to_hex(selected_color)
            self.color_panel.SetBackgroundColour(selected_color)
            self.color_panel.Refresh()
        
        dialog.Destroy()
    
    def get_category_name(self) -> str:
        """Get category name"""
        return self.name_text.GetValue().strip()
    
    def get_category_color(self) -> str:
        """Get category color"""
        return self.selected_color
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert Hex to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _rgb_to_hex(self, rgb_color) -> str:
        """Convert RGB to Hex"""
        return f"#{rgb_color.Red():02x}{rgb_color.Green():02x}{rgb_color.Blue():02x}"
