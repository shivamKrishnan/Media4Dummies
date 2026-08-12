# main.py
import sys
import os
import importlib
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, 
    QListWidget, QStackedWidget, QLabel, QVBoxLayout
)
from plugin_base import FeaturePlugin

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QGroupBox, QMessageBox
)

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QGroupBox, QMessageBox
)

class GlobalSettingsUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Initialize QSettings (This saves to the OS automatically)
        self.settings = QSettings("ModularMedia", "ToolboxSettings")
        
        # --- MKVToolNix Settings ---
        mkv_group = QGroupBox("MKVToolNix Path")
        mkv_layout = QHBoxLayout()
        self.input_mkv = QLineEdit(self.settings.value("mkvtoolnix_path", ""))
        self.input_mkv.setPlaceholderText("Select the folder containing mkvpropedit and mkvmerge...")
        btn_mkv = QPushButton("Browse")
        btn_mkv.clicked.connect(lambda: self.browse_path(self.input_mkv, "mkvtoolnix_path"))
        
        mkv_layout.addWidget(self.input_mkv)
        mkv_layout.addWidget(btn_mkv)
        mkv_group.setLayout(mkv_layout)
        
        # --- FFmpeg Settings ---
        ff_group = QGroupBox("FFmpeg Path")
        ff_layout = QHBoxLayout()
        self.input_ff = QLineEdit(self.settings.value("ffmpeg_path", ""))
        self.input_ff.setPlaceholderText("Select the folder containing ffmpeg and ffprobe...")
        btn_ff = QPushButton("Browse")
        btn_ff.clicked.connect(lambda: self.browse_path(self.input_ff, "ffmpeg_path"))
        
        ff_layout.addWidget(self.input_ff)
        ff_layout.addWidget(btn_ff)
        ff_group.setLayout(ff_layout)
        
        # --- TMDB API Settings (NEW) ---
        tmdb_group = QGroupBox("TMDB API Key (Optional)")
        tmdb_layout = QHBoxLayout()
        self.input_tmdb = QLineEdit(self.settings.value("tmdb_api_key", ""))
        self.input_tmdb.setEchoMode(QLineEdit.Password)  # Hides the key with dots
        self.input_tmdb.setPlaceholderText("Enter your TMDB API v3 Key...")
        
        tmdb_layout.addWidget(self.input_tmdb)
        tmdb_group.setLayout(tmdb_layout)
        
        # --- Save Button ---
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 8px;")
        self.btn_save.clicked.connect(self.save_settings)
        
        # Add everything to main layout in order
        self.layout.addWidget(mkv_group)
        self.layout.addWidget(ff_group)
        self.layout.addWidget(tmdb_group)  # Inserted right above the save button
        self.layout.addWidget(self.btn_save)
        self.layout.addStretch()

    def browse_path(self, line_edit, setting_key):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            line_edit.setText(folder)

    def save_settings(self):
        # Save values to the OS (Added TMDB here!)
        self.settings.setValue("mkvtoolnix_path", self.input_mkv.text())
        self.settings.setValue("ffmpeg_path", self.input_ff.text())
        self.settings.setValue("tmdb_api_key", self.input_tmdb.text().strip())

        # Force the app to immediately write the buffer to the Windows Registry
        self.settings.sync()
        
        QMessageBox.information(self, "Saved", "Global settings have been saved successfully!")

    def browse_path(self, line_edit, setting_key):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            line_edit.setText(folder)

    def save_settings(self):
        # Save values to the OS
        self.settings.setValue("mkvtoolnix_path", self.input_mkv.text())
        self.settings.setValue("ffmpeg_path", self.input_ff.text())
        QMessageBox.information(self, "Saved", "Global paths have been saved successfully!")

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
        # Ensure the plugin directory exists
        if not os.path.exists(plugin_folder):
            os.makedirs(plugin_folder)

        sys.path.insert(0, os.path.abspath(plugin_folder))
        
        plugins_found = False

        for filename in os.listdir(plugin_folder):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                module = importlib.import_module(module_name)
                
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if isinstance(attribute, type) and issubclass(attribute, FeaturePlugin) and attribute is not FeaturePlugin:
                        # Instantiate the plugin
                        plugin_instance = attribute()
                        
                        # 1. Add name to sidebar
                        self.sidebar.addItem(plugin_instance.name)
                        
                        # 2. Get the plugin's UI and add it to the stack
                        plugin_ui = plugin_instance.get_ui(self)
                        self.plugin_stack.addWidget(plugin_ui)
                        
                        plugins_found = True

        # If no plugins exist, show a placeholder
        if not plugins_found:
            placeholder = QLabel("No plugins found in the 'plugins' folder.")
            self.plugin_stack.addWidget(placeholder)
            self.sidebar.addItem("Empty")

if __name__ == "__main__":
    app = QApplication(sys.path)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())