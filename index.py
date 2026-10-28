import os
import json
import tkinter as tk
from tkinter import filedialog
import subprocess
import platform

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.utils import get_color_from_hex

from converter_engine import FullConverterEngine

# Window Setup
Window.maximize()
Window.clearcolor = get_color_from_hex("#0B1120")

# Color Palette
BG_DARK = "#0B1120"
PANEL_BG = "#111827"
CARD_BG = "#1E293B"
TEXT_PRIMARY = "#FFFFFF"
TEXT_MUTED = "#94A3B8"
BORDER_COLOR = "#334155"

# Button Palette
COLOR_BLUE = "#2563EB"
COLOR_GREEN = "#059669"
COLOR_PURPLE = "#7C3AED"
COLOR_RED = "#DC2626"
COLOR_AMBER = "#D97706"
COLOR_ROSE = "#E11D48"

# Dropdown Item Palette
DROPDOWN_ITEM_BG = "#334155"

HISTORY_DIR = os.path.join(os.path.expanduser("~"), ".convertHistory")
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.json")

# Keep the picker aligned with converter_engine.py. Optional dependencies may
# be needed (FFmpeg, Pillow, pandas, LibreOffice, Pandoc, Poppler, py7zr, rarfile).
CATEGORY_EXTENSIONS = {
    "Document": {"pdf", "doc", "docx", "odt", "rtf", "txt", "md", "html", "htm", "epub"},
    "Image": {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "ico", "avif", "gif"},
    "Audio": {"mp3", "wav", "aac", "flac", "ogg", "m4a", "opus", "wma", "aiff", "ac3"},
    "Video": {"mp4", "mkv", "avi", "mov", "webm", "wmv", "flv", "mpeg", "mpg", "3gp", "gif", "m4v", "ts"},
    "Archive": {"zip", "rar", "7z", "tar", "tgz", "gz"},
    "eBook": {"epub", "pdf", "txt", "html", "htm", "md", "doc", "docx", "odt", "rtf"},
    "Spreadsheet": {"xlsx", "xls", "csv", "tsv", "ods", "json"},
    "Presentation": {"pptx", "ppt", "odp"}
}

_FORMAT_FAMILIES = {
    "DOCUMENT": {"pdf", "doc", "docx", "odt", "rtf", "txt", "md", "html", "htm", "epub"},
    "IMAGE": {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "ico", "avif", "gif"},
    "AUDIO": {"mp3", "wav", "aac", "flac", "ogg", "m4a", "opus", "wma", "aiff", "ac3"},
    "VIDEO": {"mp4", "mkv", "avi", "mov", "webm", "wmv", "flv", "mpeg", "mpg", "3gp", "gif", "m4v", "ts"},
    "TABLE": {"csv", "tsv", "xlsx", "xls", "ods", "json"},
    "STRUCTURED": {"json", "xml", "yaml", "yml"},
    "PRESENTATION": {"ppt", "pptx", "odp"},
}
CONVERSION_RULES = {}
for _family, _formats in _FORMAT_FAMILIES.items():
    for _source in _formats:
        _targets = set(_formats) - {_source}
        if _family == "DOCUMENT" and _source == "pdf":
            _targets |= {"jpg", "png", "webp"}  # PDF rendering currently exports page 1.
        if _family == "PRESENTATION":
            _targets |= {"pdf", "docx", "ppt", "pptx", "odp"} - {_source}
        CONVERSION_RULES.setdefault(_source.upper(), [])
        CONVERSION_RULES[_source.upper()] = sorted(set(CONVERSION_RULES[_source.upper()]) |
                                                   {fmt.upper() for fmt in _targets})

# Archive formats can be read from ZIP/TAR/GZIP/7Z/RAR; output supports ZIP,
# TAR/GZIP and 7Z only. The engine intentionally cannot create RAR files.
_ARCHIVE_READ = {"zip", "rar", "7z", "tar", "tgz", "gz", "tar.gz"}
_ARCHIVE_WRITE = {"zip", "7z", "tar", "tgz", "gz", "tar.gz"}
for _source in _ARCHIVE_READ:
    CONVERSION_RULES[_source.upper()] = sorted(fmt.upper() for fmt in _ARCHIVE_WRITE if fmt != _source)

