# plugins/batch_muxer.py
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QLineEdit, QTextEdit, 
    QApplication, QGroupBox, QCheckBox, QMessageBox, QComboBox
)
from plugin_base import FeaturePlugin

class BatchMuxerUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 1. Directory Selections
        dirs_group = QGroupBox("Directory Setup")
        dirs_layout = QVBoxLayout()
        
        # Video Folder
        vid_layout = QHBoxLayout()
        self.input_vid_dir = QLineEdit()
        self.input_vid_dir.setPlaceholderText("Select folder with Base Video files (.mkv, .mp4)...")
        btn_vid = QPushButton("Browse")
        btn_vid.clicked.connect(lambda: self.select_directory(self.input_vid_dir))
        vid_layout.addWidget(QLabel("Videos:"))
        vid_layout.addWidget(self.input_vid_dir)
        vid_layout.addWidget(btn_vid)
        
        # Track Folder
        trk_layout = QHBoxLayout()
        self.input_trk_dir = QLineEdit()
        self.input_trk_dir.setPlaceholderText("Select folder with Tracks to add (.ass, .srt, .mka, .aac)...")
        btn_trk = QPushButton("Browse")
        btn_trk.clicked.connect(lambda: self.select_directory(self.input_trk_dir))
        trk_layout.addWidget(QLabel("Tracks:"))
        trk_layout.addWidget(self.input_trk_dir)
        trk_layout.addWidget(btn_trk)
        
        dirs_layout.addLayout(vid_layout)
        dirs_layout.addLayout(trk_layout)
        dirs_group.setLayout(dirs_layout)
        
        # 2. Track Properties Configuration
        props_group = QGroupBox("New Track Properties")
        props_layout = QHBoxLayout()
        
        props_layout.addWidget(QLabel("Language Code:"))
        self.input_lang = QComboBox()
        self.input_lang.setEditable(True)
        # Add common ISO 639-2 codes
        self.input_lang.addItems(["eng", "jpn", "spa", "fre", "ger", "chi", "kor", "und"])
        props_layout.addWidget(self.input_lang)
        
        props_layout.addWidget(QLabel("Track Name:"))
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("e.g., English (Styled)")
        props_layout.addWidget(self.input_name)
        
        self.chk_default = QCheckBox("Set as Default Track")
        self.chk_default.setChecked(True)
        props_layout.addWidget(self.chk_default)
        
        self.chk_forced = QCheckBox("Set as Forced Track")
        props_layout.addWidget(self.chk_forced)
        
        props_group.setLayout(props_layout)

        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_scan = QPushButton("Preview Matches")
        self.btn_scan.setStyleSheet("background-color: #455A64; color: white;")
        self.btn_scan.clicked.connect(self.scan_matches)
        
        self.btn_run = QPushButton("Start Batch Muxing")
        self.btn_run.setStyleSheet("background-color: #E65100; color: white; font-weight: bold;")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.process_muxing)
        
        btn_layout.addWidget(self.btn_scan)
        btn_layout.addWidget(self.btn_run)
        
        # 4. Logs
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # Assembly
        layout.addWidget(dirs_group)
        layout.addWidget(props_group)
        layout.addLayout(btn_layout)
        layout.addWidget(self.log_output)

        self.match_map = {} # Maps Video Path -> Track Path

    def select_directory(self, line_edit):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            line_edit.setText(folder)
            self.btn_run.setEnabled(False)
            self.match_map.clear()

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()

    def check_mkvtoolnix(self):
        settings = QSettings("ModularMedia", "ToolboxSettings")
        mkv_path = settings.value("mkvtoolnix_path", "")
        if not mkv_path:
            QMessageBox.critical(self, "Missing Tool", "MKVToolNix path is not set in Global Settings.")
            return None
            
        mkvmerge_exe = os.path.join(mkv_path, "mkvmerge")
        if os.name == 'nt': 
            mkvmerge_exe += ".exe"
            
        if not os.path.exists(mkvmerge_exe):
            QMessageBox.critical(self, "Missing Tool", f"mkvmerge not found at:\n{mkvmerge_exe}")
            return None
            
        return mkvmerge_exe

    def scan_matches(self):
        vid_dir = self.input_vid_dir.text().strip()
        trk_dir = self.input_trk_dir.text().strip()
        
        if not os.path.isdir(vid_dir) or not os.path.isdir(trk_dir):
            QMessageBox.warning(self, "Error", "Please select valid directories for both Videos and Tracks.")
            return
            
        self.log_output.clear()
        self.match_map.clear()
        
        video_exts = {".mkv", ".mp4", ".avi", ".m4v"}
        videos = [p for p in Path(vid_dir).iterdir() if p.is_file() and p.suffix.lower() in video_exts]
        tracks = [p for p in Path(trk_dir).iterdir() if p.is_file()]
        
        if not videos:
            self.log("No compatible video files found in the Video directory.", "red")
            return
            
        self.log("--- Scanning for Matches ---", "blue")
        
        for vid in videos:
            match_found = False
            for trk in tracks:
                # STEM MATCHING: "Frieren - S01E01" perfectly matches "Frieren - S01E01.ass" 
                # or even "Frieren - S01E01_eng.srt"
                if trk.stem.startswith(vid.stem):
                    self.match_map[vid] = trk
                    self.log(f"Matched: <b>{vid.name}</b> &rarr; <b>{trk.name}</b>", "green")
                    match_found = True
                    break # Stop looking for this video once we find a match
                    
            if not match_found:
                self.log(f"No track match found for: {vid.name}", "orange")
                
        if self.match_map:
            self.log(f"<b>Ready to mux {len(self.match_map)} files.</b>", "blue")
            self.btn_run.setEnabled(True)
        else:
            self.log("No valid pairs found. Make sure file names match.", "red")

    def process_muxing(self):
        mkvmerge_exe = self.check_mkvtoolnix()
        if not mkvmerge_exe: return
        
        output_dir = Path(self.input_vid_dir.text()) / "Muxed_Output"
        output_dir.mkdir(exist_ok=True)
        
        lang = self.input_lang.currentText().strip() or "und"
        trk_name = self.input_name.text().strip()
        is_default = "yes" if self.chk_default.isChecked() else "no"
        is_forced = "yes" if self.chk_forced.isChecked() else "no"
        
        self.btn_run.setEnabled(False)
        self.btn_scan.setEnabled(False)
        self.log("--- Starting Batch Mux ---", "blue")
        
        success_count = 0
        
        for vid_path, trk_path in self.match_map.items():
            out_path = output_dir / f"{vid_path.stem}.mkv"
            
            # Base command setup
            cmd = [mkvmerge_exe, "-o", str(out_path), str(vid_path)]
            
            # Apply flags to the incoming track (Track ID 0 of the standalone track file)
            cmd.extend(["--language", f"0:{lang}"])
            cmd.extend(["--default-track", f"0:{is_default}"])
            cmd.extend(["--forced-track", f"0:{is_forced}"])
            
            if trk_name:
                cmd.extend(["--track-name", f"0:{trk_name}"])
                
            # Finally, add the track file to the command
            cmd.append(str(trk_path))
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                self.log(f"Successfully Muxed: {out_path.name}", "green")
                success_count += 1
            except subprocess.CalledProcessError as e:
                self.log(f"Failed to mux {vid_path.name}: {e.stderr.decode('utf-8', errors='ignore')}", "red")
            except Exception as e:
                self.log(f"Error processing {vid_path.name}: {str(e)}", "red")
                
        self.log(f"--- Completed: {success_count} files saved to 'Muxed_Output' folder ---", "blue")
        self.btn_run.setEnabled(True)
        self.btn_scan.setEnabled(True)


class BatchMuxerPlugin(FeaturePlugin):
    @property
    def name(self):
        return "Smart Batch Muxer"

    @property
    def description(self):
        return "Automatically pairs and merges subtitles or audio tracks into your videos based on filenames."

    def get_ui(self, parent=None):
        return BatchMuxerUI(parent)