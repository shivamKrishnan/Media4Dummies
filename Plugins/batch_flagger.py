# plugins/batch_flagger.py
import os
import json
import subprocess
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QLineEdit, QTextEdit, 
    QApplication, QGroupBox, QComboBox, QMessageBox
)
from plugin_base import FeaturePlugin

# --- DICTIONARIES & LOGIC ---

# 1. Translation dictionary for "Dummies": Maps short codes to Long Names
FRIENDLY_NAMES = {
    "und": "Unknown Language",
    "eng": "English", "en": "English",
    "jpn": "Japanese", "ja": "Japanese",
    "chi": "Chinese", "zho": "Chinese", "zh": "Chinese",
    "zh-cn": "Simplified Chinese", "zh-hans": "Simplified Chinese",
    "zh-tw": "Traditional Chinese", "zh-hant": "Traditional Chinese", "zh-hk": "Traditional Chinese",
    "kor": "Korean", "ko": "Korean",
    "tha": "Thai", "th": "Thai",
    "vie": "Vietnamese", "vi": "Vietnamese",
    "ind": "Indonesian", "id": "Indonesian",
    "may": "Malay", "ms": "Malay", "msa": "Malay",
    "tgl": "Tagalog / Filipino", "tl": "Tagalog / Filipino", "fil": "Tagalog / Filipino",
    "hin": "Hindi", "hi": "Hindi",
    "tam": "Tamil", "ta": "Tamil",
    "tel": "Telugu", "te": "Telugu",
    "ara": "Arabic", "ar": "Arabic",
    "spa": "Spanish", "es": "Spanish",
    "fre": "French", "fra": "French", "fr": "French",
    "ger": "German", "deu": "German", "de": "German",
    "ita": "Italian", "it": "Italian",
    "por": "Portuguese", "pt": "Portuguese", "pt-br": "Brazilian Portuguese",
    "rus": "Russian", "ru": "Russian"
}

# 2. Logic grouping to catch missing/overlapping dialects
LANGUAGE_GROUPS = [
    {"und"}, {"eng", "en"}, {"jpn", "ja"}, {"kor", "ko"},
    {"tha", "th"}, {"vie", "vi"}, {"ind", "id"}, {"may", "ms", "msa"},
    {"tgl", "tl", "fil"}, {"hin", "hi"}, {"tam", "ta"}, {"tel", "te"},
    {"ara", "ar"}, {"spa", "es"}, {"fre", "fra", "fr"}, {"ger", "deu", "de"},
    {"ita", "it"}, {"por", "pt", "pt-br"}, {"rus", "ru"},
    {"chi", "zho", "zh"} # Base Chinese separated from specific dialect
]

DIALECT_EQUIVALENTS = {
    "zh-cn": "zh-hans", "zh-sg": "zh-hans",
    "zh-tw": "zh-hant", "zh-hk": "zh-hant"
}

TYPE_LETTER = {"audio": "a", "video": "v", "subtitles": "s"}

def language_matches(properties, target_lang_norm):
    """Return True if a track matches, safely handling dialects."""
    legacy = str(properties.get("language", "und")).lower()
    ietf = str(properties.get("language_ietf", "")).lower()

    normalized_ietf = DIALECT_EQUIVALENTS.get(ietf, ietf)
    normalized_target = DIALECT_EQUIVALENTS.get(target_lang_norm, target_lang_norm)

    if normalized_target == normalized_ietf: return True
    if normalized_target == legacy: return True

    for group in LANGUAGE_GROUPS:
        if normalized_target in group:
            if legacy in group or normalized_ietf in group:
                if normalized_target in ["zh-hans", "zh-hant"] and normalized_ietf in ["zh-hans", "zh-hant"]:
                    return False
                return True
    return False

# --- UI CLASS ---

class BatchFlaggerUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Store scanned tracks dynamically
        self.discovered_langs = {"subtitles": {}, "audio": {}}
        
        # 1. Directory Selection
        dir_layout = QHBoxLayout()
        self.input_dir = QLineEdit()
        self.input_dir.setPlaceholderText("Select folder containing MKV files...")
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.select_directory)
        dir_layout.addWidget(QLabel("Folder:"))
        dir_layout.addWidget(self.input_dir)
        dir_layout.addWidget(btn_browse)
        
        # 2. Flagging Rules
        rules_group = QGroupBox("Batch Flagging Rules (Modifies Files Instantly)")
        rules_layout = QVBoxLayout()
        
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Find"))
        
        self.combo_type = QComboBox()
        self.combo_type.currentTextChanged.connect(self.update_language_dropdown)
        target_layout.addWidget(self.combo_type)
        
        target_layout.addWidget(QLabel("track in Language:"))
        
        self.combo_lang = QComboBox()
        target_layout.addWidget(self.combo_lang)
        
        target_layout.addWidget(QLabel("and set it to:"))
        self.combo_action = QComboBox()
        self.combo_action.addItems(["Default = ON, Forced = OFF", "Default = ON, Forced = ON", "Remove All Defaults"])
        target_layout.addWidget(self.combo_action)
        
        rules_layout.addLayout(target_layout)
        
        warning_label = QLabel("<i>Note: This will automatically remove the 'Default' flag from all other tracks of the same type.</i>")
        warning_label.setStyleSheet("color: #757575;")
        rules_layout.addWidget(warning_label)
        rules_group.setLayout(rules_layout)

        # 3. Action Button
        self.btn_run = QPushButton("Apply Flags Instantly")
        self.btn_run.setStyleSheet("background-color: #00838F; color: white; font-weight: bold; padding: 10px;")
        self.btn_run.clicked.connect(self.process_flags)
        
        # 4. Logs
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # Assembly
        layout.addLayout(dir_layout)
        layout.addWidget(rules_group)
        layout.addWidget(self.btn_run)
        layout.addWidget(self.log_output)

    def select_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)
            self.scan_folder_for_tracks(folder) # Trigger auto-scan

    def scan_folder_for_tracks(self, folder_path):
        mkvmerge_exe, _ = self.check_tools()
        if not mkvmerge_exe: return
        
        mkv_files = list(Path(folder_path).glob("*.mkv"))
        if not mkv_files:
            self.log("No .mkv files found to scan.", "orange")
            return
            
        self.log(f"Scanning '{mkv_files[0].name}' to detect available tracks...", "blue")
        
        discovered_types = set()
        self.discovered_langs = {"subtitles": {}, "audio": {}}
        
        # Hide the command prompt window on Windows
        cflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        
        try:
            probe = subprocess.run(
                [mkvmerge_exe, "-J", str(mkv_files[0])],
                capture_output=True, text=True, check=True,
                encoding="utf-8", errors="replace", creationflags=cflags
            )
            file_data = json.loads(probe.stdout)
            
            for track in file_data.get("tracks", []):
                t_type = track.get("type")
                if t_type in ["subtitles", "audio"]:
                    discovered_types.add(t_type)
                    
                    props = track.get("properties", {})
                    legacy = str(props.get("language", "und")).lower()
                    ietf = str(props.get("language_ietf", "")).lower()
                    
                    # Prefer the modern IETF code if it exists and isn't undefined
                    best_code = ietf if (ietf and ietf != "und") else legacy
                    
                    # Convert the short code to a Dummy-friendly long name
                    friendly_name = FRIENDLY_NAMES.get(best_code, best_code.title())
                    
                    self.discovered_langs[t_type][best_code] = friendly_name
                    
            # Update the Type Dropdown
            self.combo_type.blockSignals(True) # Prevent double triggering
            self.combo_type.clear()
            self.combo_type.addItems(list(discovered_types))
            self.combo_type.blockSignals(False)
            
            # Populate language combo based on the first type found
            self.update_language_dropdown(self.combo_type.currentText())
            
            self.log("Scan complete. Please select the track you want to edit above.", "green")
            
        except Exception as e:
            self.log(f"Pre-scan failed: {str(e)}", "red")

    def update_language_dropdown(self, current_type):
        """Updates the language dropdown when the user switches between Audio/Subtitles"""
        self.combo_lang.clear()
        if current_type and current_type in self.discovered_langs:
            for code, friendly_name in self.discovered_langs[current_type].items():
                # Display the friendly name (e.g. "Simplified Chinese"), but save the code (e.g. "zh-cn") in the background
                self.combo_lang.addItem(friendly_name, userData=code)

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()

    def check_tools(self):
        settings = QSettings("ModularMedia", "ToolboxSettings")
        mkv_path = settings.value("mkvtoolnix_path", "")
        if not mkv_path:
            QMessageBox.critical(self, "Missing Tool", "MKVToolNix path is not set in Global Settings.")
            return None, None
            
        mkvmerge_exe = os.path.join(mkv_path, "mkvmerge")
        mkvpropedit_exe = os.path.join(mkv_path, "mkvpropedit")
        
        if os.name == 'nt': 
            mkvmerge_exe += ".exe"
            mkvpropedit_exe += ".exe"
            
        if not os.path.exists(mkvmerge_exe) or not os.path.exists(mkvpropedit_exe):
            QMessageBox.critical(self, "Missing Tool", "Could not find mkvmerge or mkvpropedit in the selected directory.")
            return None, None
            
        return mkvmerge_exe, mkvpropedit_exe

    def process_flags(self):
        folder_path = self.input_dir.text().strip()
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Error", "Invalid folder selection.")
            return
            
        mkvmerge_exe, mkvpropedit_exe = self.check_tools()
        if not mkvmerge_exe: return

        mkv_files = list(Path(folder_path).glob("*.mkv"))
        if not mkv_files:
            return

        target_type = self.combo_type.currentText()
        # Retrieve the hidden short code from the dropdown (e.g., 'zh-cn' instead of 'Simplified Chinese')
        target_lang_norm = self.combo_lang.currentData()
        action_idx = self.combo_action.currentIndex()
        type_letter = TYPE_LETTER[target_type]
        
        if not target_lang_norm:
            QMessageBox.warning(self, "Error", "No language selected.")
            return

        self.btn_run.setEnabled(False)
        self.log("--- Starting High-Speed Header Edit ---", "blue")
        success_count = 0
        cflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

        for mkv in mkv_files:
            try:
                probe = subprocess.run(
                    [mkvmerge_exe, "-J", str(mkv)],
                    capture_output=True, text=True, check=True,
                    encoding="utf-8", errors="replace", creationflags=cflags
                )
                file_data = json.loads(probe.stdout)
                
                edit_args = [mkvpropedit_exe, str(mkv)]
                found_target = False
                type_counter = 0 

                for track in file_data.get("tracks", []):
                    if track.get("type") != target_type: continue

                    type_counter += 1
                    selector = f"track:{type_letter}{type_counter}"
                    props = track.get("properties", {})

                    if action_idx == 2:
                        edit_args.extend(["--edit", selector, "--set", "flag-default=0", "--set", "flag-forced=0"])
                        found_target = True
                    elif not found_target and language_matches(props, target_lang_norm):
                        set_forced = "1" if action_idx == 1 else "0"
                        edit_args.extend(["--edit", selector, "--set", "flag-default=1", "--set", f"flag-forced={set_forced}"])
                        found_target = True
                    else:
                        edit_args.extend(["--edit", selector, "--set", "flag-default=0", "--set", "flag-forced=0"])

                if found_target:
                    result = subprocess.run(edit_args, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=cflags)
                    if result.returncode == 0:
                        self.log(f"Updated Flags: {mkv.name}", "green")
                        success_count += 1
                    else:
                        detail = (result.stderr or result.stdout or "unknown error").strip()
                        self.log(f"Failed to edit {mkv.name}: {detail}", "red")
                else:
                    self.log(f"Skipped {mkv.name}: No {target_type} track found matching '{self.combo_lang.currentText()}'.", "orange")
                    
            except subprocess.CalledProcessError as e:
                self.log(f"Failed to probe {mkv.name}", "red")
            except Exception as e:
                self.log(f"Failed to edit {mkv.name}: {str(e)}", "red")

        self.log(f"--- Process Complete: Updated {success_count} files instantly ---", "blue")
        self.btn_run.setEnabled(True)

class BatchFlaggerPlugin(FeaturePlugin):
    @property
    def name(self):
        return "Smart Metadata Flagger"

    @property
    def description(self):
        return "Instantly change Default and Forced tags in MKV files without re-encoding or remuxing."

    def get_ui(self, parent=None):
        return BatchFlaggerUI(parent)