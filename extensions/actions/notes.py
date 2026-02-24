defination = '''
function notes(action: str, content: str = "", title: str = "") -> str:

arguments:
- action: "add", "list", "read", "delete", "clear"
- content: Note content (required for add)
- title: Note title (optional for add, required for read/delete)

Example usage:
notes("add", content="Buy groceries", title="shopping")
notes("list")
notes("read", title="shopping")
notes("delete", title="shopping")
notes("clear")
'''

import os
import sys
import json
import tempfile
import subprocess
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOTES_FILE = os.path.join(BASE_DIR, "notes.json")

# ── Data helpers ──────────────────────────────────────────────────────────────

def _load() -> list:
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r") as f:
            return json.load(f)
    return []

def _save(data: list):
    with open(NOTES_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── UI helpers ────────────────────────────────────────────────────────────────

def _launch_script(script: str):
    """Launch completely independent popup process."""
    subprocess.Popen(
        [sys.executable, "-c", script],
        creationflags=subprocess.CREATE_NO_WINDOW
    )

def _launch_file(script: str):
    """Write script to temp file and launch — avoids all escaping issues."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                      delete=False, encoding="utf-8")
    tmp.write(script)
    tmp.close()
    subprocess.Popen(
        [sys.executable, tmp.name],
        creationflags=subprocess.CREATE_NO_WINDOW
    )

def _show_toast(title: str, message: str, color: str = "#7c6af7"):
    _launch_script(f"""
import tkinter as tk
root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg="#1e1e2e")
w, h = 380, 115
sx = root.winfo_screenwidth()
sy = root.winfo_screenheight()
root.geometry(f"{{w}}x{{h}}+{{sx - w - 20}}+{{sy - h - 60}}")
tk.Frame(root, bg="{color}", width=5).pack(side="left", fill="y")
frame = tk.Frame(root, bg="#1e1e2e", padx=14, pady=12)
frame.pack(fill="both", expand=True)
tk.Label(frame, text="{title}", bg="#1e1e2e", fg="{color}",
         font=("Segoe UI", 10, "bold")).pack(anchor="w")
tk.Label(frame, text="{message}", bg="#1e1e2e", fg="#e0e0f0",
         font=("Segoe UI", 9), wraplength=300).pack(anchor="w", pady=(4, 0))
tk.Button(frame, text="✕  Dismiss", command=root.destroy,
          bg="{color}", fg="white", relief="flat",
          font=("Segoe UI", 8), padx=10, pady=3,
          cursor="hand2").pack(anchor="e", pady=(8, 0))
root.mainloop()
""")

def _show_read_popup_from_file(data_file: str):
    """Read popup — reads note from temp json file, no escaping needed."""
    _launch_file(f"""
import tkinter as tk
import json, os

with open(r"{data_file}", "r", encoding="utf-8") as f:
    note = json.load(f)

root = tk.Tk()
root.title(note["title"])
root.configure(bg="#1e1e2e")
root.resizable(False, False)
w, h = 480, 320
x = (root.winfo_screenwidth()  - w) // 2
y = (root.winfo_screenheight() - h) // 2
root.geometry(f"{{w}}x{{h}}+{{x}}+{{y}}")
root.attributes("-topmost", True)

header = tk.Frame(root, bg="#56cfb2", height=50)
header.pack(fill="x")
tk.Label(header, text=f"  📝  {{note['title']}}", bg="#56cfb2", fg="white",
         font=("Segoe UI", 12, "bold")).pack(side="left", pady=12)

content_frame = tk.Frame(root, bg="#2a2a3d", padx=16, pady=12)
content_frame.pack(fill="both", expand=True, padx=16, pady=12)

tk.Label(content_frame, text=note["content"], bg="#2a2a3d", fg="#e0e0f0",
         font=("Segoe UI", 11), wraplength=420, justify="left").pack(anchor="w")
tk.Label(content_frame, text=f"Created: {{note['created']}}", bg="#2a2a3d", fg="#888aaa",
         font=("Segoe UI", 8)).pack(anchor="e", pady=(8, 0))

