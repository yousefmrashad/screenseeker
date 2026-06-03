# Vision-Based Desktop Automation with Dynamic Icon Grounding

A robust Python automation script that leverages computer vision to dynamically ground, launch, interact with, and close the Windows Notepad application. 

This project was built to automate fetching blog posts from a REST API and writing them to individual text files in a target directory via Notepad GUI automation, handling various hardware constraints, window state checks, and display scales.

---

## 🚀 Key Features

* **Dynamic Visual Grounding**: Captured via `pyautogui` and grounded dynamically on *every loop iteration* to adapt to layouts where the desktop Notepad icon is moved, dragged, or rearranged during execution.
* **CLI Testing Flag (`--cache-icon`)**: Supports running in cached-coordinate mode, locating the Notepad icon once at the start of execution to accelerate debugging of the keyboard and file-saving loops.
* **High-DPI Display Scaling Match**: Automatically resolves physical pixel bounds returned by visual search models to logical OS screen coordinate clicks by comparing screenshot dimensions with PyAutoGUI display metrics.
* **Resilient Window Closing Sequence**: Bypasses common laptop hardware conflicts (such as Fn-Lock blocking `Alt+F4` from registering) by executing a primary `Alt + Space` -> `c` (system menu Close command) sequence, with a secondary fallback to `Alt + F4` if the window is still detected.
* **Multi-Layer API Graceful Degradation**: Fetches posts from JSONPlaceholder, automatically switches to a Beeceptor mirror if blocked, and falls back to a clean mock post dataset if all network attempts fail.
* **Pre-run Cleanup**: Sweeps the target directory on start to avoid write prompts or replacement dialog blockers.

---

## 🛠️ Requirements & Setup

### Prerequisites
* **Target OS**: Windows 10 or 11
* **Screen Resolution**: 1920x1080 (standard layout settings)
* **Desktop Setup**: Create or place a Notepad shortcut icon visible on the Desktop before running.

### Installation
Ensure you have the required dependencies installed using `uv`:

```bash
uv pip install pyautogui pyperclip requests pillow
```

Ensure the grounding package `screenseeker` is correctly configured in your Python path.

---

## 💻 Usage

### 1. Run in Dynamic Grounding Mode (Default)
Captures a fresh screenshot and runs visual search to find the Notepad icon on every iteration. This is the main mode for robust automation:

```bash
uv run automate.py
```

### 2. Run in Cached Testing Mode
Locates the Notepad icon once before entering the loop. Useful for fast debugging of keyboard emulation, clipboard syncing, and directory write validations:

```bash
uv run automate.py --cache-icon
```

### 3. Run Grounding-Only Script
Performs *only* the visual search to locate the Notepad icon on the desktop, calculates display-scaled click coordinates, and saves an annotated screenshot—without invoking the Notepad automation loop. This is useful for capturing the required 3 position screenshots (top-left, bottom-right, center):

```bash
uv run ground_only.py
```

---

## 📂 Project Outputs

* **Target Directory**: Written files are saved to `~/Desktop/tjm-project/` formatted as `post_{post_id}.txt`.
* **Annotated Detections**: Detection bounding boxes are drawn and saved in the `annotated_screenshots/` folder (formatted as `grounding_detection_{timestamp}_{click_x}_{click_y}.png` to prevent overwriting past runs).
