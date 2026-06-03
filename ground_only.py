import os
import sys
import time
import pyautogui
from PIL import Image, ImageDraw
from screenseeker import ElementConfig, ScreenSeekeR


def main() -> None:
    # Setup directories
    annotated_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "annotated_screenshots")
    os.makedirs(annotated_dir, exist_ok=True)

    print("Initializing ScreenSeekeR visual grounding agent...")
    seeker: ScreenSeekeR = ScreenSeekeR()
    config: ElementConfig = ElementConfig()

    print("Taking desktop screenshot...")
    screenshot: Image.Image = pyautogui.screenshot()

    print("Running visual search to locate Notepad icon...")
    try:
        icon_box = seeker.visual_search(screenshot, config)
    except Exception as e:
        print(f"Error during visual search: {e}", file=sys.stderr)
        return

    if icon_box is None:
        print("[-] Notepad icon not found on the desktop.", file=sys.stderr)
        return

    # Compute coordinates
    x1, y1, x2, y2 = icon_box
    cx: int = int((x1 + x2) / 2)
    cy: int = int((y1 + y2) / 2)

    # DPI scaling conversion
    screen_w, screen_h = pyautogui.size()
    img_w, img_h = screenshot.size
    scale_x: float = screen_w / img_w
    scale_y: float = screen_h / img_h
    click_x: int = int(cx * scale_x)
    click_y: int = int(cy * scale_y)

    print(f"[+] Notepad icon successfully grounded!")
    print(f"    - Bounding Box in Pixels: {icon_box}")
    print(f"    - Center Pixel Coordinates: ({cx}, {cy})")
    print(f"    - Display Scale Factors: x={scale_x:.2f}, y={scale_y:.2f}")
    print(f"    - Resolved Click Coordinates: ({click_x}, {click_y})")

    # Annotate screenshot
    draw: ImageDraw.ImageDraw = ImageDraw.Draw(screenshot)
    draw.rectangle(icon_box, outline="red", width=3)

    # Save with unique name to prevent overwriting previous detections
    timestamp: str = time.strftime("%Y%m%d_%H%M%S")
    filename: str = f"grounding_detection_{timestamp}_{click_x}_{click_y}.png"
    output_path: str = os.path.join(annotated_dir, filename)
    screenshot.save(output_path)

    print(f"[+] Saved annotated screenshot to:")
    print(f"    {output_path}")


if __name__ == "__main__":
    main()