def on_close():
    try:
        os.remove(r"{data_file}")
    except:
        pass
    root.destroy()

tk.Button(root, text="Close", command=on_close,
          bg="#56cfb2", fg="white", relief="flat",
          font=("Segoe UI", 10), padx=20, pady=6,
          cursor="hand2").pack(pady=8)

root.mainloop()
""")

def _show_list_popup(data: list):
    # Write data to temp file — zero escaping issues
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                      delete=False, encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    data_file = tmp.name

    _launch_file(f"""
import tkinter as tk
from tkinter import ttk
import json, sys, subprocess, tempfile, os

with open(r"{data_file}", "r", encoding="utf-8") as f:
    data = json.load(f)

def open_note(note):
    # Write individual note to temp file and open read popup
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                      delete=False, encoding="utf-8")
    json.dump(note, tmp, ensure_ascii=False)
    tmp.close()

    script = f\"\"\"
import tkinter as tk
import json, os

with open(r"{{tmp.name}}", "r", encoding="utf-8") as f:
    note = json.load(f)

root = tk.Tk()
root.title(note["title"])
root.configure(bg="#1e1e2e")
root.resizable(False, False)
w, h = 480, 320
x = (root.winfo_screenwidth()  - w) // 2
y = (root.winfo_screenheight() - h) // 2
root.geometry(f"{{{{w}}}}x{{{{h}}}}+{{{{x}}}}+{{{{y}}}}")
root.attributes("-topmost", True)

header = tk.Frame(root, bg="#56cfb2", height=50)
header.pack(fill="x")
tk.Label(header, text=f"  📝  {{{{note['title']}}}}", bg="#56cfb2", fg="white",
         font=("Segoe UI", 12, "bold")).pack(side="left", pady=12)

content_frame = tk.Frame(root, bg="#2a2a3d", padx=16, pady=12)
content_frame.pack(fill="both", expand=True, padx=16, pady=12)

tk.Label(content_frame, text=note["content"], bg="#2a2a3d", fg="#e0e0f0",
         font=("Segoe UI", 11), wraplength=420, justify="left").pack(anchor="w")
tk.Label(content_frame, text=f"Created: {{{{note['created']}}}}", bg="#2a2a3d", fg="#888aaa",
         font=("Segoe UI", 8)).pack(anchor="e", pady=(8, 0))

def on_close():
    try:
        os.remove(r"{{tmp.name}}")
    except:
        pass
    root.destroy()

tk.Button(root, text="Close", command=on_close,
          bg="#56cfb2", fg="white", relief="flat",
          font=("Segoe UI", 10), padx=20, pady=6,
          cursor="hand2").pack(pady=8)

root.mainloop()
\"\"\"
    subprocess.Popen([sys.executable, "-c", script])

# ── Build UI ──────────────────────────────────────────────────────────────────

root = tk.Tk()
root.title("Your Notes")
root.configure(bg="#1e1e2e")
root.resizable(False, False)
w, h = 520, 420
x = (root.winfo_screenwidth()  - w) // 2
y = (root.winfo_screenheight() - h) // 2
root.geometry(f"{{w}}x{{h}}+{{x}}+{{y}}")
root.attributes("-topmost", True)

header = tk.Frame(root, bg="#7c6af7", height=50)
header.pack(fill="x")
tk.Label(header, text="  📝  Your Notes", bg="#7c6af7", fg="white",
         font=("Segoe UI", 13, "bold")).pack(side="left", pady=12)
tk.Label(header, text=f"{{len(data)}} note(s)  ", bg="#7c6af7", fg="white",
         font=("Segoe UI", 9)).pack(side="right", pady=12)

if not data:
    tk.Label(root, text="No notes yet.", bg="#1e1e2e", fg="#888aaa",
             font=("Segoe UI", 11)).pack(expand=True)
