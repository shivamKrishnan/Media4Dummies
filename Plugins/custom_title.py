# plugins/custom_title.py
import os
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QLineEdit, QTextEdit, 
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox
)
from plugin_base import FeaturePlugin

class CustomTitleUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 1. Directory Selection
        dir_layout = QHBoxLayout()
        self.input_dir = QLineEdit()
        self.input_dir.setPlaceholderText("Select folder...")
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.select_directory)
        dir_layout.addWidget(QLabel("Folder:"))
        dir_layout.addWidget(self.input_dir)
        dir_layout.addWidget(btn_browse)
        
        # 2. Dummy-Proof Instructions
        cheat_sheet = QGroupBox("Cheat Sheet: Available Tags")
        cheat_layout = QVBoxLayout()
        lbl_help = QLabel(
            "<b>{show}</b> = The series name<br>"
            "<b>{season}</b> = The season number<br>"
            "<b>{episode}</b> = The episode number<br>"
            "<b>{title}</b> = The episode name<br>"
            "<b>{ignore}</b> = Skip this part of the filename (e.g. release group tags)"
        )
        cheat_layout.addWidget(lbl_help)
        cheat_sheet.setLayout(cheat_layout)

        # 3. Custom Logic Inputs
        logic_layout = QHBoxLayout()
        
        self.input_pattern = QLineEdit()
        self.input_pattern.setPlaceholderText("e.g. [{ignore}] {show} - {episode} - {title}")
        
        self.input_template = QLineEdit()
        self.input_template.setPlaceholderText("e.g. {show} - Episode {episode}: {title}")
        
        logic_layout.addWidget(QLabel("Match Pattern:"))
        logic_layout.addWidget(self.input_pattern)
        logic_layout.addWidget(QLabel("New Title Format:"))
        logic_layout.addWidget(self.input_template)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        btn_preview = QPushButton("Preview Changes")
        btn_preview.setStyleSheet("background-color: #1976D2; color: white;")
        btn_preview.clicked.connect(self.generate_preview)
        
        self.btn_run = QPushButton("Apply to Files")
        self.btn_run.setStyleSheet("background-color: #2E7D32; color: white;")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.process_files)
        
        btn_layout.addWidget(btn_preview)
        btn_layout.addWidget(self.btn_run)

        # 5. Preview Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Original Filename", "New Title", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        # 6. Log Output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(100)
        
        # --- Assembly ---
        layout.addLayout(dir_layout)
        layout.addWidget(cheat_sheet)
        layout.addLayout(logic_layout)
        layout.addLayout(btn_layout)
        layout.addWidget(self.table)
        layout.addWidget(self.log_output)

        self.pending_changes = []

    def select_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)
            self.table.setRowCount(0)
            self.btn_run.setEnabled(False)

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def compile_dummy_pattern(self, user_pattern):
        """Converts friendly {tags} into a hidden Regex engine."""
        # Maps user tags to named Regex capture groups
        tag_map = {
            "{show}": r"(?P<show>.*?)",
            "{season}": r"(?P<season>\d+)",
            "{episode}": r"(?P<episode>\d+)",
            "{title}": r"(?P<title>.*?)",
            "{ignore}": r".*?" # Matches anything, but doesn't save it
        }

        # Split the string by brackets to separate text from tags
        parts = re.split(r'(\{.*?\})', user_pattern)
        
        final_regex = "^"
        for part in parts:
            if part in tag_map:
                final_regex += tag_map[part]
            elif part.startswith("{") and part.endswith("}"):
                # If they typed a tag we don't support, just treat it as plain text
                final_regex += re.escape(part)
            else:
                # Escape standard text so things like [ ] or . don't break the regex
                final_regex += re.escape(part)
                
        # We don't append $ here so trailing tags like 1080p are safely ignored if not typed
        return re.compile(final_regex, re.IGNORECASE)

    def generate_preview(self):
        folder_path = self.input_dir.text()
        pattern_str = self.input_pattern.text()
        template_str = self.input_template.text()
        
        if not folder_path or not pattern_str or not template_str:
            QMessageBox.warning(self, "Missing Info", "Please fill in the folder, pattern, and template.")
            return
            
        target_dir = Path(folder_path)
        if not target_dir.is_dir():
            self.log("Invalid directory.", "red")
            return

        # 1. Convert user's friendly pattern to real Regex
        try:
            regex_engine = self.compile_dummy_pattern(pattern_str)
        except Exception as e:
            QMessageBox.critical(self, "Pattern Error", f"Could not read pattern:\n{str(e)}")
            return

        self.table.setRowCount(0)
        self.pending_changes = []
        
        mkv_files = list(target_dir.glob("*.mkv")) + list(target_dir.glob("*.mp4"))
        
        for filepath in mkv_files:
            filename_no_ext = filepath.stem
            match = regex_engine.search(filename_no_ext)
            
            if match:
                # match.groupdict() returns a dictionary of the named tags they used
                captured_data = match.groupdict()
                try:
                    # Inject those tags into their output template
                    new_title = template_str.format(**captured_data)
                    status = "Ready"
                    self.pending_changes.append((filepath, new_title))
                except KeyError as e:
                    new_title = f"Error: You used {e} in the output, but not in the match pattern."
                    status = "Failed"
            else:
                new_title = "No Match"
                status = "Skipped"

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(filepath.name))
            self.table.setItem(row, 1, QTableWidgetItem(new_title))
            self.table.setItem(row, 2, QTableWidgetItem(status))

        if self.pending_changes:
            self.btn_run.setEnabled(True)
            self.log(f"Preview generated. {len(self.pending_changes)} files ready for update.", "blue")
        else:
            self.btn_run.setEnabled(False)
            self.log("No files matched your pattern.", "orange")

    def process_files(self):
        settings = QSettings("ModularMedia", "ToolboxSettings")
        mkv_folder = settings.value("mkvtoolnix_path", "")
        
        if not mkv_folder:
            QMessageBox.critical(self, "Error", "MKVToolNix path not set in Global Settings.")
            return
            
        mkvpropedit_exe = os.path.join(mkv_folder, "mkvpropedit")
        if os.name == 'nt':
            mkvpropedit_exe += ".exe"
            
        self.btn_run.setEnabled(False)
        self.log("--- Applying Custom Titles ---", "blue")

        for filepath, new_title in self.pending_changes:
            if filepath.suffix.lower() == ".mkv":
                try:
                    subprocess.run(
                        [mkvpropedit_exe, str(filepath), "--edit", "info", "--set", f"title={new_title}"],
                        check=True, capture_output=True, text=True
                    )
                    self.log(f"Success: '{filepath.name}' -> '{new_title}'", "green")
                except Exception as e:
                    self.log(f"Failed '{filepath.name}': {str(e)}", "red")
            else:
                self.log(f"Skipped {filepath.name} (Not an MKV)", "gray")
                
        self.log("--- Finished ---", "blue")
        self.pending_changes = []

class CustomTitlePlugin(FeaturePlugin):
    @property
    def name(self):
        return "Custom Builder (Titles)"

    @property
    def description(self):
        return "Use friendly tags to format MKV titles exactly how you want."

    def get_ui(self, parent=None):
        return CustomTitleUI(parent)