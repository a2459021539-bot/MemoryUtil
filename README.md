# MemorySpaceExplorer 🚀

**MemorySpaceExplorer** is a high-performance visualizer and optimizer for RAM and NVIDIA GPU VRAM on Windows. It uses a **TreeMap** layout to provide a clear, intuitive view of how your system resources are allocated.

## 🖼 Screenshots

| Main Interface (English) | Main Interface (Chinese) |
| :---: | :---: |
| ![English Interface](./pics/image%20en.png) | ![Chinese Interface](./pics/image%20zh.png) |

| Collapsible Settings |
| :---: |
| ![Settings Page](./pics/image%20setting.png) |

## 📥 Download

You can directly download the pre-built executable from the [dist/MemoryUitl.exe](./dist/MemoryUitl.exe) directory for immediate use without installing Python.

[简体中文](./README_zh.md) | **English**

---

## ✨ Key Features

### 📊 Visual Resource Analysis
- **TreeMap Visualization**: Uses a high-performance squarified treemap algorithm to dynamically display RAM, Swap, and VRAM usage.
- **Process Inner-View**: Each process block is internally split into **[Physical Memory | Virtual Memory]** sub-regions, identified by different colors (Blue/Orange) for a clear memory composition view.
- **Dual View Modes**:
  - **Program Mode**: Automatically aggregates all child processes of the same application (e.g., Chrome tabs, VS Code extensions) to quickly spot memory hogs.
  - **Process Mode**: Shows individual PIDs for granular control.

### 🎮 Gaming & Performance
- **Game Mode (Auto-Pause)**: Smart detection of full-screen or borderless games. When a game is detected, the app enters a "Sleep" state (refresh rate drops to 30s) and pauses heavy monitoring logic to ensure zero impact on game FPS. A 🎮 icon appears on the map when active.
- **Single Instance Protection**: Uses a Local Server mechanism to ensure only one instance of the program runs globally, preventing resource conflicts.
- **Dynamic Tray Icon**: The system tray icon features a 4-bar real-time dynamic chart:
  - **Left 2 bars**: Physical RAM usage percentage.
  - **Right 2 bars**: GPU VRAM usage percentage.
- **Smart Memory Optimization**: Periodically releases the physical memory occupied by idle processes using the Windows Working Set API.

### 🛠 Advanced Management
- **Precision GPU Tracking**: Combines `pynvml`, `nvidia-smi`, and Windows performance counters with **LUID Hardware ID matching** to accurately identify process-level VRAM usage (fully supports multi-GPU setups).
- **CPU Affinity Management**: Records and automatically applies CPU core binding settings for processes, ideal for limiting or optimizing performance for specific apps.
- **Process Chain Analysis**: Right-click to view the "Ancestor" and "Descendant" relationship chain of a process to understand complex process trees.

### 🎨 Modern UI & Experience
- **Collapsible Settings**: Manage a vast array of configuration options with a modern, collapsible UI to keep the interface clean.
- **Real-time Search & Filtering**: Quickly find specific processes in the detailed list view.
- **Customizable Themes**: Freely adjust display colors for system memory, GPU memory, virtual memory, and free space.
- **I18N Support**: Full support for instant switching between English and Simplified Chinese, with all UI text centrally managed.
- **Safe Configuration Storage**: Config files are stored in the user's `Documents\MemorySpaceExplorer` folder, following Windows standards and avoiding permission issues.

---

## 🖥 System Requirements
- **OS**: Windows 10/11
- **Python**: 3.8+
- **Hardware**: NVIDIA GPU (for VRAM monitoring features).

---

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/memory_anaylize_tool.git
   cd memory_anaylize_tool
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   *(Required: `PyQt6`, `psutil`, `pynvml`)*

---

## ❓ Troubleshooting

### 1. Error: `TypeError: argument 1 has unexpected type 'QPoint'`
This is due to strict type checking for the `contains()` method in PyQt6.
- **Solution**: 
  - If you are a **Developer**: Ensure you have pulled the latest code. I have explicitly converted all `QPoint` instances to `QPointF`.
  - **Clear Cache**: Delete the `__pycache__` folder in the project.
  - **Rebuild**: If you are running the EXE, make sure to execute `pyinstaller --clean MemoryUitl.spec` to regenerate it.

### 2. GPU VRAM shows as 0 or processes are not recognized
- **Solution**: 
  - Ensure NVIDIA drivers are installed.
  - Try running the program as **Administrator**.
  - Check if the `nvidia-smi` command is available in your system.

---

## 🛠 Build from Source

If you want to build the executable yourself:

1. **Install PyInstaller**
   ```bash
   pip install pyinstaller
   ```

2. **Run Build Command (Using Spec File)**
   ```bash
   pyinstaller --clean MemoryUitl.spec
   ```
   *(Note: The project structure is now modular. Using the `.spec` file ensures all sub-modules are correctly included.)*

The built EXE will be generated in the `dist/` folder.

---

## 📂 Project Structure

The project has been refactored for better maintainability:
- `main.py`: Application entry point.
- `config.py`: Internationalization (I18N) and global configuration.
- `ui/`: UI components and dialogs.
- `utils/`: Core algorithms, data providers, and system utilities.

---

## 🛠 Usage

1. **Run the application**
   ```bash
   python main.py
   ```
2. **Interactions**:
   - **Double-Click**: View detailed process list for an aggregate group.
   - **Right-Click**: Access management menu (Open file location, Kill process, CPU Affinity).
   - **Tray Icon**: Hover for quick stats; right-click for quick actions.

---

## 💡 Pro Tips
- **Run as Admin**: Recommended to get full process path information and enable deeper memory optimization.
- **GPU Fallback**: The app automatically chooses the best method (NVML > XML > CSV > PowerShell) for GPU monitoring based on your system environment.

---

## ⚖ License
MIT License
