# plugins/track_extractor.py
import os
import json
import subprocess
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QLineEdit, QTextEdit, 
    QApplication, QListWidget, QListWidgetItem, QGroupBox, QMessageBox
)
from plugin_base import FeaturePlugin

class TrackExtractorUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 1. Directory Selection
        dir_layout = QHBoxLayout()
        self.input_dir = QLineEdit()
        self.input_dir.setPlaceholderText("Select folder containing video files...")
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.select_directory)
        dir_layout.addWidget(QLabel("Folder:"))
        dir_layout.addWidget(self.input_dir)
        dir_layout.addWidget(btn_browse)
        
        self.btn_scan = QPushButton("Scan Folder for Blueprint")
        self.btn_scan.setStyleSheet("background-color: #455A64; color: white;")
        self.btn_scan.clicked.connect(self.scan_folder)

        # 2. Track Preview Checklist
        preview_group = QGroupBox("Smart Blueprint (Auto-Routes to MKVToolNix or FFmpeg)")
        preview_layout = QVBoxLayout()
        self.track_list = QListWidget()
        preview_layout.addWidget(self.track_list)
        preview_group.setLayout(preview_layout)

        # 3. Action Button
        self.btn_run = QPushButton("Extract Selected Tracks")
        self.btn_run.setStyleSheet("background-color: #E65100; color: white; font-weight: bold;")
        self.btn_run.setEnabled(False) 
        self.btn_run.clicked.connect(self.process_files)
        
        # 4. Log Output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        layout.addLayout(dir_layout)
        layout.addWidget(self.btn_scan)
        layout.addWidget(preview_group)
        layout.addWidget(self.btn_run)
        layout.addWidget(self.log_output)

        self.video_files = []
        self.blueprint_ext = "" # Stores whether the current batch is .mkv, .mp4, etc.
        self.router_engine = "" # "mkvtoolnix" or "ffmpeg"

    def select_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)
            self.track_list.clear()
            self.btn_run.setEnabled(False)

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def get_extension(self, codec):
        """Universal codec mapper for both MKVToolNix and FFmpeg outputs."""
        codec = codec.lower()
        if "subrip" in codec: return ".srt"
        if "ass" in codec or "ssa" in codec: return ".ass"
        if "pgs" in codec or "hdmv_pgs_subtitle" in codec: return ".sup"
        if "dvd_subtitle" in codec or "vobsub" in codec: return ".idx"
        if "mov_text" in codec or "tx3g" in codec: return ".srt" 
        if "aac" in codec: return ".aac"
        if "ac3" in codec: return ".ac3"
        if "eac3" in codec: return ".eac3"
        if "flac" in codec: return ".flac"
        if "mp3" in codec: return ".mp3"
        if "opus" in codec: return ".opus"
        if "vorbis" in codec: return ".ogg"
        return ".bin"

    def check_paths(self):
        """Ensures both executables are set up in Global Settings."""
        settings = QSettings("ModularMedia", "ToolboxSettings")
        paths = {
            "mkv": settings.value("mkvtoolnix_path", ""),
            "ff": settings.value("ffmpeg_path", "")
        }
        if not paths["mkv"] or not paths["ff"]:
            QMessageBox.critical(self, "Missing Paths", "Please set BOTH MKVToolNix and FFmpeg paths in Global Settings.")
            return None
        return paths

    def scan_folder(self):
        folder_path = self.input_dir.text()
        paths = self.check_paths()
        if not paths: return

        target_dir = Path(folder_path)
        if not target_dir.is_dir():
            self.log("Invalid directory.", "red")
            return
            
        valid_extensions = (".mkv", ".mp4", ".avi", ".mov", ".m4v")
        self.video_files = [f for f in target_dir.iterdir() if f.suffix.lower() in valid_extensions]
        
        if not self.video_files:
            self.log("No compatible video files found.", "orange")
            return

        self.track_list.clear()
        blueprint_file = self.video_files[0]
        self.blueprint_ext = blueprint_file.suffix.lower()
        
        self.log(f"Anchoring blueprint to: {blueprint_file.name}", "blue")

        # --- SMART ROUTER (SCANNING) ---
        if self.blueprint_ext == ".mkv":
            self.router_engine = "mkvtoolnix"
            mkvmerge_exe = os.path.join(paths["mkv"], "mkvmerge")
            if os.name == 'nt': mkvmerge_exe += ".exe"
            
            try:
                probe = subprocess.run([mkvmerge_exe, "-J", str(blueprint_file)], capture_output=True, text=True, check=True, encoding="utf-8")
                file_data = json.loads(probe.stdout)
                
                for track in file_data.get("tracks", []):
                    if track.get("type") in ["subtitles", "audio"]:
                        track_id = track.get("id")
                        lang = track.get("properties", {}).get("language", "und")
                        codec = track.get("codec", "unknown")
                        display = f"{track.get('type').capitalize()} Track {track_id} ({lang}) - [{codec}]"
                        
                        item = QListWidgetItem(display)
                        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                        item.setCheckState(Qt.Unchecked)
                        item.setData(Qt.UserRole, track_id) 
                        self.track_list.addItem(item)
            except Exception as e:
                self.log(f"MKVToolNix scan failed: {e}", "red")
                return

        else:
            self.router_engine = "ffmpeg"
            ffprobe_exe = os.path.join(paths["ff"], "ffprobe")
            if os.name == 'nt': ffprobe_exe += ".exe"
            
            try:
                probe = subprocess.run([ffprobe_exe, "-v", "quiet", "-print_format", "json", "-show_streams", str(blueprint_file)], capture_output=True, text=True, check=True, encoding="utf-8")
                file_data = json.loads(probe.stdout)
                
                for stream in file_data.get("streams", []):
                    if stream.get("codec_type") in ["subtitle", "audio"]:
                        stream_index = stream.get("index")
                        lang = stream.get("tags", {}).get("language", "und")
                        codec = stream.get("codec_name", "unknown")
                        display = f"{stream.get('codec_type').capitalize()} Stream {stream_index} ({lang}) - [{codec}]"
                        
                        item = QListWidgetItem(display)
                        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                        item.setCheckState(Qt.Unchecked)
                        item.setData(Qt.UserRole, stream_index) 
                        self.track_list.addItem(item)
            except Exception as e:
                self.log(f"FFprobe scan failed: {e}", "red")
                return

        self.btn_run.setEnabled(True)
        self.log(f"Ready. Engine selected: {self.router_engine.upper()}", "green")

    def process_files(self):
        paths = self.check_paths()
        if not paths: return

        selected_ids = [self.track_list.item(i).data(Qt.UserRole) for i in range(self.track_list.count()) if self.track_list.item(i).checkState() == Qt.Checked]

        if not selected_ids:
            QMessageBox.warning(self, "No Selection", "Please check at least one track.")
            return

        base_output_dir = Path(self.input_dir.text()) / "Extracted_Tracks"
        self.btn_run.setEnabled(False)
        self.log(f"--- Starting Smart Extraction ({self.router_engine.upper()}) ---", "blue")

        for filepath in self.video_files:
            # SAFETY CHECK: Only process files matching the blueprint extension!
            if filepath.suffix.lower() != self.blueprint_ext:
                self.log(f"Skipped {filepath.name}: Extension mismatch. Run this file separately.", "orange")
                continue

            # --- SMART ROUTER (EXTRACTION) ---
            if self.router_engine == "mkvtoolnix":
                mkvmerge_exe = os.path.join(paths["mkv"], "mkvmerge")
                mkvextract_exe = os.path.join(paths["mkv"], "mkvextract")
                if os.name == 'nt': 
                    mkvmerge_exe += ".exe"
                    mkvextract_exe += ".exe"

                try:
                    probe = subprocess.run([mkvmerge_exe, "-J", str(filepath)], capture_output=True, text=True, check=True, encoding="utf-8")
                    file_data = json.loads(probe.stdout)
                    
                    extract_args = [mkvextract_exe, "tracks", str(filepath)]
                    tracks_found = 0

                    for track in file_data.get("tracks", []):
                        track_id = track.get("id")
                        if track_id in selected_ids:
                            lang = track.get("properties", {}).get("language", "und")
                            ext = self.get_extension(track.get("codec", ""))
                            lang_dir = base_output_dir / lang
                            lang_dir.mkdir(parents=True, exist_ok=True)
                            out_path = lang_dir / f"{filepath.stem}_Track{track_id}{ext}"
                            extract_args.append(f"{track_id}:{out_path}")
                            tracks_found += 1

                    if tracks_found > 0:
                        subprocess.run(extract_args, check=True, capture_output=True)
                        self.log(f"MKV Success: {filepath.name} &rarr; Extracted {tracks_found} track(s)", "green")
                    else:
                        self.log(f"Skipped: {filepath.name} &rarr; Tracks not found.", "gray")
                except Exception as e:
                    self.log(f"Failed {filepath.name}: {e}", "red")

            elif self.router_engine == "ffmpeg":
                ffmpeg_exe = os.path.join(paths["ff"], "ffmpeg")
                ffprobe_exe = os.path.join(paths["ff"], "ffprobe")
                if os.name == 'nt':
                    ffmpeg_exe += ".exe"
                    ffprobe_exe += ".exe"

                try:
                    probe = subprocess.run([ffprobe_exe, "-v", "quiet", "-print_format", "json", "-show_streams", str(filepath)], capture_output=True, text=True, check=True, encoding="utf-8")
                    file_data = json.loads(probe.stdout)
                    
                    ffmpeg_args = [ffmpeg_exe, "-y", "-i", str(filepath)]
                    tracks_found = 0

                    for stream in file_data.get("streams", []):
                        stream_index = stream.get("index")
                        if stream_index in selected_ids:
                            lang = stream.get("tags", {}).get("language", "und")
                            codec = stream.get("codec_name", "")
                            ext = self.get_extension(codec)
                            
                            lang_dir = base_output_dir / lang
                            lang_dir.mkdir(parents=True, exist_ok=True)
                            out_path = lang_dir / f"{filepath.stem}_Stream{stream_index}{ext}"
                            
                            ffmpeg_args.extend(["-map", f"0:{stream_index}", "-c", "copy", str(out_path)])
                            if codec == "mov_text":
                                ffmpeg_args[-3:-1] = ["-c:s", "srt"]
                            tracks_found += 1

                    if tracks_found > 0:
                        subprocess.run(ffmpeg_args, check=True, capture_output=True)
                        self.log(f"FFmpeg Success: {filepath.name} &rarr; Extracted {tracks_found} track(s)", "green")
                    else:
                        self.log(f"Skipped: {filepath.name} &rarr; Streams not found.", "gray")
                except Exception as e:
                    self.log(f"Failed {filepath.name}: {e}", "red")

        self.log("--- Batch Extraction Complete ---", "blue")
        self.btn_run.setEnabled(True)

class TrackExtractorPlugin(FeaturePlugin):
    @property
    def name(self):
        return "Smart Batch Extractor"

    @property
    def description(self):
        return "Automatically routes MKVs to MKVToolNix and MP4/AVIs to FFmpeg for perfect track extraction."

    def get_ui(self, parent=None):
        return TrackExtractorUI(parent)