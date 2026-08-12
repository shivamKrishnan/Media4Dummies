# plugins/title_changer.py
import os
import re
import subprocess
from pathlib import Path

# Added the missing QSettings import
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QLineEdit, QTextEdit, QApplication
)
from plugin_base import FeaturePlugin

class TitleChangerUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # --- UI Elements ---
        self.dir_layout = QHBoxLayout()
        self.lbl_dir = QLabel("Target Folder:")
        self.input_dir = QLineEdit()
        self.input_dir.setPlaceholderText("Select folder containing media files...")
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.clicked.connect(self.select_directory)
        self.dir_layout.addWidget(self.lbl_dir)
        self.dir_layout.addWidget(self.input_dir)
        self.dir_layout.addWidget(self.btn_browse)
        
        self.btn_run = QPushButton("Update Titles")
        self.btn_run.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        self.btn_run.clicked.connect(self.process_files)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        layout.addLayout(self.dir_layout)
        layout.addWidget(self.btn_run)
        layout.addWidget(self.log_output)

    def select_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def parse_filename(self, filename: str):
        """
        Advanced parser utilizing sequential cascading regex to capture 
        show names, seasons, and episodes across distinct layout conventions.
        """
        # 1. Remove file extension
        name_clean = Path(filename).stem
        
        # 2. Strip off leading release group tags like [Animekayo] or [Cleo]
        name_clean = re.sub(r'^\[[^\]]+\]\s*', '', name_clean)
        
        # 3. Define cascading patterns
        pattern_s_e = re.compile(r'^(.*?)[._\-\s]+[Ss](\d+)[._\-\s]*[Ee_]+(\d+)')
        pattern_explicit_e = re.compile(r'^(.*?)[._\-\s]+(?:[Ee][Pp]?|Episode)[._\-\s]*(\d+)', re.IGNORECASE)
        pattern_trailing_e = re.compile(r'^(.*?)[._\-\s]*[-_]+[._\-\s]*(\d+)\b')
        pattern_leading_e = re.compile(r'^(\d+)[.\s_-]+(.*)')

        # --- Evaluation Cascade ---
        
        # Check Pattern A (Season + Episode)
        match = pattern_s_e.match(name_clean)
        if match:
            show = match.group(1)
            season = match.group(2).zfill(2)
            episode = match.group(3).zfill(2)
            return self.clean_show_name(show), season, episode

        # Check Pattern B (Explicit Episode Only)
        match = pattern_explicit_e.match(name_clean)
        if match:
            show = match.group(1)
            episode = match.group(2).zfill(2)
            return self.clean_show_name(show), None, episode

        # Check Pattern C (Trailing Number Divider)
        match = pattern_trailing_e.match(name_clean)
        if match:
            show = match.group(1)
            episode = match.group(2).zfill(2)
            return self.clean_show_name(show), None, episode

        # Check Pattern D (Leading Number layout)
        match = pattern_leading_e.match(name_clean)
        if match:
            episode = match.group(1).zfill(2)
            show = match.group(2)
            return self.clean_show_name(show), None, episode

        return None, None, None

    def clean_show_name(self, show_name: str) -> str:
        """Cleans up internal delimiters and residual trailing metadata tags."""
        # Replace dots and underscores with clean single spaces
        show = re.sub(r'[._]+', ' ', show_name)
        # Strip common trailing video resolution noise if regex missed it
        show = re.sub(r'\b(720p|1080p|2160p|4k|10bit|bd|dual audio)\b.*', '', show, flags=re.IGNORECASE)
        # Clean double spaces and loose boundaries
        return show.strip()

    def process_files(self):
        folder_path = self.input_dir.text()
        
        settings = QSettings("ModularMedia", "ToolboxSettings")
        mkv_folder = settings.value("mkvtoolnix_path", "")
        
        if not mkv_folder:
            self.log("Error: MKVToolNix path not set! Go to Global Settings.", "red")
            return
            
        mkvpropedit_exe = os.path.join(mkv_folder, "mkvpropedit")
        if os.name == 'nt':
            mkvpropedit_exe += ".exe"
            
        if not os.path.exists(mkvpropedit_exe):
            self.log(f"Error: Could not find mkvpropedit at {mkvpropedit_exe}", "red")
            return

        target_dir = Path(folder_path)
        if not folder_path or not target_dir.is_dir():
            self.log("Error: Please select a valid directory.", "red")
            return
            
        mkv_files = list(target_dir.glob("*.mkv")) + list(target_dir.glob("*.mp4"))
        
        if not mkv_files:
            self.log("No media files found.", "orange")
            return

        self.log(f"--- Starting Processing in: {folder_path} ---", "blue")

        for filepath in mkv_files:
            show, season, ep = self.parse_filename(filepath.name)
            
            if show and ep:
                if season:
                    new_title = f"{show} - Season {season} Episode {ep}"
                else:
                    new_title = f"{show} - Episode {ep}"
                
                self.log(f"Matched: '{filepath.name}' &rarr; Title: '{new_title}'", "green")
                
                # Run mkvpropedit for MKV containers
                if filepath.suffix.lower() == ".mkv":
                    try:
                        subprocess.run(
                            [mkvpropedit_exe, str(filepath), "--edit", "info", "--set", f"title={new_title}"],
                            check=True, capture_output=True, text=True
                        )
                    except Exception as e:
                        self.log(f"Execution failed for {filepath.name}: {str(e)}", "red")
            else:
                self.log(f"Skipped: Pattern unmatched for '{filepath.name}'", "gray")
                
        self.log("--- Processing Complete ---", "blue")

class TitleChangerPlugin(FeaturePlugin):
    @property
    def name(self):
        return "Smart Title Fixer"

    @property
    def description(self):
        return "Intelligently parses mixed-format file names to clean and apply embedded titles."

    def get_ui(self, parent=None):
        return TitleChangerUI(parent)