defination = '''
function open_folder(name: str) -> str:

arguments:
- name: Folder name to open. Examples: "downloads", "desktop", "projects", "documents", "music", "pictures", "videos"

Example usage:
open_folder("downloads")
open_folder("desktop")
open_folder("projects")
'''

import os
import subprocess
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

USER = os.path.expanduser("~")

FOLDER_MAP = {
    # Common Windows folders
    "desktop":      os.path.join(USER, "Desktop"),
    "downloads":    os.path.join(USER, "Downloads"),
    "documents":    os.path.join(USER, "Documents"),
    "music":        os.path.join(USER, "Music"),
    "pictures":     os.path.join(USER, "Pictures"),
    "videos":       os.path.join(USER, "Videos"),

    # Project folder — update this path to yours
    "projects":     os.path.join(USER, "Documents", "SIC_Project"),

    # This voice assistant project
    "voiceassist":  os.path.join(USER, "Documents", "SIC_Project", "VoiceAssist"),
    "voice assist": os.path.join(USER, "Documents", "SIC_Project", "VoiceAssist"),

    # System folders
    "appdata":      os.path.join(USER, "AppData"),
    "temp":         os.path.join(os.environ.get("TEMP", "C:\\Windows\\Temp")),
    "c drive":      "C:\\",
    "root":         "C:\\",
}

def open_folder(name: str) -> str:
    key = name.lower().strip()

    path = FOLDER_MAP.get(key)

    # If not in map, try treating it as a direct path
    if path is None:
        if os.path.isdir(name):
            path = name
        else:
            return f"Folder '{name}' not recognized. Add it to FOLDER_MAP or provide full path."

    if not os.path.exists(path):
        return f"Folder not found: {path}"

    try:
        subprocess.Popen(f'explorer "{path}"')
        if DEBUG:
            print(f"Opening folder: {path}")
        return f"Opening {name}: {path}"
    except Exception as e:
        return f"Failed to open folder: {e}"


if __name__ == "__main__":
    print(open_folder("downloads"))
    print(open_folder("desktop"))
    print(open_folder("projects"))