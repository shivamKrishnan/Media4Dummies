# plugins/raw_subtitle_syncer.py
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QTextEdit, 
    QApplication, QGroupBox, QDoubleSpinBox, QComboBox, QMessageBox, QListWidget
)
from plugin_base import FeaturePlugin

class RawSubtitleSyncerUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 1. File Selection
        file_layout = QVBoxLayout()
        file_layout.addWidget(QLabel("Selected Subtitle Files (.srt, .ass, .vtt):"))
        
        self.file_list = QListWidget()
        file_layout.addWidget(self.file_list)
        
        btn_browse = QPushButton("Browse Subtitle Files")
        btn_browse.clicked.connect(self.select_files)
        file_layout.addWidget(btn_browse)
        
        # 2. Sync Settings
        settings_group = QGroupBox("Subtitle Timing Settings")
        settings_layout = QVBoxLayout()
        
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Time Adjustment:"))
        
        self.spin_delay = QDoubleSpinBox()
        # The default is set to Seconds initially
        self.spin_delay.setRange(-600.0, 600.0) 
        self.spin_delay.setDecimals(3)
        self.spin_delay.setSingleStep(0.5)
        delay_layout.addWidget(self.spin_delay)
        
        # Unit Dropdown
        self.combo_unit = QComboBox()
        self.combo_unit.addItems(["Seconds", "Milliseconds"])
        self.combo_unit.currentTextChanged.connect(self.update_spinbox_behavior)
        delay_layout.addWidget(self.combo_unit)
        
        help_lbl = QLabel("<i>(Positive = subs show later | Negative = subs show earlier)</i>")
        help_lbl.setStyleSheet("color: #757575;")
        
        settings_layout.addLayout(delay_layout)
        settings_layout.addWidget(help_lbl)
        settings_group.setLayout(settings_layout)

        # 3. Action Button
        self.btn_run = QPushButton("Sync and Save Copies")
        self.btn_run.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 10px;")
        self.btn_run.clicked.connect(self.process_sync)
        
        # 4. Logs
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # Assembly
        layout.addLayout(file_layout)
        layout.addWidget(settings_group)
        layout.addWidget(self.btn_run)
        layout.addWidget(self.log_output)
        
        self.selected_files = []

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Subtitle Files", "", "Subtitle Files (*.srt *.ass *.vtt)")
        if files:
            self.selected_files = files
            self.file_list.clear()
            for f in files:
                self.file_list.addItem(Path(f).name)
            self.log(f"Loaded {len(files)} file(s) for syncing.", "blue")

    def update_spinbox_behavior(self, unit):
        """Dynamically change the spinbox ranges and decimals based on the unit selected."""
        if unit == "Seconds":
            self.spin_delay.setRange(-600.0, 600.0) # 10 mins
            self.spin_delay.setDecimals(3)
            self.spin_delay.setSingleStep(0.5)
        else:
            self.spin_delay.setRange(-600000.0, 600000.0) # 10 mins in ms
            self.spin_delay.setDecimals(0) # MS should be whole numbers
            self.spin_delay.setSingleStep(100.0)

    def log(self, message, color="black"):
        self.log_output.append(f'<span style="color:{color};">{message}</span>')
        QApplication.processEvents()

    # --- Time Shifting Logic ---

    def shift_srt_vtt(self, match, delay_ms, is_vtt=False):
        sep = "." if is_vtt else ","
        def shift(time_str):
            h, m, s_ms = time_str.split(':')
            s, ms = s_ms.split(sep)
            total_ms = int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(ms)
            total_ms += delay_ms
            if total_ms < 0: total_ms = 0
            
            h2 = total_ms // 3600000
            m2 = (total_ms % 3600000) // 60000
            s2 = (total_ms % 60000) // 1000
            ms2 = total_ms % 1000
            return f"{h2:02d}:{m2:02d}:{s2:02d}{sep}{ms2:03d}"
            
        return f"{shift(match.group(1))} --> {shift(match.group(2))}"

    def shift_ass(self, match, delay_ms):
        def shift(time_str):
            h, m, s_cs = time_str.split(':')
            s, cs = s_cs.split('.')
            total_ms = int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(cs)*10
            total_ms += delay_ms
            if total_ms < 0: total_ms = 0
            
            h2 = total_ms // 3600000
            m2 = (total_ms % 3600000) // 60000
            s2 = (total_ms % 60000) // 1000
            cs2 = (total_ms % 1000) // 10
            return f"{h2}:{m2:02d}:{s2:02d}.{cs2:02d}"
        
        return f"{match.group(1)}{shift(match.group(2))},{shift(match.group(3))}{match.group(4)}"

    # --- Processing Loop ---

    def process_sync(self):
        if not self.selected_files:
            QMessageBox.warning(self, "Error", "No files selected.")
            return

        # Calculate final milliseconds based on user's unit choice
        raw_val = self.spin_delay.value()
        unit = self.combo_unit.currentText()
        
        delay_ms = int(raw_val * 1000) if unit == "Seconds" else int(raw_val)

        if delay_ms == 0:
            self.log("Delay is set to 0. Nothing to do.", "orange")
            return

        self.btn_run.setEnabled(False)
        self.log(f"--- Starting Subtitle Shift ({raw_val} {unit} / {delay_ms} ms) ---", "blue")

        srt_pattern = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")
        vtt_pattern = re.compile(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})")
        ass_pattern = re.compile(r"^(Dialogue:\s*[^,]*,)(\d:\d{2}:\d{2}\.\d{2}),(\d:\d{2}:\d{2}\.\d{2})(,.*)$", re.IGNORECASE)

        success_count = 0

        for file_path in self.selected_files:
            try:
                p = Path(file_path)
                content = p.read_text(encoding="utf-8", errors="replace")
                
                if p.suffix.lower() == '.srt':
                    new_content = srt_pattern.sub(lambda m: self.shift_srt_vtt(m, delay_ms, is_vtt=False), content)
                elif p.suffix.lower() == '.vtt':
                    new_content = vtt_pattern.sub(lambda m: self.shift_srt_vtt(m, delay_ms, is_vtt=True), content)
                elif p.suffix.lower() == '.ass':
                    lines = content.splitlines()
                    new_lines = []
                    for line in lines:
                        if line.startswith("Dialogue:"):
                            line = ass_pattern.sub(lambda m: self.shift_ass(m, delay_ms), line)
                        new_lines.append(line)
                    new_content = "\n".join(new_lines)
                else:
                    self.log(f"Skipped {p.name}: Unsupported format.", "orange")
                    continue

                out_path = p.with_name(f"{p.stem}_Synced{p.suffix}")
                out_path.write_text(new_content, encoding="utf-8")
                self.log(f"Synced: {out_path.name}", "green")
                success_count += 1
                
            except Exception as e:
                self.log(f"Failed to process {Path(file_path).name}: {str(e)}", "red")

        self.log(f"--- Complete: Synced {success_count} files ---", "blue")
        self.btn_run.setEnabled(True)

class RawSubtitleSyncPlugin(FeaturePlugin):
    @property
    def name(self):
        return "Raw Subtitle Syncer"

    @property
    def description(self):
        return "Batch shift timestamps for raw SRT, ASS, and VTT files."

    def get_ui(self, parent=None):
        return RawSubtitleSyncerUI(parent)