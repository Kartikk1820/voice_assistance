defination = '''
function open_app(app_name: str) -> str:

arguments:
- app_name: Name of the application to open (e.g. "chrome", "vscode", "notepad", "calculator")

Example usage:
open_app("chrome")
open_app("vscode")
open_app("notepad")
open_app("calculator")
open_app("spotify")
'''

import os
import subprocess
import webbrowser
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

# Map of app aliases -> possible executable paths/commands
APP_MAP = {
    # Browsers
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],

    # Dev tools
    "vscode": [
        r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "code": "vscode",  # alias
    "visual studio code": "vscode",  # alias

    "git bash": [
        r"C:\Program Files\Git\git-bash.exe",
    ],
    "postman": [
        r"C:\Users\{user}\AppData\Local\Postman\Postman.exe",
    ],
    "github desktop": [
        r"C:\Users\{user}\AppData\Local\GitHubDesktop\GitHubDesktop.exe",
    ],

    # Terminals
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "terminal": ["wt.exe"],  # Windows Terminal
    "windows terminal": ["wt.exe"],

    # System apps (always available on Windows)
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "wordpad": ["wordpad.exe"],
    "task manager": ["taskmgr.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "control panel": ["control.exe"],
    "settings": ["ms-settings:"],  # special URI
    "snipping tool": ["SnippingTool.exe"],

    # Office
    "word": [
        r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
    ],
    "excel": [
        r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
    ],
    "powerpoint": [
        r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE",
    ],

    # Media & Entertainment
    "spotify": [
        r"C:\Users\{user}\AppData\Roaming\Spotify\Spotify.exe",
    ],
    "vlc": [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ],
    "windows media player": ["wmplayer.exe"],

    # Communication
    "discord": [
        r"C:\Users\{user}\AppData\Local\Discord\Update.exe",
    ],
    "slack": [
        r"C:\Users\{user}\AppData\Local\slack\slack.exe",
    ],
    "teams": [
        r"C:\Users\{user}\AppData\Local\Microsoft\Teams\current\Teams.exe",
    ],
    "zoom": [
        r"C:\Users\{user}\AppData\Roaming\Zoom\bin\Zoom.exe",
    ],
    "whatsapp": [
        r"C:\Users\{user}\AppData\Local\WhatsApp\WhatsApp.exe",
    ],

    # Utilities
    "obs": [
        r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    ],
    "7zip": [
        r"C:\Program Files\7-Zip\7zFM.exe",
    ],
    "winrar": [
        r"C:\Program Files\WinRAR\WinRAR.exe",
    ],
    "notepad++": [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
    ],
}

# Google search URLs for downloading apps
DOWNLOAD_SEARCH = "https://www.google.com/search?q=download+{app}"


def _resolve_alias(app_name: str) -> str:
    """Resolve alias to canonical name."""
    val = APP_MAP.get(app_name)
    if isinstance(val, str):
        return val  # it's an alias
    return app_name


def _get_username() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or "User"


def _resolve_paths(paths: list) -> list:
    """Replace {user} placeholder with actual username."""
    user = _get_username()
    return [p.replace("{user}", user) for p in paths]


def open_app(app_name: str) -> str:
    app_key = app_name.lower().strip()

    # Resolve alias
    app_key = _resolve_alias(app_key)
    if app_key not in APP_MAP:
        # Not in map at all — search Google to download
        search_url = DOWNLOAD_SEARCH.format(app=app_name.replace(" ", "+"))
        webbrowser.open(search_url)
        return f"'{app_name}' not recognized. Opened Google search to download it."

    paths = APP_MAP[app_key]
    if isinstance(paths, str):
        # Still an alias after resolution (shouldn't happen but safe)
        paths = APP_MAP.get(paths, [])

    paths = _resolve_paths(paths)

    # Try each path
    for path in paths:
        # Handle special URIs like ms-settings:
        if ":" in path and not os.path.isabs(path):
            try:
                os.startfile(path)
                if DEBUG:
                    print(f"Opened URI: {path}")
                return f"Opening {app_name}."
            except Exception as e:
                if DEBUG:
                    print(f"URI failed: {e}")
                continue

        # Handle plain executables (like notepad.exe, calc.exe)
        if not os.path.isabs(path):
            try:
                subprocess.Popen([path], shell=True)
                if DEBUG:
                    print(f"Opened via shell: {path}")
                return f"Opening {app_name}."
            except Exception as e:
                if DEBUG:
                    print(f"Shell open failed: {e}")
                continue

        # Handle full absolute paths
        if os.path.exists(path):
            try:
                subprocess.Popen([path])
                if DEBUG:
                    print(f"Opened: {path}")
                return f"Opening {app_name}."
            except Exception as e:
                if DEBUG:
                    print(f"Failed to open {path}: {e}")
                continue

    # None of the paths worked — search Google
    search_url = DOWNLOAD_SEARCH.format(app=app_name.replace(" ", "+"))
    webbrowser.open(search_url)
    return f"'{app_name}' not found on this PC. Opened Google to download it."


if __name__ == "__main__":
    print(open_app("chrome"))
    print(open_app("notepad"))
    print(open_app("calculator"))
    print(open_app("vscode"))