CAT_COLORS = {
    "All Formats": "#2563EB",
    "Document": "#2563EB",
    "Image": "#10B981",
    "Audio": "#8B5CF6",
    "Video": "#EC4899",
    "Archive": "#EAB308",
    "eBook": "#06B6D4",
    "Spreadsheet": "#10B981",
    "Presentation": "#7C3AED"
}

FILE_TYPE_ICONS = {
    "PDF": "📄", "DOCX": "📝", "DOC": "📄", "TXT": "📑", "JPG": "🖼️", "JPEG": "🖼️",
    "PNG": "🖼️", "WEBP": "🖼️", "BMP": "🖼️", "TIFF": "🖼️", "MP3": "🎵", "WAV": "🎶",
    "FLAC": "🎵", "M4A": "🎵", "MP4": "🎬", "MKV": "🎥", "AVI": "🎬", "MOV": "🎬",
    "XLSX": "📊", "CSV": "📈", "EPUB": "📚", "PPTX": "📽️", "PPT": "📽️", "ODP": "📽️"
}


class VibrantButton(Button):
    def __init__(self, bg_hex=COLOR_BLUE, text_hex="#FFFFFF", radius=10, font_size='14sp', **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.bg_hex = bg_hex
        self.radius_val = radius
        self.color = get_color_from_hex(text_hex)
        self.font_size = font_size
        self.bold = True
        self.halign = 'center'
        self.valign = 'middle'

        with self.canvas.before:
            self.bg_color = Color(*get_color_from_hex(self.bg_hex))
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[self.radius_val])

        self.bind(pos=self._update_bounds, size=self._update_bounds)

    def set_color(self, hex_code):
        self.bg_hex = hex_code
        self.bg_color.rgba = get_color_from_hex(hex_code)

    def _update_bounds(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size
        self.text_size = instance.size


class SidebarCategoryItem(BoxLayout):
    def __init__(self, title, subtitle, color_hex="#2563EB", active=False, on_select=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 60
        self.padding = [14, 8]
        self.spacing = 14
        self.active = active
        self.title = title
        self.color_hex = color_hex
        self.on_select_cb = on_select

        with self.canvas.before:
            self.bg_color = Color(*get_color_from_hex(COLOR_BLUE if active else PANEL_BG))
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[10])
        self.bind(pos=self._update_rect, size=self._update_rect)

        icon_box = BoxLayout(size_hint=(None, None), size=(36, 36), pos_hint={'center_y': 0.5})
        with icon_box.canvas.before:
            Color(*get_color_from_hex(color_hex if not active else "#FFFFFF"))
            icon_box.rect = RoundedRectangle(size=icon_box.size, pos=icon_box.pos, radius=[8])
        icon_box.bind(pos=lambda inst, v: setattr(icon_box.rect, 'pos', inst.pos),
                      size=lambda inst, v: setattr(icon_box.rect, 'size', inst.size))

        lbl_initial = Label(text=title[0], bold=True, color=get_color_from_hex("#FFFFFF" if not active else color_hex), font_size='16sp', halign='center', valign='middle')
        lbl_initial.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        icon_box.add_widget(lbl_initial)
        self.add_widget(icon_box)

        text_box = BoxLayout(orientation='vertical', pos_hint={'center_y': 0.5})
        self.t_lbl = Label(text=f"[b]{title}[/b]", markup=True, halign='left', valign='middle', font_size='15sp', color=get_color_from_hex("#FFFFFF"))
        self.s_lbl = Label(text=subtitle, halign='left', valign='middle', font_size='11sp', color=get_color_from_hex("#DBEAFE") if active else get_color_from_hex(TEXT_MUTED))

        self.t_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        self.s_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))

        text_box.add_widget(self.t_lbl)
        if subtitle:
            text_box.add_widget(self.s_lbl)

        self.add_widget(text_box)

    def set_active(self, state):
        self.active = state
        self.bg_color.rgba = get_color_from_hex(COLOR_BLUE if state else PANEL_BG)
        self.s_lbl.color = get_color_from_hex("#DBEAFE") if state else get_color_from_hex(TEXT_MUTED)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.on_select_cb:
                self.on_select_cb(self)
            return True
        return super().on_touch_down(touch)


