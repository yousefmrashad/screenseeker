import os
import sys
import time

import pyautogui
import typer
from PIL import Image, ImageDraw

import config as app_config
from screenseeker import ElementConfig, ScreenSeekeR

app = typer.Typer(add_completion=False)


@app.command()
def main(
    target_name: str = typer.Argument(
        "Notepad icon", help="Name of the target element (e.g. 'Notepad icon')"
    ),
    instruction: str = typer.Argument(
        "Find the Notepad shortcut icon on the desktop",
        help="Grounding instruction (e.g. 'Find the Notepad shortcut icon on the desktop')",
    ),
    min_size_ratio: float = typer.Option(
        0.25,
        "--min-size-ratio",
        help="Dynamic Smin scaling ratio (relative to screen size)",
    ),
    max_depth: int = typer.Option(
        3, "--max-depth", help="Maximum search recursion depth"
    ),
) -> None:
    # Setup directories
    annotated_dir: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "annotated_screenshots"
    )
    os.makedirs(annotated_dir, exist_ok=True)

    print("Initializing ScreenSeekeR visual grounding agent...")
    seeker: ScreenSeekeR = ScreenSeekeR()
    elem_config: ElementConfig = ElementConfig(
        target_name=target_name,
        instruction=instruction,
        min_size_ratio=min_size_ratio,
        max_depth=max_depth,
        model_name=app_config.MODEL_NAME,
    )

    print("Taking desktop screenshot...")
    pyautogui.hotkey("win", "d")  # Show desktop to ensure icons are visible
    time.sleep(1)  # Allow time for desktop to be shown
    screenshot: Image.Image = pyautogui.screenshot()

    print(f"Running visual search to locate: '{elem_config.target_name}'...")
    try:
        icon_box = seeker.visual_search(screenshot, elem_config)
    except Exception as e:
        print(f"Error during visual search: {e}", file=sys.stderr)
        return

    if icon_box is None:
        print(
            f"[-] '{elem_config.target_name}' not found on the desktop.",
            file=sys.stderr,
        )
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

    print(f"[+] '{elem_config.target_name}' successfully grounded!")
    print(f"    - Bounding Box in Pixels: {icon_box}")
    print(f"    - Center Pixel Coordinates: ({cx}, {cy})")
    print(f"    - Display Scale Factors: x={scale_x:.2f}, y={scale_y:.2f}")
    print(f"    - Resolved Click Coordinates: ({click_x}, {click_y})")

    # Annotate screenshot
    draw: ImageDraw.ImageDraw = ImageDraw.Draw(screenshot)
    draw.rectangle(icon_box, outline="red", width=3)

    # Save with unique name to prevent overwriting previous detections
    timestamp: str = time.strftime("%Y%m%d_%H%M%S")
    sanitized_target: str = "".join(
        c if c.isalnum() else "_" for c in target_name
    ).strip("_")
    filename: str = f"grounding_{sanitized_target}_{timestamp}_{click_x}_{click_y}.png"
    output_path: str = os.path.join(annotated_dir, filename)
    screenshot.save(output_path)

    print("[+] Saved annotated screenshot to:")
    print(f"    {output_path}")


if __name__ == "__main__":
    app()
