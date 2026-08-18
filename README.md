<div align="center">

# 🎬 Media4Dummies

**A modular, plugin-driven toolkit for simplifying repetitive media-file operations.**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black.svg)](https://github.com/shivamKrishnan/Media4Dummies)

<p>
  <em>
    Because media processing shouldn't require remembering a dozen terminal commands.
  </em>
</p>

</div>

---

## 📖 About

**Media4Dummies** is a modular media-processing toolkit designed to simplify repetitive tasks involved in managing a personal media library.

Instead of manually remembering and executing long, complicated CLI commands for every operation, Media4Dummies provides a unified interface for common media-processing workflows.

The project follows a **plugin-based architecture**, where each operation is implemented independently as a plugin. This makes the application easy to extend, maintain, and customize without modifying the core system.

### 🎯 What it is built for

* Batch-processing large numbers of media files
* Automating repetitive media-library tasks
* Manipulating tracks, subtitles, and container metadata
* Renaming and organizing files
* Creating repeatable media-processing workflows

---

## ✨ Features

| Plugin                    | Description                                                                         |
| :------------------------ | :---------------------------------------------------------------------------------- |
| 🎬 **Batch Muxer**        | Combine video, audio, and subtitle tracks into a single media container.            |
| 🎵 **Track Extractor**    | Extract selected audio, video, or subtitle tracks from media containers.            |
| 🏳️ **Batch Flagger**     | Modify track flags such as `Default`, `Forced`, and other track properties in bulk. |
| 📝 **Title Changer**      | Clean up and standardize internal container and track titles.                       |
| ✏️ **Custom Title**       | Apply custom naming conventions to media container titles.                          |
| 📁 **Local Renamer**      | Batch-rename physical files using customizable patterns and regular expressions.    |
| 💬 **Subtitle Converter** | Convert subtitles between common formats such as SRT, ASS, and VTT.                 |
| 🔄 **Raw Subtitle Sync**  | Retime and synchronize external subtitle files with their corresponding media.      |

---

## 🧩 Architecture

Media4Dummies separates the **application logic** from individual media-processing operations.

The core application is responsible for discovering and running plugins, while each plugin handles a specific task.

```text
                           Media4Dummies
                                │
                                ▼
                         ┌─────────────┐
                         │   main.py   │
                         │ Entry Point │
                         └──────┬──────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Plugin System  │
                       │ plugin_base.py  │
                       └────────┬────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
       ┌─────────────┐   ┌─────────────┐   ┌───────────────┐
       │ Batch Muxer │   │   Track     │   │   Subtitle    │
       │             │   │  Extractor  │   │    Tools      │
       └─────────────┘   └─────────────┘   └───────────────┘
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                       Media Processing Tools
                     (FFmpeg / MKVToolNix / etc.)
```

### 📂 Project Structure

```text
Media4Dummies/
│
├── Plugins/
│   ├── batch_flagger.py
│   ├── batch_muxer.py
│   ├── custom_title.py
│   ├── local_renamer.py
│   ├── raw_subtitle_sync.py
│   ├── subtitle_converter.py
│   ├── title_changer.py
│   └── track_extractor.py
│
├── main.py                 # Application entry point
├── plugin_base.py          # Base plugin class and interface
├── requirements.txt        # Python dependencies
├── LICENSE
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites

Make sure the following are available on your system:

* **Python 3.8 or newer**
* Required media-processing tools depending on the plugins you use
* The corresponding executables should be available in your system `PATH`

Depending on the operation, Media4Dummies may use tools such as:

* **FFmpeg**
* **MKVToolNix**

> **Note:** The exact external dependencies may vary depending on the plugin being used.

---

### 2. Installation

Clone the repository:

```bash
git clone https://github.com/shivamKrishnan/Media4Dummies.git
cd Media4Dummies
```

Create a virtual environment:

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

---

### 3. Usage

Start the application:

```bash
python main.py
```

The application will provide an interface for selecting the desired plugin and supplying the required input.

Each plugin is designed to handle a specific media-processing task, allowing workflows to be performed without manually constructing complex command-line arguments.

---

## 🛠️ Design Philosophy

> **"Media processing shouldn't require a cheat sheet of terminal commands."**

Media4Dummies is built around four principles:

### 🧩 Modular

Each feature is isolated into its own plugin.

A problem in one plugin should not require changes to unrelated functionality.

### 🔌 Extensible

New functionality can be added by creating a new plugin rather than rewriting the core application.

### ⚡ Practical

The project focuses on repetitive operations that commonly occur when maintaining a personal media library.

### 🤖 Automation-First

Operations are designed with **batch processing** in mind, reducing repetitive manual work and making large-scale media organization easier.

---

## 🔌 Creating a Plugin

Adding a new feature is designed to be straightforward.

Create a new Python file inside the `Plugins/` directory and inherit from the base `Plugin` class.

For example:

```python
from plugin_base import Plugin


class MyNewPlugin(Plugin):
    # Plugin implementation
    pass
```

The plugin can then be integrated into the existing plugin system without modifying unrelated features.

> The exact methods required by a plugin depend on the interface defined in `plugin_base.py`.

---

## 🗺️ Roadmap

Media4Dummies is an ongoing project. Potential future improvements include:

* [ ] 🖥️ Improved graphical interface
* [ ] 🔌 More media-processing plugins
* [ ] ⚡ Improved batch-processing workflows
* [ ] 🏷️ Advanced metadata editing
* [ ] ⚙️ Plugin configuration system
* [ ] 🔎 Plugin discovery and management
* [ ] 📊 Better processing status and progress reporting
* [ ] 🧾 Improved logging and error reporting
* [ ] 📦 Preset-based processing workflows

---


## 📜 License

This project is licensed under the **MIT License**.

See the [`LICENSE`](LICENSE) file for the complete license text.

---

<div align="center">

**🎬 Media4Dummies — Making media management a little less painful.**

</div>
