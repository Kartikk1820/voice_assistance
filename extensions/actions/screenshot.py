defination = '''
function screenshot(save_path: str = None) -> str:

arguments:
- save_path: (optional) Full path to save screenshot. Defaults to Desktop/screenshots folder.

Example usage:
screenshot()
screenshot("C:/Users/karti/Pictures/myshot.png")
'''

import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

from PIL import ImageGrab

# Default save folder — Desktop/screenshots/
DEFAULT_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop", "screenshots")

def screenshot(save_path: str = None) -> str:
    if save_path is None:
        os.makedirs(DEFAULT_FOLDER, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(DEFAULT_FOLDER, f"screenshot_{timestamp}.png")

    try:
        img = ImageGrab.grab()  # captures full screen
        img.save(save_path)
        if DEBUG:
            print(f"Screenshot saved: {save_path}")
        return f"Screenshot saved to: {save_path}"
    except Exception as e:
        return f"Failed to take screenshot: {e}"


if __name__ == "__main__":
    print(screenshot())