defination = '''
function window_control(action: str) -> str:

arguments:
- action: The action to perform on the focused window. One of: "minimize", "maximize", "close", "restore"

Example usage:
window_control("minimize")
window_control("maximize")
window_control("close")
window_control("restore")
'''

import os
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

import pygetwindow as gw

def window_control(action: str) -> str:
    action = action.lower().strip()

    # Get the currently active/focused window
    window = gw.getActiveWindow()

    if window is None:
        return "No active window found."

    title = window.title
    if DEBUG:
        print(f"Active window: {title} | Action: {action}")

    try:
        if action == "minimize":
            window.minimize()
            return f"Minimized: {title}"

        elif action == "maximize":
            window.maximize()
            return f"Maximized: {title}"

        elif action == "restore":
            window.restore()
            return f"Restored: {title}"

        elif action == "close":
            window.close()
            return f"Closed: {title}"

        else:
            return f"Unknown action '{action}'. Use: minimize, maximize, restore, close."

    except Exception as e:
        return f"Failed to {action} window '{title}': {e}"


if __name__ == "__main__":
    import time
    time.sleep(2)  # 2 sec to switch to any window for testing
    print(window_control("minimize"))