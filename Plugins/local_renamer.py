# plugins/local_renamer.py
import os
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QLineEdit, QTextEdit, 
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QCheckBox
)
from plugin_base import FeaturePlugin

class LocalRenamerUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 1. Directory Selection
        dir_layout = QHBoxLayout()
        self.input_dir = QLineEdit()
        self.input_dir.setPlaceholderText("Select folder containing files to rename...")
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.select_directory)
        dir_layout.addWidget(QLabel("Folder:"))
        dir_layout.addWidget(self.input_dir)
        dir_layout.addWidget(btn_browse)
        
        # 2. PowerRename Controls
        power_group = QGroupBox("Search and Replace")
        power_layout = QVBoxLayout()
        
        # Search / Replace Inputs
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search for:"))
        self.input_find = QLineEdit()
        search_layout.addWidget(self.input_find)
        
        search_layout.addWidget(QLabel("Replace with:"))
        self.input_replace = QLineEdit()
        search_layout.addWidget(self.input_replace)
        
        # Options Toggles
        options_layout = QHBoxLayout()
        self.chk_regex = QCheckBox("Use Regular Expressions")
        self.chk_case = QCheckBox("Match Case")
        self.chk_ext = QCheckBox("Ignore Extension (Recommended)")
        self.chk_ext.setChecked(True) # Safe default for media files
        
        options_layout.addWidget(self.chk_regex)
        options_layout.addWidget(self.chk_case)
        options_layout.addWidget(self.chk_ext)
        options_layout.addStretch()
        
        power_layout.addLayout(search_layout)
        power_layout.addLayout(options_layout)
        power_group.setLayout(power_layout)

        # Connect signals for Live Preview
        self.input_find.textChanged.connect(self.update_preview)
        self.input_replace.textChanged.connect(self.update_preview)
        self.chk_regex.stateChanged.connect(self.update_preview)
        self.chk_case.stateChanged.connect(self.update_preview)
        self.chk_ext.stateChanged.connect(self.update_preview)

        # 3. Preview Grid
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Original Filename", "Renamed Filename"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 4. Action Button
        self.btn_rename = QPushButton("Apply Renaming")
        self.btn_rename.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 8px;")
        self.btn_rename.setEnabled(False)
        self.btn_rename.clicked.connect(self.execute_renaming)
        
        # 5. Logs
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(100)
        
        # Assembly
        layout.addLayout(dir_layout)
        layout.addWidget(power_group)
        layout.addWidget(self.table)
        layout.addWidget(self.btn_rename)
        layout.addWidget(self.log_output)

        self.rename_map = {} 
        self.cached_files = [] 

    def select_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)
            self.load_files()

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()

    def load_files(self):
        folder_path = self.input_dir.text()
        if not os.path.isdir(folder_path):
            return

        self.cached_files.clear()
        
        # Load all files in the directory (ignoring subfolders)
        self.cached_files = [p for p in Path(folder_path).iterdir() if p.is_file()]
        
        if not self.cached_files:
            self.log("No files found in this directory.", "orange")
            self.table.setRowCount(0)
            return

        self.log(f"Loaded {len(self.cached_files)} files. Ready to rename.", "blue")
        self.update_preview()

    def update_preview(self):
        """Redraws the table grid instantly based on Find/Replace inputs."""
        if not self.cached_files:
            return

        find_str = self.input_find.text()
        replace_str = self.input_replace.text()
        use_regex = self.chk_regex.isChecked()
        match_case = self.chk_case.isChecked()
        ignore_ext = self.chk_ext.isChecked()

        self.table.setRowCount(0)
        self.rename_map.clear()

        # Pre-compile regex if needed, handle invalid regex typing gracefully
        pattern = None
        if find_str:
            try:
                flags = 0 if match_case else re.IGNORECASE
                if use_regex:
                    pattern = re.compile(find_str, flags)
                else:
                    # Escape raw text so symbols like [ or . don't trigger regex logic
                    pattern = re.compile(re.escape(find_str), flags)
            except re.error:
                # User is in the middle of typing an invalid regex (e.g., "[108")
                pattern = None 

        row = 0
        changes_detected = False

        for filepath in self.cached_files:
            orig_name = filepath.name
            new_name = orig_name

            if pattern:
                if ignore_ext:
                    # Modify only the stem, keep the original extension intact
                    stem = filepath.stem
                    ext = filepath.suffix
                    new_stem = pattern.sub(replace_str, stem)
                    new_name = f"{new_stem}{ext}"
                else:
                    # Modify the entire filename including extension
                    new_name = pattern.sub(replace_str, orig_name)

            # Sanitize illegal characters just in case the user typed them in 'Replace'
            new_name = re.sub(r'[\\/*?:"<>|]', "", new_name)

            # Insert into grid
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(orig_name))
            
            new_item = QTableWidgetItem(new_name)
            if new_name != orig_name:
                new_item.setForeground(Qt.darkGreen) # Highlight changed files in green
                self.rename_map[filepath] = filepath.parent / new_name
                changes_detected = True
            
            self.table.setItem(row, 1, new_item)
            row += 1

        self.btn_rename.setEnabled(changes_detected)

    def execute_renaming(self):
        success_count = 0
        self.log("Applying renaming rules...", "blue")
        
        for old_path, new_path in list(self.rename_map.items()):
            # Prevent overwriting if a file with the new name already exists
            if new_path.exists() and old_path != new_path:
                self.log(f"Skipped {old_path.name}: A file named {new_path.name} already exists.", "red")
                continue

            try:
                if old_path.exists():
                    old_path.rename(new_path)
                    success_count += 1
            except Exception as e:
                self.log(f"Failed to rename {old_path.name}: {e}", "red")

        self.log(f"Process complete. Successfully renamed {success_count} files.", "green")
        
        # Reload directory to reflect the new state on the hard drive
        self.load_files()

class LocalRenamerPlugin(FeaturePlugin):
    @property
    def name(self):
        return "Power Batch Renamer"

    @property
    def description(self):
        return "A live-preview renaming engine with support for Search & Replace and Regular Expressions."

    def get_ui(self, parent=None):
        return LocalRenamerUI(parent)