else:
    canvas = tk.Canvas(root, bg="#1e1e2e", highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    frame = tk.Frame(canvas, bg="#1e1e2e")
    frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    scrollbar.pack(side="right", fill="y")

    for n in data:
        card = tk.Frame(frame, bg="#2a2a3d", padx=12, pady=8, cursor="hand2")
        card.pack(fill="x", pady=4, padx=4)

        dot  = tk.Label(card, text="●", bg="#2a2a3d", fg="#7c6af7",
                        font=("Segoe UI", 8), cursor="hand2")
        dot.pack(side="left", padx=(0, 8))

        info = tk.Frame(card, bg="#2a2a3d", cursor="hand2")
        info.pack(side="left", fill="x", expand=True)

        lbl_title = tk.Label(info, text=n["title"], bg="#2a2a3d", fg="#e0e0f0",
                             font=("Segoe UI", 10, "bold"), cursor="hand2")
        lbl_title.pack(anchor="w")

        lbl_date = tk.Label(info, text=n["created"], bg="#2a2a3d", fg="#888aaa",
                            font=("Segoe UI", 8), cursor="hand2")
        lbl_date.pack(anchor="w")

        # Hover effect
        def _enter(e, c=card, i=info, d=dot, lt=lbl_title, ld=lbl_date):
            for w in [c, i, d, lt, ld]: w.configure(bg="#3a3a55")
        def _leave(e, c=card, i=info, d=dot, lt=lbl_title, ld=lbl_date):
            for w in [c, i, d, lt, ld]: w.configure(bg="#2a2a3d")

        # Click handler
        def _click(e, note=n): open_note(note)

        for widget in [card, dot, info, lbl_title, lbl_date]:
            widget.bind("<Enter>",    _enter)
            widget.bind("<Leave>",    _leave)
            widget.bind("<Button-1>", _click)

def on_close():
    try:
        os.remove(r"{data_file}")
    except:
        pass
    root.destroy()

tk.Button(root, text="Close", command=on_close,
          bg="#7c6af7", fg="white", relief="flat",
          font=("Segoe UI", 10), padx=20, pady=6,
          cursor="hand2").pack(pady=12)

root.mainloop()
""")

def _show_read_popup(note: dict):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                      delete=False, encoding="utf-8")
    json.dump(note, tmp, ensure_ascii=False)
    tmp.close()
    _show_read_popup_from_file(tmp.name)

# ── Main function ─────────────────────────────────────────────────────────────

def notes(action: str, content: str = "", title: str = "") -> str:
    action = action.lower().strip()
    data   = _load()

    if action == "add":
        if not content:
            return "Please provide note content."
        title = title or f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        data.append({
            "title":   title,
            "content": content,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        _save(data)
        _show_toast("Note Saved ✓", f"'{title}' has been saved.")
        return f"Note saved: '{title}'"

    elif action == "list":
        _show_list_popup(data)
        count = len(data)
        return f"Showing {count} note(s)." if count else "No notes found."

    elif action == "read":
        if not title:
            return "Please provide a title to read."
        for n in data:
            if n["title"].lower() == title.lower():
                _show_read_popup(n)
                return f"Opening note: '{title}'"
        _show_toast("Not Found", f"Note '{title}' not found.", color="#f75f6a")
        return f"Note '{title}' not found."

    elif action == "delete":
        if not title:
            return "Please provide a title to delete."
        new_data = [n for n in data if n["title"].lower() != title.lower()]
        if len(new_data) == len(data):
            _show_toast("Not Found", f"Note '{title}' not found.", color="#f75f6a")
            return f"Note '{title}' not found."
        _save(new_data)
        _show_toast("Note Deleted", f"'{title}' has been deleted.", color="#f75f6a")
        return f"Note '{title}' deleted."

    elif action == "clear":
        count = len(data)
        _save([])
        _show_toast("Cleared", f"All {count} note(s) deleted.", color="#f75f6a")
        return f"Cleared {count} note(s)."

    else:
        return f"Unknown action '{action}'. Use: add, list, read, delete, clear."


if __name__ == "__main__":
    import time
    print(notes("add", content="Buy groceries and milk", title="Cart"))
    time.sleep(1)
    print(notes("list"))
    time.sleep(10)