class ConvertedHistoryRow(BoxLayout):
    def __init__(self, filename, filepath, filesize, target_fmt, badge_color="#8B5CF6", on_remove=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 58
        self.padding = [12, 6]
        self.spacing = 12
        self.filename = filename
        self.filepath = filepath
        self.filesize = filesize
        self.target_fmt = target_fmt

        with self.canvas.before:
            Color(*get_color_from_hex(CARD_BG))
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[10])
        self.bind(pos=self._update_rect, size=self._update_rect)

        target_icon = FILE_TYPE_ICONS.get(target_fmt.upper(), "📄")

        badge = BoxLayout(size_hint=(None, None), size=(40, 40), pos_hint={'center_y': 0.5})
        with badge.canvas.before:
            Color(*get_color_from_hex(badge_color))
            badge.rect = RoundedRectangle(size=badge.size, pos=badge.pos, radius=[8])
        badge.bind(pos=lambda inst, v: setattr(badge.rect, 'pos', inst.pos),
                   size=lambda inst, v: setattr(badge.rect, 'size', inst.size))

        ext_lbl = Label(text=target_icon, bold=True, font_size='16sp', halign='center', valign='middle', font_name="seguiemj.ttf")
        ext_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        badge.add_widget(ext_lbl)
        self.add_widget(badge)

        details = BoxLayout(orientation='vertical', pos_hint={'center_y': 0.5})
        
        lbl_name = Label(
            text=f"[color=#10B981]✓[/color] [b]{filename}[/b]", 
            markup=True, font_name="seguiemj.ttf",
            halign='left', valign='middle', font_size='13sp', color=get_color_from_hex("#F1F5F9")
        )
        
        lbl_path = Label(
            text=f"{filesize} • Path: {filepath}", 
            halign='left', valign='middle', font_size='10sp',
            color=get_color_from_hex(TEXT_MUTED),
            shorten=True, shorten_from='left'
        )
        lbl_name.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        lbl_path.bind(size=lambda inst, val: setattr(inst, 'text_size', val))

        details.add_widget(lbl_name)
        details.add_widget(lbl_path)
        self.add_widget(details)

        btn_folder = VibrantButton(text="📁", bg_hex=COLOR_AMBER, font_size='16sp', size_hint=(None, None), size=(36, 36), pos_hint={'center_y': 0.5}, radius=8, font_name="seguiemj.ttf")
        btn_folder.bind(on_release=self._open_file_location)
        self.add_widget(btn_folder)

        pill = VibrantButton(text=f".{target_fmt.lower()}", bg_hex=badge_color, font_size='12sp', size_hint=(None, None), size=(65, 30), pos_hint={'center_y': 0.5}, radius=14, font_name="seguiemj.ttf")
        self.add_widget(pill)

        btn_del = VibrantButton(text="❌", bg_hex=COLOR_ROSE, font_size='12sp', size_hint=(None, None), size=(32, 32), pos_hint={'center_y': 0.5}, radius=16, font_name="seguiemj.ttf")
        if on_remove:
            btn_del.bind(on_release=lambda x: on_remove(self))
        self.add_widget(btn_del)

    def _open_file_location(self, instance):
        target_dir = os.path.dirname(self.filepath) if self.filepath else os.path.expanduser("~/Downloads/ConvertedFiles")
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        if platform.system() == "Windows":
            os.startfile(target_dir)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", target_dir])
        else:
            subprocess.Popen(["xdg-open", target_dir])

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size


