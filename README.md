# ScreenSeekeR: General-Purpose VLM-Based Visual Grounding Engine

<p align="center">
  <a href="https://www.codefactor.io/repository/github/yousefmrashad/screenseeker"><img src="https://www.codefactor.io/repository/github/yousefmrashad/screenseeker/badge" alt="CodeFactor" /></a>
  <a href="https://deepwiki.com/yousefmrashad/screenseeker"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki" /></a>
  <a href="https://www.gnu.org/licenses/gpl-3.0"><img src="https://img.shields.io/badge/License-GPLv3-orange.svg" alt="License: GPL v3" /></a>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue.svg" alt="Python: 3.13+" />
</p>

A general-purpose visual grounding utility adapted from the recursive visual search concepts in the ScreenSeekeR paper ([arXiv:2504.07981](https://arxiv.org/pdf/2504.07981)). It leverages Vision-Language Models (VLMs) like Gemini 3.5 Flash to dynamically locate any arbitrary GUI element, icon, text field, or button on a desktop screen without requiring pre-trained templates or exact match images.

This repository provides a primary command-line grounding tool (`ground.py`) and a specific end-to-end demonstration (`automate.py`) showing how the visual grounding engine is integrated into a desktop automation loop (automating Windows Notepad tasks).

---

## 🚀 Key Features

* **Zero-Shot Visual Grounding**: Locate any arbitrary interface element using plain-text instructions (e.g. "Find the recycle bin", "Locate the save button").
* **Recursive Search & Focus**: Adapts the paper's multi-step visual search concept: Position Inference (Planner) $\rightarrow$ Context Dilation ($S_{min}$ / $R_{max}$ padding) $\rightarrow$ Direct Grounding $\rightarrow$ Attention-based Red-box Verification.
* **Adapted & Streamlined Flow**: Streamlines the academic paper by removing complex Non-Maximum Suppression (NMS) in favor of direct LLM confidence ranking, creating a lightweight, highly responsive Python codebase.
* **Scale & DPI Invariance**: Automatically resolves physical pixel bounds returned by the VLM to logical OS screen coordinate clicks by comparing screenshot aspect ratios with PyAutoGUI display metrics.
* **Transient API Resilience**: Wraps VLM API requests with a 3-attempt linear/exponential backoff retry block to safely absorb temporary network timeouts or rate limits.
* **Hallucination Protection**: Features a 2-pass check where direct grounding verifies target presence (`found: bool`) before running verification, preventing erroneous mouse events.

---

## 🛠️ Requirements & Setup

### Prerequisites
* **Target OS**: Windows 10 or 11
* **Desktop Setup**: Ensure the target icon or button you want to search for is visible on your screen.

### Installation
1. **Sync dependencies** using `uv` (this automatically creates a virtual environment and installs all packages in `pyproject.toml`, including `typer` and the `google-genai` SDK):
   ```bash
   uv sync
   ```

2. **Configure environment variables**: Copy the example configuration and add your Gemini API key:
   ```bash
   # On Windows (Command Prompt)
   copy .env.example .env

   # On Windows (PowerShell) or Linux/macOS
   cp .env.example .env
   ```
   Open the `.env` file and set your `GEMINI_API_KEY`.

---

## 💻 Primary Tool: Generalized Grounding CLI (`ground.py`)

The primary entry point of the project is `ground.py`, a general-purpose command-line utility that takes a desktop screenshot, locates your requested target, translates the coordinate space, and saves a visual detection debug image.

### Usage Examples

1. **Locate the default Notepad shortcut icon:**
   ```bash
   uv run ground.py
   ```

2. **Locate any custom target on your screen:**
   ```bash
   uv run ground.py "Chrome icon" "Find the Google Chrome shortcut icon on the desktop"
   ```

3. **Modify search configurations (such as custom scaling ratios or max search depth):**
   ```bash
   uv run ground.py "Save Button" --min-size-ratio 0.2 --max-depth 4
   ```

4. **View all CLI arguments and options:**
   ```bash
   uv run ground.py --help
   ```

---

## 📝 Demo Application: Notepad Task Automation (`automate.py`)

To demonstrate how `ScreenSeekeR` is used inside a live script, `automate.py` integrates the grounding coordinates inside a loop to perform a complete data-writing task:
1. Minimizes all windows (`Win+D`) to expose the desktop.
2. Dynamically locates the Notepad shortcut icon and double-clicks it to launch the app.
3. Fetches 10 blog posts from a REST API (with Beeceptor mirror and local offline dataset fallbacks).
4. Types the post content, copy-verifies clipboard syncing to bypass system delays, saves the text file to `~/Desktop/screenseeker-demo/`, closes Notepad via system menu commands, and repeats.

### Running the Demo

* **Standard Dynamic Loop (Grounds the Notepad icon on every iteration):**
  ```bash
  uv run automate.py
  ```

* **Cached Coordinator Mode (Locates the icon once at startup for testing keyboard loops):**
  ```bash
  uv run automate.py --cache-icon
  ```

---

## 📂 Project Outputs

* **Annotated Groundings**: Grounding results are annotated with a red boundary box and saved under `annotated_screenshots/` with target-specific names (e.g. `grounding_Chrome_icon_{timestamp}_{click_x}_{click_y}.png`).
* **Demo Target Directory**: Files generated by the Notepad demonstration are saved under `~/Desktop/screenseeker-demo/` formatted as `post_{post_id}.txt`.

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. See the [LICENSE](LICENSE) file for the full text.
