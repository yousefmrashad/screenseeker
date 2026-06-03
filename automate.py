import ctypes
import logging
import os
import sys
import time
from typing import Tuple

import pyautogui
import pyperclip
import requests
from PIL import Image, ImageDraw

from screenseeker import ElementConfig, ScreenSeekeR
import config as app_config

# Configuration Flags
CACHE_ICON = "--cache-icon" in sys.argv

# Configure logging: Root logger to WARNING to suppress third-party loggers
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Orchestrator")
logger.setLevel(logging.INFO)


def get_desktop_path() -> str:
    """
    Get the standard Desktop folder path.
    """
    return os.path.join(os.path.expanduser("~"), "Desktop")


def fetch_posts() -> list:
    """
    Fetch the first 10 posts from JSONPlaceholder or its Beeceptor mirror.
    """
    urls = [
        "https://jsonplaceholder.typicode.com/posts",
        "https://json-placeholder.mock.beeceptor.com/posts",
    ]
    for url in urls:
        logger.info(f"Fetching posts from {url}...")
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            posts = response.json()
            logger.info(f"Successfully fetched posts from {url}.")
            return posts[:10]
        except Exception as e:
            logger.warning(f"Failed to fetch posts from {url}: {e}")

    logger.warning("All API endpoints failed. Falling back to local mock data.")
    return [
        {
            "id": i,
            "title": f"Mock Blog Post {i}",
            "body": f"This is the body content of mock blog post number {i}. It serves as a fallback content.",
        }
        for i in range(1, 11)
    ]


def is_notepad_open() -> bool:
    """
    Check if any open visible window is the Windows Notepad application.
    """
    notepad_found = []

    def win_enum_handler(hwnd, ctx):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            h_process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h_process:
                try:
                    buf = ctypes.create_unicode_buffer(1024)
                    size = ctypes.c_ulong(1024)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                        h_process, 0, buf, ctypes.byref(size)
                    ):
                        exe_name = os.path.basename(buf.value).lower()
                        if exe_name == "notepad.exe":
                            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                            buf_title = ctypes.create_unicode_buffer(length + 1)
                            ctypes.windll.user32.GetWindowTextW(
                                hwnd, buf_title, length + 1
                            )
                            if buf_title.value:
                                notepad_found.append(hwnd)
                finally:
                    ctypes.windll.kernel32.CloseHandle(h_process)
        return True

    try:
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(EnumWindowsProc(win_enum_handler), 0)
        return len(notepad_found) > 0
    except Exception as e:
        logger.error(f"Error checking if Notepad is open: {e}")
        return False


def locate_notepad_icon(
    seeker: ScreenSeekeR, config: ElementConfig
) -> Tuple[int, int, Image.Image, Tuple[int, int, int, int]]:
    """
    Locate the Notepad icon on the desktop and return resolved logical coordinates (click_x, click_y).
    """
    screenshot = pyautogui.screenshot()
    try:
        icon_box = seeker.visual_search(screenshot, config)
        if icon_box is not None:
            x1, y1, x2, y2 = icon_box
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            # Resolve scaling
            screen_w, screen_h = pyautogui.size()
            img_w, img_h = screenshot.size
            scale_x = screen_w / img_w
            scale_y = screen_h / img_h

            return int(cx * scale_x), int(cy * scale_y), screenshot, icon_box
    except Exception as e:
        logger.error(f"Error during visual search: {e}")
    return None, None, None, None


