# MemorySpaceExplorer 🚀

**MemorySpaceExplorer** is a high-performance visualizer and optimizer for RAM and NVIDIA GPU VRAM on Windows. It uses a **TreeMap** layout to provide a clear, intuitive view of how your system resources are allocated.

## 📥 Download

You can directly download the pre-built executable from the [dist/MemoryUitl.exe](./dist/MemoryUitl.exe) directory for immediate use without installing Python.

[简体中文](./README_zh.md) | **English**

---

## ✨ Key Features

### 📊 Visual Resource Analysis
- **TreeMap Visualization**: Uses a high-performance squarified treemap algorithm to display RAM, Swap, and VRAM usage.
- **Dual View Modes**:
  - **Program Mode**: Aggregates processes from the same application (e.g., Chrome tabs) to identify the biggest resource consumers.
  - **Process Mode**: Shows individual PIDs for granular control.

### 🎮 Gaming & Performance
- **Game Mode (Auto-Pause)**: Automatically detects full-screen/borderless games and pauses monitoring/optimization to ensure zero performance impact. A 🎮 icon appears on the map when active.
- **Dynamic Tray Icon**: The system tray icon features a 4-bar real-time chart:
  - **Left 2 bars**: RAM usage.
  - **Right 2 bars**: GPU VRAM usage.
- **Smart Optimization**: Periodically releases idle process working sets using Windows APIs to keep your system snappy.

### 🛠 Advanced GPU & CPU Management
- **Precision GPU Tracking**: Combines `pynvml`, `nvidia-smi`, and PowerShell performance counters with **LUID matching** to accurately identify process-level VRAM usage, even in multi-GPU setups.
- **CPU Affinity**: View process chains and set CPU core affinity directly from the right-click menu.
- **Permission Handling**: Automatically attempts to fetch process names using Windows API if standard methods fail due to permissions.

### 🎨 Modern UI & Experience
- **Collapsible Settings**: Manage complex configurations with an organized, collapsible interface.
- **Customizable Themes**: Adjust colors for system components, GPU, and free memory.
- **I18N Support**: Fully supports English and Simplified Chinese, managed through a centralized configuration.
- **User-Centric Storage**: Configuration is stored in the user's `Documents` folder for easy access and permission safety.

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
