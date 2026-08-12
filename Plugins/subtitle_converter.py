# plugins/subtitle_converter.py
import os
import re
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QTextEdit, 
    QApplication, QGroupBox, QCheckBox, QMessageBox, QSpinBox,
    QComboBox, QLineEdit
)
from plugin_base import FeaturePlugin

class SubtitleConverterUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 1. Directory Selection
        dir_layout = QHBoxLayout()
        self.input_dir = QLineEdit()
        self.input_dir.setPlaceholderText("Select folder containing SRT files...")
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.select_directory)
        dir_layout.addWidget(QLabel("Folder:"))
        dir_layout.addWidget(self.input_dir)
        dir_layout.addWidget(btn_browse)
        
        # 2. Dual Font Settings (NEW)
        font_group = QGroupBox("Custom Font & Size Settings")
        font_layout = QVBoxLayout() # Stack them vertically
        
        # Load system fonts once
        font_db = QFontDatabase()
        system_fonts = font_db.families()
        
        # --- Bottom (Dialogue) Row ---
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(QLabel("Dialogue (Bottom):"))
        
        self.font_combo_bottom = QComboBox()
        self.font_combo_bottom.addItems(system_fonts)
        default_idx_bottom = self.font_combo_bottom.findText("Arial")
        if default_idx_bottom >= 0:
            self.font_combo_bottom.setCurrentIndex(default_idx_bottom)
        bottom_layout.addWidget(self.font_combo_bottom)
        
        bottom_layout.addWidget(QLabel("Size:"))
        self.spin_size_bottom = QSpinBox()
        self.spin_size_bottom.setRange(10, 150)
        self.spin_size_bottom.setValue(52)
        bottom_layout.addWidget(self.spin_size_bottom)
        
        # --- Top (Signs & Songs) Row ---
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Signs/Songs (Top):"))
        
        self.font_combo_top = QComboBox()
        self.font_combo_top.addItems(system_fonts)
        default_idx_top = self.font_combo_top.findText("Arial")
        if default_idx_top >= 0:
            self.font_combo_top.setCurrentIndex(default_idx_top)
        top_layout.addWidget(self.font_combo_top)
        
        top_layout.addWidget(QLabel("Size:"))
        self.spin_size_top = QSpinBox()
        self.spin_size_top.setRange(10, 150)
        self.spin_size_top.setValue(44) # Defaulted to slightly smaller
        top_layout.addWidget(self.spin_size_top)
        
        font_layout.addLayout(bottom_layout)
        font_layout.addLayout(top_layout)
        font_group.setLayout(font_layout)

        # 3. Smart Rules Configuration
        rules_group = QGroupBox("Smart Detection Rules (Send to Top)")
        rules_layout = QVBoxLayout()
        
        self.chk_music = QCheckBox("Send lines with musical notes to top (♪, ♫, ♬, #)")
        self.chk_music.setChecked(True)
        
        self.chk_brackets = QCheckBox("Extract bracketed text and send to top (e.g. (Sign) Dialogue)")
        self.chk_brackets.setChecked(True)
        
        self.chk_caps = QCheckBox("Send completely ALL CAPS lines to top")
        self.chk_caps.setChecked(True)
        
        # Exception Rule
        exception_layout = QHBoxLayout()
        exception_layout.addWidget(QLabel("Ignore brackets containing:"))
        self.input_exceptions = QLineEdit("years, ago, later, day, episode")
        self.input_exceptions.setPlaceholderText("Comma separated words...")
        exception_layout.addWidget(self.input_exceptions)
        
        rules_layout.addWidget(self.chk_music)
        rules_layout.addWidget(self.chk_brackets)
        rules_layout.addLayout(exception_layout)
        rules_layout.addWidget(self.chk_caps)
        rules_group.setLayout(rules_layout)

        # 4. Action Button
        self.btn_run = QPushButton("Convert SRT to Styled ASS")
        self.btn_run.setStyleSheet("background-color: #673AB7; color: white; font-weight: bold; padding: 10px;")
        self.btn_run.clicked.connect(self.process_subtitles)
        
        # 5. Logs
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # Assembly
        layout.addLayout(dir_layout)
        layout.addWidget(font_group)
        layout.addWidget(rules_group)
        layout.addWidget(self.btn_run)
        layout.addWidget(self.log_output)

    def select_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()

    def srt_time_to_ass(self, srt_time_str):
        srt_time_str = srt_time_str.strip().replace(',', '.')
        parts = srt_time_str.split(':')
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = parts[1]
            seconds = float(parts[2])
            return f"{hours}:{minutes}:{seconds:05.2f}"
        return "0:00:00.00"

    def is_all_caps(self, text):
        alpha_only = ''.join(c for c in text if c.isalpha())
        return bool(alpha_only and alpha_only.isupper())

    def contains_exception(self, text, exceptions_list):
        text_lower = text.lower()
        for word in exceptions_list:
            if word and word in text_lower:
                return True
        return False

    def process_subtitles(self):
        folder_path = self.input_dir.text()
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Error", "Invalid folder selection.")
            return
            
        target_dir = Path(folder_path)
        srt_files = list(target_dir.glob("*.srt"))
        
        if not srt_files:
            self.log("No .srt files found in this directory.", "orange")
            return
            
        output_dir = target_dir / "Converted_ASS"
        output_dir.mkdir(exist_ok=True)
            
        self.btn_run.setEnabled(False)
        self.log("--- Starting Subtitle Processing ---", "blue")
        
        # Fetch Independent Custom Settings
        font_name_bottom = self.font_combo_bottom.currentText()
        font_name_top = self.font_combo_top.currentText()
        size_bottom = self.spin_size_bottom.value()
        size_top = self.spin_size_top.value()
        
        raw_exceptions = self.input_exceptions.text().split(',')
        exceptions = [word.strip().lower() for word in raw_exceptions if word.strip()]
        
        # Dynamic ASS Header Injection with separated variables
        ass_header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{font_name_bottom},{size_bottom},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,2,30,30,40,1\n"
            f"Style: TopSongsSigns,{font_name_top},{size_top},&H0000FFFF,&H000000FF,&H00000000,&H00000000,0,1,0,0,100,100,0,0,1,2,0,8,30,30,40,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        success_count = 0
        
        for srt_path in srt_files:
            try:
                with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
                    srt_content = f.read()

                blocks = srt_content.replace('\r\n', '\n').split('\n\n')
                ass_events = []

                for block in blocks:
                    lines = block.strip().split('\n')
                    if len(lines) < 3:
                        continue
                        
                    time_line = lines[1]
                    if "-->" not in time_line:
                        for l in lines:
                            if "-->" in l:
                                time_line = l
                                break
                        else:
                            continue
                            
                    start_str, end_str = time_line.split("-->")
                    start_ass = self.srt_time_to_ass(start_str)
                    end_ass = self.srt_time_to_ass(end_str)
                    
                    text_lines = lines[lines.index(time_line)+1:]
                    text_raw = " ".join(text_lines).strip()
                    clean_text = re.sub(r'<[^>]*>', '', text_raw)
                    
                    if not clean_text:
                        continue

                    top_segments = []
                    bottom_text = clean_text

                    if self.chk_brackets.isChecked():
                        brackets_found = re.findall(r'([\[\(].*?[\]\)])', bottom_text)
                        for item in brackets_found:
                            if self.contains_exception(item, exceptions):
                                continue 
                                
                            top_segments.append(item)
                            bottom_text = bottom_text.replace(item, "")
                        
                        bottom_text = re.sub(r'^\s*[-–—,.;:]+\s*', '', bottom_text).strip()

                    if self.chk_music.isChecked() and any(char in bottom_text for char in ['♪', '♫', '♩', '♬', '#']):
                        top_segments.append(bottom_text)
                        bottom_text = ""

                    if self.chk_caps.isChecked() and bottom_text and self.is_all_caps(bottom_text):
                        top_segments.append(bottom_text)
                        bottom_text = ""

                    for segment in top_segments:
                        if segment.strip():
                            ass_events.append(f"Dialogue: 0,{start_ass},{end_ass},TopSongsSigns,,0,0,0,,{segment.strip()}\n")

                    if bottom_text.strip():
                        ass_events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{bottom_text.strip()}\n")

                ass_path = output_dir / f"{srt_path.stem}.ass"
                with open(ass_path, 'w', encoding='utf-8') as f:
                    f.write(ass_header)
                    f.writelines(ass_events)
                    
                self.log(f"Converted & Sorted: '{srt_path.name}'", "green")
                success_count += 1
                
            except Exception as e:
                self.log(f"Failed processing '{srt_path.name}': {str(e)}", "red")

        self.log(f"--- Completed: {success_count} files sorted into 'Converted_ASS' folder ---", "blue")
        self.btn_run.setEnabled(True)

class SubtitleConverterPlugin(FeaturePlugin):
    @property
    def name(self):
        return "Smart Subtitle Converter"

    @property
    def description(self):
        return "Converts SRT to ASS, automatically sorting signs/songs with fully independent dual-font controls."

    def get_ui(self, parent=None):
        return SubtitleConverterUI(parent)