class ModernProgressBar(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = 45
        self.progress = 0

        self.lbl_pct = Label(text="Converting... 0%", font_size='15sp', bold=True, color=get_color_from_hex(TEXT_PRIMARY), size_hint_y=None, height=22, halign='center', valign='middle')
        self.lbl_pct.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        self.add_widget(self.lbl_pct)

        self.bar_bg = BoxLayout(size_hint_y=None, height=14)
        with self.bar_bg.canvas.before:
            Color(*get_color_from_hex(CARD_BG))
            self.track = RoundedRectangle(size=self.bar_bg.size, pos=self.bar_bg.pos, radius=[7])
            Color(*get_color_from_hex("#10B981"))
            self.fill = RoundedRectangle(size=(0, self.bar_bg.height), pos=self.bar_bg.pos, radius=[7])

        self.bar_bg.bind(pos=self._update_bar, size=self._update_bar)
        self.add_widget(self.bar_bg)

    def set_progress(self, val, message="Converting..."):
        self.progress = min(max(val, 0), 100)
        self.lbl_pct.text = f"{message} {int(self.progress)}%"
        fill_width = (self.bar_bg.width * self.progress) / 100.0
        self.fill.size = (fill_width, self.bar_bg.height)

    def _update_bar(self, instance, value):
        self.track.pos = instance.pos
        self.track.size = instance.size
        self.fill.pos = instance.pos
        self.fill.size = ((instance.width * self.progress) / 100.0, instance.height)


class ModernFileConverterUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.padding = 20
        self.spacing = 20

        # Instantiate Engine Properly
        self.engine = FullConverterEngine()

        self.current_category = "All Formats"
        self.sidebar_items = []
        self.selected_files = []
        self.current_target_fmt = "PDF"

        Window.bind(on_drop_file=self._on_file_dropped)

        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR)

        # SIDEBAR
        sidebar = BoxLayout(orientation='vertical', size_hint_x=0.28, spacing=14)

        header = BoxLayout(size_hint_y=None, height=55, spacing=10)
        t_box = BoxLayout(orientation='vertical', pos_hint={'center_y': 0.5})
        title = Label(text="[b]⚡ File Converter[/b]", markup=True, font_size='20sp', halign='left', valign='middle', color=get_color_from_hex(TEXT_PRIMARY), font_name="seguiemj.ttf")
        sub = Label(text="Convert files to any format easily", font_size='12sp', halign='left', valign='middle', color=get_color_from_hex(TEXT_MUTED))
        title.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        sub.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        t_box.add_widget(title)
        t_box.add_widget(sub)
        header.add_widget(t_box)
        sidebar.add_widget(header)

        scroll_cat = ScrollView()
        self.cats_layout = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.cats_layout.bind(minimum_height=self.cats_layout.setter('height'))

        items = [
            ("All Formats", "Everything", CAT_COLORS["All Formats"]),
            ("Document", "PDF, DOCX, TXT, etc.", CAT_COLORS["Document"]),
            ("Image", "JPG, PNG, GIF, BMP, etc.", CAT_COLORS["Image"]),
            ("Audio", "MP3, WAV, AAC, etc.", CAT_COLORS["Audio"]),
            ("Video", "MP4, AVI, MKV, etc.", CAT_COLORS["Video"]),
            ("Archive", "ZIP, RAR, 7Z, etc.", CAT_COLORS["Archive"]),
            ("eBook", "EPUB, MOBI, PDF, etc.", CAT_COLORS["eBook"]),
            ("Spreadsheet", "XLSX, CSV, etc.", CAT_COLORS["Spreadsheet"]),
            ("Presentation", "PPTX, PPT, ODP, etc.", CAT_COLORS["Presentation"])
        ]

        for idx, (name, sub_txt, col) in enumerate(items):
            item_widget = SidebarCategoryItem(name, sub_txt, col, active=(idx == 0), on_select=self._on_category_click)
            self.sidebar_items.append(item_widget)
            self.cats_layout.add_widget(item_widget)

        scroll_cat.add_widget(self.cats_layout)
        sidebar.add_widget(scroll_cat)
        self.add_widget(sidebar)

        # WORKSPACE
        main_workspace = BoxLayout(orientation='vertical', size_hint_x=0.72, spacing=16)

        top_bar_container = BoxLayout(size_hint_y=None, size_hint_x=1.0, height=58)
        top_bar = BoxLayout(size_hint_x=1.0, spacing=15)

        from_box = BoxLayout(orientation='vertical', size_hint_x=0.48)
        lbl_from = Label(text="From", font_size='13sp', halign='left', valign='middle', color=get_color_from_hex(TEXT_MUTED), size_hint_y=None, height=18)
        lbl_from.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        from_box.add_widget(lbl_from)

        self.btn_from = VibrantButton(text="Select file type  ▼", bg_hex=CARD_BG, text_hex=TEXT_PRIMARY, font_size='13sp', radius=10, size_hint_x=1.0, font_name="seguiemj.ttf")
        self.from_dropdown = DropDown(auto_width=False)
        self.btn_from.bind(on_release=self._open_from_dropdown)
        from_box.add_widget(self.btn_from)

        arrow = Label(text="-->", font_size='18sp', bold=True, size_hint_x=None, width=30, color=get_color_from_hex(TEXT_MUTED), pos_hint={'center_y': 0.3})

        to_box = BoxLayout(orientation='vertical', size_hint_x=0.48)
        lbl_to = Label(text="To", font_size='13sp', halign='left', valign='middle', color=get_color_from_hex(TEXT_MUTED), size_hint_y=None, height=18)
        lbl_to.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        to_box.add_widget(lbl_to)

        self.btn_to = VibrantButton(text="Select output format  ▼", bg_hex=CARD_BG, text_hex=TEXT_PRIMARY, font_size='13sp', radius=10, size_hint_x=1.0, font_name="seguiemj.ttf")
        self.to_dropdown = DropDown(auto_width=False)
        self.btn_to.bind(on_release=self._open_to_dropdown)
        to_box.add_widget(self.btn_to)

        top_bar.add_widget(from_box)
        top_bar.add_widget(arrow)
        top_bar.add_widget(to_box)
        top_bar_container.add_widget(top_bar)
        main_workspace.add_widget(top_bar_container)

        self.drop_area = BoxLayout(orientation='vertical', size_hint_x=1.0, padding=20, spacing=10)
        with self.drop_area.canvas.before:
            self.drop_bg = Color(*get_color_from_hex(PANEL_BG))
            self.drop_rect = RoundedRectangle(size=self.drop_area.size, pos=self.drop_area.pos, radius=[12])
            self.drop_line_color = Color(*get_color_from_hex(BORDER_COLOR))
            self.drop_line = Line(rounded_rectangle=(self.drop_area.pos[0], self.drop_area.pos[1], self.drop_area.size[0], self.drop_area.size[1], 12), width=1)

        self.drop_area.bind(pos=self._update_drop_bounds, size=self._update_drop_bounds)

        self.lbl_image = Image(source="drag_drop.png", size_hint_y=None, height=85, allow_stretch=True, keep_ratio=True)
        self.lbl_drop_title = Label(text="Drag and drop file here", font_size='16sp', bold=True, color=get_color_from_hex(TEXT_PRIMARY), size_hint_y=None, height=24, halign='center', valign='middle', font_name="seguiemj.ttf")
        self.lbl_or = Label(text="or", font_size='12sp', color=get_color_from_hex(TEXT_MUTED), size_hint_y=None, height=16, halign='center', valign='middle', font_name="seguiemj.ttf")
        self.lbl_sub = Label(text="Select a file to start converting", font_size='12sp', color=get_color_from_hex(TEXT_MUTED), size_hint_y=None, height=20, halign='center', valign='middle', font_name="seguiemj.ttf")

        for l in (self.lbl_drop_title, self.lbl_or, self.lbl_sub, self.lbl_image):
            l.bind(size=lambda inst, val: setattr(inst, 'text_size', val))

        self.drop_area.add_widget(self.lbl_image)
        self.drop_area.add_widget(self.lbl_drop_title)
        self.drop_area.add_widget(self.lbl_or)

        self.btn_add = VibrantButton(text="+ Add File", bg_hex=COLOR_BLUE, font_size='15sp', radius=8, size_hint=(None, None), size=(140, 42), pos_hint={'center_x': 0.5})
        self.btn_add.bind(on_release=self._open_file_dialog)
        self.drop_area.add_widget(self.btn_add)
        self.drop_area.add_widget(self.lbl_sub)

        self.progress_bar = ModernProgressBar()
        main_workspace.add_widget(self.drop_area)

        history_panel = BoxLayout(orientation='vertical', size_hint_x=1.0, padding=14, spacing=10)
        with history_panel.canvas.before:
            Color(*get_color_from_hex(PANEL_BG))
            history_panel.rect = RoundedRectangle(size=history_panel.size, pos=history_panel.pos, radius=[12])
        history_panel.bind(pos=lambda inst, v: setattr(history_panel.rect, 'pos', inst.pos),
                           size=lambda inst, v: setattr(history_panel.rect, 'size', inst.size))

        h_head = BoxLayout(size_hint_y=None, height=32)
        lbl_h = Label(text="[b]Files Converted / History[/b]", markup=True, halign='left', valign='middle', font_size='15sp', color=get_color_from_hex("#E2E8F0"))
        lbl_h.bind(size=lambda inst, val: setattr(inst, 'text_size', val))

        btn_clear = VibrantButton(text="🗑 Clear All", bg_hex=COLOR_RED, font_size='13sp', radius=6, size_hint_x=None, width=110, font_name="seguiemj.ttf")
        btn_clear.bind(on_release=self._clear_history)
        h_head.add_widget(lbl_h)
        h_head.add_widget(btn_clear)
        history_panel.add_widget(h_head)

        self.history_box = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.history_box.bind(minimum_height=self.history_box.setter('height'))

        scroll_h = ScrollView()
        scroll_h.add_widget(self.history_box)
        history_panel.add_widget(scroll_h)

        main_workspace.add_widget(history_panel)

        # BOTTOM BAR
        bottom_bar = BoxLayout(size_hint_y=None, size_hint_x=1.0, height=48, spacing=14)

        out_input_box = BoxLayout(orientation='horizontal', padding=[12, 0], spacing=8, size_hint_x=0.60)
        with out_input_box.canvas.before:
            Color(*get_color_from_hex(CARD_BG))
            out_input_box.rect = RoundedRectangle(size=out_input_box.size, pos=out_input_box.pos, radius=[8])
        out_input_box.bind(pos=lambda inst, v: setattr(out_input_box.rect, 'pos', inst.pos),
                           size=lambda inst, v: setattr(out_input_box.rect, 'size', inst.size))

        lbl_folder_icon = Label(text="📁", font_size='16sp', size_hint_x=None, width=24, pos_hint={'center_y': 0.5}, font_name="seguiemj.ttf")

        default_dir = os.path.join(os.path.expanduser("~"), "Downloads\\ConvertedFiles")
        self.out_input = TextInput(text=default_dir, multiline=False,
                                   background_color=(0, 0, 0, 0), foreground_color=get_color_from_hex("#E2E8F0"),
                                   font_size='14sp', cursor_color=get_color_from_hex(COLOR_BLUE),
                                   padding=[0, 14, 0, 0], halign='left')

        out_input_box.add_widget(lbl_folder_icon)
        out_input_box.add_widget(self.out_input)

        btn_browse = VibrantButton(text="📁 Browse", bg_hex=COLOR_GREEN, font_size='14sp', radius=8, size_hint_x=0.18, font_name="seguiemj.ttf")
        btn_browse.bind(on_release=self._open_folder_dialog)

        self.btn_convert = VibrantButton(text="🚀 Convert", bg_hex=COLOR_PURPLE, font_size='15sp', radius=8, size_hint_x=0.22, font_name="seguiemj.ttf")
        self.btn_convert.bind(on_release=self._start_conversion_process)

        bottom_bar.add_widget(out_input_box)
        bottom_bar.add_widget(btn_browse)
        bottom_bar.add_widget(self.btn_convert)
        main_workspace.add_widget(bottom_bar)

        self.add_widget(main_workspace)

        self._load_stored_history()

    def _open_from_dropdown(self, widget):
        self.from_dropdown.width = widget.width
        if not self.from_dropdown.children[0].children:
            all_formats = list(CONVERSION_RULES.keys())
            content = self._create_colored_dropdown_content(all_formats, self._select_from_format)
            self.from_dropdown.add_widget(content)
        self.from_dropdown.open(widget)

    def _open_to_dropdown(self, widget):
        self.to_dropdown.width = widget.width
        self.to_dropdown.open(widget)

    def _update_drop_bounds(self, instance, value):
        self.drop_rect.pos = instance.pos
        self.drop_rect.size = instance.size
        self.drop_line.rounded_rectangle = (instance.pos[0], instance.pos[1], instance.size[0], instance.size[1], 12)

    def _on_category_click(self, selected_item):
        self.current_category = selected_item.title
        for item in self.sidebar_items:
            item.set_active(item == selected_item)

    def _create_colored_dropdown_content(self, items, select_callback):
        container = BoxLayout(orientation='vertical', spacing=8, padding=10, size_hint_y=None, size_hint_x=1.0)
        container.bind(minimum_height=container.setter('height'))

        with container.canvas.before:
            Color(*get_color_from_hex(PANEL_BG))
            container.rect = RoundedRectangle(size=container.size, pos=container.pos, radius=[10])
            Color(*get_color_from_hex(BORDER_COLOR))
            container.line = Line(rounded_rectangle=(container.pos[0], container.pos[1], container.size[0], container.size[1], 10), width=1)

        container.bind(pos=lambda inst, v: (setattr(container.rect, 'pos', inst.pos), setattr(container.line, 'rounded_rectangle', (inst.pos[0], inst.pos[1], inst.size[0], inst.size[1], 10))),
                       size=lambda inst, v: (setattr(container.rect, 'size', inst.size), setattr(container.line, 'rounded_rectangle', (inst.pos[0], inst.pos[1], inst.size[0], inst.size[1], 10))))

        for fmt in items:
            btn = VibrantButton(
                text=f"{FILE_TYPE_ICONS.get(fmt, '📄')}  {fmt}", 
                font_name="seguiemj.ttf",
                bg_hex=DROPDOWN_ITEM_BG,
                text_hex="#FFFFFF",
                radius=8,
                font_size='13sp',
                size_hint_y=None,
                size_hint_x=1.0,
                height=38
            )
            btn.bind(on_release=lambda b, f=fmt: select_callback(f))
            container.add_widget(btn)

        return container

    def _select_from_format(self, fmt):
        self.btn_from.text = f"{FILE_TYPE_ICONS.get(fmt, '📄')}  {fmt}  ▼"
        self.from_dropdown.dismiss()

    def _select_to_format(self, fmt):
        self.current_target_fmt = fmt.upper()
        self.btn_to.text = f"{FILE_TYPE_ICONS.get(fmt, '📄')}  {fmt}  ▼"
        self.to_dropdown.dismiss()

    def _open_folder_dialog(self, instance):
            root = tk.Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Select Output Directory")
            root.destroy()
    
            if folder:
                self.out_input.text = folder
    def _open_file_dialog(self, instance):
        root = tk.Tk()
        root.withdraw()

        # Build file dialog filters dynamically based on selected category
        if self.current_category in CATEGORY_EXTENSIONS:
            allowed_exts = CATEGORY_EXTENSIONS[self.current_category]
            patterns = " ".join(f"*.{ext}" for ext in allowed_exts)
            file_types = [
                (f"{self.current_category} Files", patterns),
                ("All Files", "*.*")
            ]
            files = filedialog.askopenfilenames(
                title=f"Select {self.current_category} File to Convert", 
                filetypes=file_types
            )
        else:
            files = filedialog.askopenfilenames(title="Select File to Convert")

        root.destroy()

        if files:
            self._process_single_selected_file(files[0])

    def _on_file_dropped(self, window, file_path, x=0, y=0, *args):
        path = file_path.decode('utf-8') if isinstance(file_path, bytes) else file_path
        self._process_single_selected_file(path)

    def _process_single_selected_file(self, file_path):
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].replace(".", "").lower()

        # Validate file against active sidebar category restriction
        if self.current_category in CATEGORY_EXTENSIONS:
            allowed = CATEGORY_EXTENSIONS[self.current_category]
            if ext not in allowed:
                self.lbl_drop_title.text = (
                    f"⚠️ Only {self.current_category} formats allowed!\n"
                    f"({', '.join(allowed).upper()})"
                )
                self.drop_bg.rgba = get_color_from_hex("#331B1B")
                self.drop_line_color.rgba = get_color_from_hex(COLOR_ROSE)
                self.selected_files = []
                return

        self.selected_files = [file_path]
        ext_upper = ext.upper()

        icon = FILE_TYPE_ICONS.get(ext_upper, '📄')
        self.btn_from.text = f"{icon}  {ext_upper}  ▼"

        available_targets = CONVERSION_RULES.get(ext_upper, ["PDF", "TXT"])
        self._update_to_dropdown_options(available_targets)

        default_target = available_targets[0]
        self.current_target_fmt = default_target.upper()
        target_icon = FILE_TYPE_ICONS.get(default_target, '📄')
        self.btn_to.text = f"{target_icon}  {default_target}  ▼"

        self._set_active_drag_ui(f"{icon} File Name: {filename}\nFile Type: {ext_upper}")
        
    def _update_to_dropdown_options(self, target_formats):
        self.to_dropdown.clear_widgets()
        to_content = self._create_colored_dropdown_content(target_formats, self._select_to_format)
        self.to_dropdown.add_widget(to_content)

    def _set_active_drag_ui(self, message):
        self.drop_bg.rgba = get_color_from_hex("#1E293B")
        self.drop_line_color.rgba = get_color_from_hex(COLOR_BLUE)
        self.lbl_drop_title.text = message

    def _start_conversion_process(self, instance):
        if not self.selected_files:
            self.lbl_drop_title.text = "⚠️ Please add or drop a file first!"
            return

        self.drop_area.clear_widgets()
        self.drop_area.add_widget(self.progress_bar)
        self.progress_bar.set_progress(10, "Converting...")

        target_dir = os.path.abspath(self.out_input.text)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        target_fmt = getattr(self, "current_target_fmt", "PDF").lower()

        for file_path in self.selected_files:
            filename = os.path.basename(file_path)
            base_name = os.path.splitext(filename)[0]
            out_filepath = os.path.join(target_dir, f"{base_name}.{target_fmt}")

            # Safe progress update scheduled on Kivy's main UI thread
            def progress_cb(pct, status="Converting..."):
                Clock.schedule_once(lambda dt: self.progress_bar.set_progress(pct * 100 if pct <= 1 else pct, status))

            # Completion callback passed to convert_async
            def completion_cb(success, error_msg=None):
                Clock.schedule_once(lambda dt: self._on_single_conversion_done(success, file_path, out_filepath, target_fmt))

            # Trigger async conversion
            try:
                self.engine.convert_async(
                    input_path=file_path,
                    output_path=out_filepath,
                    progress_callback=progress_cb,
                    completion_callback=completion_cb
                )
            except TypeError:
                # Fallback if engine convert_async only accepts (file_path, out_filepath, progress_cb)
                self.engine.convert_async(file_path, out_filepath, progress_cb)
                # Force trigger completion check after conversion finishes
                Clock.schedule_interval(
                    lambda dt: self._check_async_completion(out_filepath, file_path, target_fmt, dt), 0.5
                )

    def _check_async_completion(self, out_filepath, file_path, target_fmt, dt):
        if os.path.exists(out_filepath):
            self._on_single_conversion_done(True, file_path, out_filepath, target_fmt)
            return False  # Unschedule interval
        return True

    def _on_single_conversion_done(self, success, file_path, out_filepath, target_fmt):
        try:
            if success and os.path.exists(out_filepath):
                converted_filename = os.path.basename(out_filepath)
                filesize = f"{os.path.getsize(out_filepath) / (1024*1024):.2f} MB"
                
                # 1. Add item to visual history UI
                row = ConvertedHistoryRow(
                    converted_filename, out_filepath, filesize, target_fmt,
                    CAT_COLORS.get(self.current_category, "#2563EB"),
                    on_remove=self._remove_history_item
                )
                self.history_box.add_widget(row)

                # 2. Persist record to JSON file
                self._save_record_to_history_file(
                    converted_filename, out_filepath, filesize, target_fmt,
                    CAT_COLORS.get(self.current_category, "#2563EB")
                )
        except Exception as e:
            print(f"Error handling history item: {e}")
        finally:
            # 3. Always reset the drag-and-drop dropzone UI
            self.selected_files = []
            self._reset_drop_zone_ui()

    def _reset_drop_zone_ui(self):
        self.drop_area.clear_widgets()
        self.drop_bg.rgba = get_color_from_hex(PANEL_BG)
        self.drop_line_color.rgba = get_color_from_hex(BORDER_COLOR)

        self.lbl_drop_title.text = "Drag and drop file here"
        self.btn_from.text = "Select file type  ▼"
        self.btn_to.text = "Select output format  ▼"

        self.drop_area.add_widget(self.lbl_image)
        self.drop_area.add_widget(self.lbl_drop_title)
        self.drop_area.add_widget(self.lbl_or)
        self.drop_area.add_widget(self.btn_add)
        self.drop_area.add_widget(self.lbl_sub)

    def _save_record_to_history_file(self, filename, filepath, filesize, target_fmt, badge_color):
        records = self._read_history_file()
        records.append({
            "filename": filename,
            "filepath": filepath,
            "filesize": filesize,
            "target_fmt": target_fmt,
            "badge_color": badge_color
        })
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=4)

    def _read_history_file(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _load_stored_history(self):
        records = self._read_history_file()
        for r in records:
            row = ConvertedHistoryRow(r["filename"], r["filepath"], r["filesize"], r["target_fmt"],
                                      r["badge_color"], on_remove=self._remove_history_item)
            self.history_box.add_widget(row)

    def _remove_history_item(self, row_instance):
        self.history_box.remove_widget(row_instance)

        records = self._read_history_file()
        updated = [r for r in records if not (r["filename"] == row_instance.filename and r["target_fmt"] == row_instance.target_fmt)]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=4)

    def _clear_history(self, instance):
        self.history_box.clear_widgets()
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)


class FileConverterApp(App):
    def build(self):
        self.title = "Modern File Converter"
        return ModernFileConverterUI()


if __name__ == "__main__":
    FileConverterApp().run()
