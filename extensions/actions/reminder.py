defination = '''
function reminder(action: str, message: str = "", seconds: int = 0, minutes: int = 0, hours: int = 0) -> str:

arguments:
- action: "set" to create reminder, "list" to see all, "clear" to remove all
- message: The reminder message (required for set)
- seconds: Delay in seconds (optional)
- minutes: Delay in minutes (optional)
- hours: Delay in hours (optional)

Example usage:
reminder("set", "Drink water", minutes=30)
reminder("set", "Meeting starts", hours=1, minutes=30)
reminder("list")
reminder("clear")
'''

import os
import json
import subprocess
import threading
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REMINDER_FILE = os.path.join(BASE_DIR, "reminders.json")
SCRIPTS_DIR   = os.path.join(BASE_DIR, "reminder_scripts")
os.makedirs(SCRIPTS_DIR, exist_ok=True)

def _load_reminders() -> list:
    if os.path.exists(REMINDER_FILE):
        with open(REMINDER_FILE, "r") as f:
            return json.load(f)
    return []

def _save_reminders(data: list):
    with open(REMINDER_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _show_popup(message: str):
    """Show Windows popup using PowerShell directly (instant)."""
    safe_message = message.replace("'", "''")
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.MessageBox]::Show("
        f"'{safe_message}', 'Voice Assistant Reminder', "
        f"[System.Windows.Forms.MessageBoxButtons]::OK, "
        f"[System.Windows.Forms.MessageBoxIcon]::Information)"
    )
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        creationflags=subprocess.CREATE_NO_WINDOW
    )

def _thread_reminder(reminder_id: int, message: str, total_seconds: int):
    """Background thread for short reminders — fires popup after delay."""
    time.sleep(total_seconds)
    _show_popup(message)
    # Remove from reminders file after firing
    reminders = _load_reminders()
    _save_reminders([r for r in reminders if r["id"] != reminder_id])
    if DEBUG:
        print(f"\nReminder #{reminder_id} fired: {message}")

def _create_ps1(reminder_id: int, message: str) -> str:
    ps1_path = os.path.join(SCRIPTS_DIR, f"reminder_{reminder_id}.ps1")
    safe_message = message.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms\n"
        f"[System.Windows.Forms.MessageBox]::Show("
        f"'{safe_message}', "
        f"'Voice Assistant Reminder', "
        f"[System.Windows.Forms.MessageBoxButtons]::OK, "
        f"[System.Windows.Forms.MessageBoxIcon]::Information)\n"
    )
    with open(ps1_path, "w") as f:
        f.write(script)
    return ps1_path

def _schedule_windows_task(reminder_id: int, message: str, fire_at: datetime) -> bool:
    """Task Scheduler for long reminders (>= 1 min) — survives script exit."""
    ps1_path = _create_ps1(reminder_id, message)
    task_name = f"VoiceAssist_Reminder_{reminder_id}"
    time_str  = fire_at.strftime("%H:%M")
    date_str  = fire_at.strftime("%d/%m/%Y")

    tr = f'powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "{ps1_path}"'
    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", tr,
        "/sc", "once",
        "/st", time_str,
        "/sd", date_str,
        "/f"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if DEBUG:
        print(f"schtasks: {result.returncode} | {result.stdout.strip()} | {result.stderr.strip()}")
    return result.returncode == 0

def _remove_windows_task(reminder_id: int):
    task_name = f"VoiceAssist_Reminder_{reminder_id}"
    subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True)
    ps1_path = os.path.join(SCRIPTS_DIR, f"reminder_{reminder_id}.ps1")
    if os.path.exists(ps1_path):
        os.remove(ps1_path)

def reminder(action: str, message: str = "", seconds: int = 0, minutes: int = 0, hours: int = 0) -> str:
    action = action.lower().strip()

    if action == "set":
        if not message:
            return "Please provide a reminder message."

        total_seconds = seconds + (minutes * 60) + (hours * 3600)
        if total_seconds <= 0:
            return "Please provide a valid time (seconds, minutes, or hours)."

        fire_at   = datetime.now() + timedelta(seconds=total_seconds)
        reminders = _load_reminders()
        reminder_id = (max(r["id"] for r in reminders) + 1) if reminders else 1

        if total_seconds < 60:
            # SHORT reminder — use background thread (instant, no Task Scheduler)
            t = threading.Thread(
                target=_thread_reminder,
                args=(reminder_id, message, total_seconds),
                daemon=False  # keep process alive until popup fires
            )
            t.start()
            method = "thread"
        else:
            # LONG reminder — use Task Scheduler (survives script exit)
            success = _schedule_windows_task(reminder_id, message, fire_at)
            if not success:
                return "Failed to schedule reminder. Try running terminal as Administrator."
            method = "scheduler"

        reminders.append({
            "id": reminder_id,
            "message": message,
            "fire_at": fire_at.strftime("%Y-%m-%d %H:%M:%S"),
            "method": method
        })
        _save_reminders(reminders)

        parts = []
        if hours:   parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        if seconds: parts.append(f"{seconds}s")

        return f"Reminder set! Popup in {' '.join(parts)}: '{message}'"

    elif action == "list":
        reminders = _load_reminders()
        if not reminders:
            return "No active reminders."
        result = "Active reminders:\n"
        for r in reminders:
            result += f"  #{r['id']} — '{r['message']}' at {r['fire_at']}\n"
        return result.strip()

    elif action == "clear":
        reminders = _load_reminders()
        for r in reminders:
            if r.get("method") == "scheduler":
                _remove_windows_task(r["id"])
        _save_reminders([])
        return f"Cleared {len(reminders)} reminder(s)."

    else:
        return f"Unknown action '{action}'. Use: set, list, clear."


if __name__ == "__main__":
    print(reminder("list"))