def main():
    desktop_path = get_desktop_path()
    tjm_project_dir = os.path.join(desktop_path, "tjm-project")
    logger.info(f"Target saving directory: {tjm_project_dir}")
    os.makedirs(tjm_project_dir, exist_ok=True)

    # Clean existing post files
    for f in os.listdir(tjm_project_dir):
        if f.startswith("post_") and f.endswith(".txt"):
            try:
                os.remove(os.path.join(tjm_project_dir, f))
            except Exception as e:
                logger.warning(f"Could not remove {f}: {e}")

    annotated_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "annotated_screenshots"
    )
    os.makedirs(annotated_dir, exist_ok=True)

    seeker = ScreenSeekeR()
    config = ElementConfig(
        target_name=app_config.TARGET_ELEMENT["target_name"],
        instruction=app_config.TARGET_ELEMENT["instruction"],
        min_size_ratio=app_config.TARGET_ELEMENT["min_size_ratio"],
        max_depth=app_config.TARGET_ELEMENT["max_depth"],
        model_name=app_config.MODEL_NAME,
    )
    posts = fetch_posts()

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5

    # Minimize all windows once at the start to reveal the desktop
    logger.info("Minimizing all windows to reveal desktop...")
    pyautogui.hotkey("win", "d")
    time.sleep(1.5)

    cached_x, cached_y = None, None
    if CACHE_ICON:
        logger.info("Locating Notepad icon once before the loop...")
        for attempt in range(3):
            click_x, click_y, screenshot, icon_box = locate_notepad_icon(seeker, config)
            if click_x is not None:
                cached_x, cached_y = click_x, click_y
                # Save annotated screenshot
                draw = ImageDraw.Draw(screenshot)
                draw.rectangle(icon_box, outline="red", width=3)
                screenshot.save(
                    os.path.join(
                        annotated_dir, "annotated_screenshot_detection_cached.png"
                    )
                )
                break
            time.sleep(1.0)

        if cached_x is None:
            logger.error("Failed to locate Notepad icon. Exiting.")
            return

    for idx, post in enumerate(posts):
        post_id = post["id"]
        title = post["title"]
        body = post["body"]

        logger.info(f"=== Processing Post {idx + 1}/10 (ID: {post_id}) ===")

        # Minimize windows to expose desktop on subsequent runs or when doing dynamic searches
        if idx > 0 or not CACHE_ICON:
            pyautogui.hotkey("win", "d")
            time.sleep(1.5)

        if CACHE_ICON:
            click_x, click_y = cached_x, cached_y
        else:
            # Dynamic search: locate icon on every iteration
            click_x, click_y = None, None
            for attempt in range(3):
                cx, cy, screenshot, icon_box = locate_notepad_icon(seeker, config)
                if cx is not None:
                    click_x, click_y = cx, cy
                    # Save annotated screenshot for each iteration
                    draw = ImageDraw.Draw(screenshot)
                    draw.rectangle(icon_box, outline="red", width=3)
                    screenshot.save(
                        os.path.join(
                            annotated_dir,
                            f"annotated_screenshot_detection_post_{post_id}.png",
                        )
                    )
                    break
                time.sleep(1.0)

            if click_x is None:
                logger.error(
                    f"Failed to locate Notepad icon dynamically. Skipping post {post_id}."
                )
                continue

        logger.info(f"Double-clicking Notepad icon at ({click_x}, {click_y})...")
        pyautogui.doubleClick(click_x, click_y)

        # Wait for Notepad window to appear
        notepad_launched = False
        for _ in range(10):
            time.sleep(0.5)
            if is_notepad_open():
                notepad_launched = True
                break

        if not notepad_launched:
            logger.error("Notepad failed to launch. Retrying double click...")
            pyautogui.doubleClick(click_x, click_y)
            time.sleep(2.0)
            if not is_notepad_open():
                logger.error("Notepad still closed. Skipping post.")
                continue

        time.sleep(1.5)  # Wait for focus to stabilize

        # Type content
        post_content = f"Title: {title}\n\n{body}"
        pyperclip.copy(post_content)

        # Verify clipboard synchronization to prevent OS/clipboard-history races
        for _ in range(15):
            if pyperclip.paste() == post_content:
                break
            time.sleep(0.1)

        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)

        # Save file
        filename = f"post_{post_id}.txt"
        file_path = os.path.join(tjm_project_dir, filename)
        logger.info(f"Saving file as {file_path}...")
        pyautogui.hotkey("ctrl", "s")
        time.sleep(1.5)

        pyperclip.copy(file_path)

        # Verify clipboard synchronization
        for _ in range(15):
            if pyperclip.paste() == file_path:
                break
            time.sleep(0.1)

        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(2.0)

        # Close Notepad (trying Alt+Space then 'c' first to bypass laptop Fn-Lock issues)
        logger.info("Closing Notepad...")
        pyautogui.hotkey("alt", "space")
        time.sleep(0.3)
        pyautogui.press("c")

        # Verify closed, fallback to Alt+F4 if still open
        notepad_closed = False
        for _ in range(4):
            time.sleep(0.5)
            if not is_notepad_open():
                notepad_closed = True
                break

        if not notepad_closed:
            logger.warning(
                "Notepad failed to close via Alt+Space. Trying Alt+F4 fallback..."
            )
            pyautogui.hotkey("alt", "f4")
            for _ in range(4):
                time.sleep(0.5)
                if not is_notepad_open():
                    notepad_closed = True
                    break


if __name__ == "__main__":
    main()
