import sys
import os
import shutil
import importlib
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QStackedWidget, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QGroupBox, QMessageBox
)

from plugin_base import FeaturePlugin


class GlobalSettingsUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Initialize QSettings (Saves to OS Registry/Config)
        self.settings = QSettings("ModularMedia", "ToolboxSettings")
        
        # --- MKVToolNix Settings ---
        mkv_group = QGroupBox("MKVToolNix Path")
        mkv_layout = QHBoxLayout()
        self.input_mkv = QLineEdit(self.settings.value("mkvtoolnix_path", ""))
        self.input_mkv.setPlaceholderText("Select folder containing mkvmerge / mkvpropedit...")
        
        btn_mkv_browse = QPushButton("Browse")
        btn_mkv_browse.clicked.connect(lambda: self.browse_path(self.input_mkv))
        
        btn_mkv_auto = QPushButton("Auto-Detect")
        btn_mkv_auto.clicked.connect(lambda: self.detect_and_set("mkvtoolnix"))
        
        mkv_layout.addWidget(self.input_mkv)
        mkv_layout.addWidget(btn_mkv_browse)
        mkv_layout.addWidget(btn_mkv_auto)
        mkv_group.setLayout(mkv_layout)
        
        # --- FFmpeg Settings ---
        ff_group = QGroupBox("FFmpeg Path")
        ff_layout = QHBoxLayout()
        self.input_ff = QLineEdit(self.settings.value("ffmpeg_path", ""))
        self.input_ff.setPlaceholderText("Select folder containing ffmpeg / ffprobe...")
        
        btn_ff_browse = QPushButton("Browse")
        btn_ff_browse.clicked.connect(lambda: self.browse_path(self.input_ff))
        
        btn_ff_auto = QPushButton("Auto-Detect")
        btn_ff_auto.clicked.connect(lambda: self.detect_and_set("ffmpeg"))
        
        ff_layout.addWidget(self.input_ff)
        ff_layout.addWidget(btn_ff_browse)
        ff_layout.addWidget(btn_ff_auto)
        ff_group.setLayout(ff_layout)
        
        # --- TMDB API Settings ---
        tmdb_group = QGroupBox("TMDB API Key (Optional)")
        tmdb_layout = QHBoxLayout()
        self.input_tmdb = QLineEdit(self.settings.value("tmdb_api_key", ""))
        self.input_tmdb.setEchoMode(QLineEdit.Password)
        self.input_tmdb.setPlaceholderText("Enter your TMDB API v3 Key...")
        
        tmdb_layout.addWidget(self.input_tmdb)
        tmdb_group.setLayout(tmdb_layout)
        
        # --- Save Button ---
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 8px;")
        self.btn_save.clicked.connect(self.save_settings)
        
        # Layout Assembly
        self.layout.addWidget(mkv_group)
        self.layout.addWidget(ff_group)
        self.layout.addWidget(tmdb_group)
        self.layout.addWidget(self.btn_save)
        self.layout.addStretch()

        # Run initial auto-detection for empty paths
        self.initial_auto_detect()

    @staticmethod
    def find_tool_folder(tool_name: str) -> str:
        """
        Searches for a binary tool folder by checking:
        1. System PATH
        2. Local application subdirectories ('bin', 'tools', root)
        3. Standard operating system installation paths
        """
        exe_name = f"{tool_name}.exe" if os.name == "nt" else tool_name

        # 1. Check System PATH
        system_path = shutil.which(exe_name) or shutil.which(tool_name)
        if system_path:
            return str(Path(system_path).parent.resolve())

        # 2. Check App Local Directories (e.g. portable / bundled bin folder)
        base_dir = Path(__file__).parent.resolve()
        candidate_subdirs = ["", "bin", "tools", f"bin/{tool_name}", f"tools/{tool_name}"]
        for sub in candidate_subdirs:
            target_path = base_dir / sub / exe_name
            if target_path.exists():
                return str(target_path.parent.resolve())

        # 3. Check Standard Install Locations (Windows Specific)
        if os.name == "nt":
            program_files = [
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                os.environ.get("LOCALAPPDATA", "")
            ]

            known_paths = []
            if tool_name == "mkvmerge" or tool_name == "mkvtoolnix":
                for pf in program_files:
                    if pf:
                        known_paths.append(Path(pf) / "MKVToolNix")
            elif tool_name == "ffmpeg":
                for pf in program_files:
                    if pf:
                        known_paths.extend([
                            Path(pf) / "ffmpeg" / "bin",
                            Path(pf) / "FFmpeg" / "bin",
                        ])
                known_paths.extend([Path("C:/ffmpeg/bin"), Path("C:/FFmpeg/bin")])

            for path in known_paths:
                if (path / exe_name).exists():
                    return str(path.resolve())

        return ""

    def detect_and_set(self, tool_type: str):
        """Triggers manual detection and gives user feedback."""
        target_binary = "mkvmerge" if tool_type == "mkvtoolnix" else "ffmpeg"
        found_dir = self.find_tool_folder(target_binary)

        if tool_type == "mkvtoolnix":
            if found_dir:
                self.input_mkv.setText(found_dir)
                QMessageBox.information(self, "Found", f"MKVToolNix detected at:\n{found_dir}")
            else:
                QMessageBox.warning(self, "Not Found", "Could not automatically locate MKVToolNix on this system.")
        elif tool_type == "ffmpeg":
            if found_dir:
                self.input_ff.setText(found_dir)
                QMessageBox.information(self, "Found", f"FFmpeg detected at:\n{found_dir}")
            else:
                QMessageBox.warning(self, "Not Found", "Could not automatically locate FFmpeg on this system.")

    def initial_auto_detect(self):
        """Pre-populates empty fields on initial load without showing dialog popups."""
        if not self.input_mkv.text().strip():
            mkv_dir = self.find_tool_folder("mkvmerge")
            if mkv_dir:
                self.input_mkv.setText(mkv_dir)

        if not self.input_ff.text().strip():
            ff_dir = self.find_tool_folder("ffmpeg")
            if ff_dir:
                self.input_ff.setText(ff_dir)

    def browse_path(self, line_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            line_edit.setText(folder)

    def save_settings(self):
        # Save values to OS Registry / Config
        self.settings.setValue("mkvtoolnix_path", self.input_mkv.text().strip())
        self.settings.setValue("ffmpeg_path", self.input_ff.text().strip())
        self.settings.setValue("tmdb_api_key", self.input_tmdb.text().strip())

        # Force write buffer
        self.settings.sync()
        
        QMessageBox.information(self, "Saved", "Global settings have been saved successfully!")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modular Media Toolbox")
        self.resize(850, 550)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.plugin_stack = QStackedWidget()

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.plugin_stack)

        self.sidebar.currentRowChanged.connect(self.plugin_stack.setCurrentIndex)

        # --- 1. Load the Global Settings Tab First ---
        self.sidebar.addItem("⚙️ Global Settings")
        self.settings_ui = GlobalSettingsUI()
        self.plugin_stack.addWidget(self.settings_ui)

        # --- 2. Load the Plugins ---
        self.load_plugins()

    def load_plugins(self, plugin_folder="plugins"):
        """Dynamically loads plugin UIs into the application."""
        if not os.path.exists(plugin_folder):
            os.makedirs(plugin_folder)

        sys.path.insert(0, os.path.abspath(plugin_folder))
        
        plugins_found = False

        for filename in os.listdir(plugin_folder):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(module_name)
                except Exception as e:
                    print(f"Failed to load plugin {filename}: {e}")
                    continue
                
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if (
                        isinstance(attribute, type) and 
                        issubclass(attribute, FeaturePlugin) and 
                        attribute is not FeaturePlugin
                    ):
                        plugin_instance = attribute()
                        self.sidebar.addItem(plugin_instance.name)
                        plugin_ui = plugin_instance.get_ui(self)
                        self.plugin_stack.addWidget(plugin_ui)
                        plugins_found = True

        if not plugins_found:
            placeholder = QLabel("No plugins found in the 'plugins' folder.")
            placeholder.setAlignment(Qt.AlignCenter)
            self.plugin_stack.addWidget(placeholder)


if __name__ == "__main__":
    app = QApplication(sys.path)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())