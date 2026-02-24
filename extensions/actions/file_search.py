defination = '''
function file_search(query: str, action: str = "search", path: str = None) -> str:

arguments:
- query: File name or keyword to search
- action: "search" to find files, "open" to open first result
- path: (optional) folder to search in. Defaults to whole PC (C drive)

Example usage:
file_search("resume")
file_search("resume", action="open")
file_search("notes.txt", path="C:/Users/karti/Documents")
'''

import os
import subprocess
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

# Folders to skip — speeds up search massively
SKIP_DIRS = {
    "Windows", "Program Files", "Program Files (x86)",
    "$Recycle.Bin", "System Volume Information",
    "AppData", "ProgramData", "node_modules",
    ".git", "__pycache__", "venv", ".venv"
}

MAX_RESULTS = 10  # stop after finding this many

def _search(query: str, root: str) -> list:
    query   = query.lower()
    results = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip unwanted folders in-place (fast pruning)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            if query in filename.lower():
                results.append(os.path.join(dirpath, filename))
                if len(results) >= MAX_RESULTS:
                    return results  # stop early

    return results

def file_search(query: str, action: str = "search", path: str = None) -> str:
    action = action.lower().strip()

    # Default search root
    root = path or "C:\\"

    if DEBUG:
        print(f"Searching '{query}' in {root}...")

    results = _search(query, root)

    if not results:
        return f"No files found matching '{query}'."

    if action == "open":
        # Open the first result
        try:
            os.startfile(results[0])
            return f"Opening: {results[0]}"
        except Exception as e:
            return f"Found but failed to open: {results[0]} | Error: {e}"

    elif action == "search":
        response = f"Found {len(results)} file(s) matching '{query}':\n"
        for i, path in enumerate(results, 1):
            response += f"  {i}. {path}\n"
        return response.strip()

    else:
        return f"Unknown action '{action}'. Use: search, open."


if __name__ == "__main__":
    print(file_search("resume"))
    print(file_search("notes.txt", action="open"))