"""
analytics.py  —  Command Analytics Logger
==========================================
Tracks every command the assistant executes:
  - what was said, what function was called
  - how long thinking + execution took
  - whether it succeeded or failed
  - timestamp

Drop this file into:  extensions/essentials/analytics.py

Usage (in main.py / gui.py):
    from extensions.essentials.analytics import analytics

    session = analytics.start_session()

    with analytics.track(session, user_text, function_name) as t:
        call_function_by_name(function_name, args)
    # ↑ automatically records duration + success/fail

    analytics.end_session(session)
    analytics.print_session_summary(session)
"""

import os
import json
import time
import contextlib
from datetime import datetime, date
from typing import Optional

# ── paths ─────────────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANALYTICS_DIR = os.path.join(BASE_DIR, "analytics")
LOG_FILE      = os.path.join(ANALYTICS_DIR, "commands.json")
STATS_FILE    = os.path.join(ANALYTICS_DIR, "stats.json")

os.makedirs(ANALYTICS_DIR, exist_ok=True)

# ── internal helpers ──────────────────────────────────────────────────────────

def _load_log() -> list:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return []

def _save_log(data: list):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {
        "total_commands":   0,
        "total_success":    0,
        "total_errors":     0,
        "total_sessions":   0,
        "function_counts":  {},     # {"open_app": 12, "music": 8, ...}
        "daily_counts":     {},     # {"2025-01-01": 5, ...}
        "avg_think_ms":     0.0,
        "avg_exec_ms":      0.0,
    }

def _save_stats(data: dict):
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _rolling_avg(current_avg: float, new_val: float, n: int) -> float:
    """Update a running average without storing all values."""
    return ((current_avg * (n - 1)) + new_val) / n

# ── public API ────────────────────────────────────────────────────────────────

def start_session() -> str:
    """
    Call once at app startup. Returns a session_id string.
    Records session start in stats.
    """
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    stats = _load_stats()
    stats["total_sessions"] += 1
    _save_stats(stats)
    return session_id


def log_command(
    session_id:    str,
    user_text:     str,
    function_name: str,
    args:          dict,
    think_ms:      float,
    exec_ms:       float,
    success:       bool,
    error_msg:     str = "",
):
    """
    Record a single command entry. Called automatically by track().
    You can also call this manually if needed.
    """
    today    = date.today().isoformat()
    log      = _load_log()
    stats    = _load_stats()

    entry = {
        "session":       session_id,
        "timestamp":     datetime.now().isoformat(timespec="seconds"),
        "user_text":     user_text,
        "function":      function_name,
        "args":          args,
        "think_ms":      round(think_ms,  1),
        "exec_ms":       round(exec_ms,   1),
        "total_ms":      round(think_ms + exec_ms, 1),
        "success":       success,
        "error":         error_msg,
    }
    log.append(entry)
    _save_log(log)

    # ── update rolling stats ──
    stats["total_commands"] += 1
    n = stats["total_commands"]

    if success:
        stats["total_success"] += 1
    else:
        stats["total_errors"] += 1

    # function frequency
    fc = stats["function_counts"]
    fc[function_name] = fc.get(function_name, 0) + 1

    # daily count
    dc = stats["daily_counts"]
    dc[today] = dc.get(today, 0) + 1

    # rolling averages (only successful commands have meaningful exec time)
    stats["avg_think_ms"] = _rolling_avg(stats["avg_think_ms"], think_ms, n)
    if success:
        s = stats["total_success"]
        stats["avg_exec_ms"] = _rolling_avg(stats["avg_exec_ms"], exec_ms, s)

    _save_stats(stats)
    return entry


@contextlib.contextmanager
def track(
    session_id:    str,
    user_text:     str,
    function_name: str,
    args:          dict,
    think_ms:      float = 0.0,
):
    """
    Context manager. Wraps a function execution and auto-logs result.

    Usage:
        with analytics.track(session, text, fn_name, fn_args, think_ms=t) as t:
            call_function_by_name(fn_name, fn_args)
    """
    t_start = time.perf_counter()
    error   = ""
    success = True
    try:
        yield
    except Exception as e:
        success   = False
        error     = str(e)
        raise
    finally:
        exec_ms = (time.perf_counter() - t_start) * 1000
        log_command(
            session_id    = session_id,
            user_text     = user_text,
            function_name = function_name,
            args          = args,
            think_ms      = think_ms,
            exec_ms       = exec_ms,
            success       = success,
            error_msg     = error,
        )


def end_session(session_id: str):
    """Call on goodbye / app close. Just a semantic marker — no-op for now."""
    pass   # future: could write session-end marker to log


# ── summary & display ─────────────────────────────────────────────────────────

def get_stats() -> dict:
    return _load_stats()


def get_session_commands(session_id: str) -> list:
    return [e for e in _load_log() if e["session"] == session_id]


def print_session_summary(session_id: str):
    """Print a clean summary table to the terminal at end of session."""
    cmds   = get_session_commands(session_id)
    stats  = get_stats()

    if not cmds:
        print("\n[analytics] No commands recorded this session.")
        return

    total     = len(cmds)
    succeeded = sum(1 for c in cmds if c["success"])
    failed    = total - succeeded
    avg_think = sum(c["think_ms"] for c in cmds) / total
    avg_exec  = sum(c["exec_ms"]  for c in cmds if c["success"]) / max(succeeded, 1)
    slowest   = max(cmds, key=lambda c: c["total_ms"])
    fastest   = min(cmds, key=lambda c: c["total_ms"])

    # top functions this session
    fn_counts: dict = {}
    for c in cmds:
        fn_counts[c["function"]] = fn_counts.get(c["function"], 0) + 1
    top_fns = sorted(fn_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    W = 54
    line  = "─" * W
    dline = "═" * W

    print(f"\n╔{dline}╗")
    print(f"║{'  SESSION ANALYTICS REPORT':^{W}}║")
    print(f"╠{dline}╣")
    print(f"║  Session ID : {session_id:<{W-15}}║")
    print(f"╠{line}╣")
    print(f"║  {'COMMANDS':30} {'VALUE':>10}    ║")
    print(f"║  {'─'*30} {'─'*10}    ║")
    print(f"║  {'Total commands':30} {total:>10}    ║")
    print(f"║  {'Succeeded':30} {succeeded:>10}    ║")
    print(f"║  {'Failed':30} {failed:>10}    ║")
    print(f"╠{line}╣")
    print(f"║  {'TIMING':30} {'VALUE':>10}    ║")
    print(f"║  {'─'*30} {'─'*10}    ║")
    print(f"║  {'Avg think time':30} {avg_think:>9.0f}ms ║")
    print(f"║  {'Avg exec time':30} {avg_exec:>9.0f}ms ║")
    print(f"║  {'Slowest command':30} {slowest['total_ms']:>9.0f}ms ║")
    print(f"║  {('  └ \"' + slowest['user_text'][:24] + '\"'):30} {'':>10}    ║")
    print(f"║  {'Fastest command':30} {fastest['total_ms']:>9.0f}ms ║")
    print(f"║  {('  └ \"' + fastest['user_text'][:24] + '\"'):30} {'':>10}    ║")
    print(f"╠{line}╣")
    print(f"║  {'TOP FUNCTIONS THIS SESSION':<{W}}║")
    print(f"║  {'─'*30} {'─'*10}    ║")
    for fn, count in top_fns:
        bar = "█" * count
        print(f"║  {fn:<30} {bar:<10} {count:>2}  ║")
    print(f"╠{line}╣")
    print(f"║  {'ALL-TIME STATS':<{W}}║")
    print(f"║  {'─'*30} {'─'*10}    ║")
    print(f"║  {'Total all-time commands':30} {stats['total_commands']:>10}    ║")
    print(f"║  {'All-time avg think':30} {stats['avg_think_ms']:>9.0f}ms ║")

    if stats["function_counts"]:
        top_ever = max(stats["function_counts"].items(), key=lambda x: x[1])
        print(f"║  {'Most used ever':30} {top_ever[0][:10]:>10}    ║")
        print(f"║  {'  └ used':30} {top_ever[1]:>9}x  ║")

    print(f"╚{dline}╝\n")


def print_all_time_report():
    """Print an all-time leaderboard. Call anytime."""
    stats = get_stats()
    log   = _load_log()

    if not log:
        print("[analytics] No data yet.")
        return

    W    = 54
    line = "─" * W

    # sort functions by usage
    fn_sorted = sorted(stats["function_counts"].items(), key=lambda x: x[1], reverse=True)

    # last 7 days activity
    today     = date.today()
    week_days = [(today.replace(day=today.day - i)).isoformat() for i in range(6, -1, -1)]
    dc        = stats["daily_counts"]
    max_day   = max((dc.get(d, 0) for d in week_days), default=1) or 1

    print(f"\n╔{'═'*W}╗")
    print(f"║{'  ALL-TIME ANALYTICS':^{W}}║")
    print(f"╠{line}╣")
    print(f"║  {'Total commands':30} {stats['total_commands']:>10}    ║")
    print(f"║  {'Total sessions':30} {stats['total_sessions']:>10}    ║")
    print(f"║  {'Total errors':30} {stats['total_errors']:>10}    ║")
    success_rate = (stats['total_success'] / max(stats['total_commands'], 1)) * 100
    print(f"║  {'Success rate':30} {success_rate:>9.1f}%  ║")
    print(f"║  {'Avg think time':30} {stats['avg_think_ms']:>9.0f}ms ║")
    print(f"║  {'Avg exec time':30} {stats['avg_exec_ms']:>9.0f}ms ║")
    print(f"╠{line}╣")
    print(f"║  {'FUNCTION LEADERBOARD':<{W}}║")
    print(f"║  {'─'*30} {'─'*10}    ║")
    for fn, count in fn_sorted[:10]:
        bar = "█" * min(count, 10)
        print(f"║  {fn:<30} {bar:<10} {count:>2}  ║")
    print(f"╠{line}╣")
    print(f"║  {'LAST 7 DAYS ACTIVITY':<{W}}║")
    print(f"║  {'─'*{W}}║")
    for d in week_days:
        count   = dc.get(d, 0)
        bar_len = int((count / max_day) * 20)
        bar     = "█" * bar_len
        label   = d[5:]  # MM-DD
        print(f"║  {label}  {bar:<20} {count:>3}  {'':>7}║")
    print(f"╚{'═'*W}╝\n")


# ── test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import random

    print("Running analytics self-test...\n")
    session = start_session()

    test_commands = [
        ("open chrome",          "open_app",      {"app_name": "chrome"},    True),
        ("play music",           "music",         {"action": "play"},         True),
        ("what time is it",      "tell_time",     {},                         True),
        ("set reminder 5 min",   "reminder",      {"action":"set","message":"test","minutes":5}, True),
        ("search python",        "google_search", {"query": "python"},        True),
        ("open youtube",         "link_open",     {"url": "https://youtube.com"}, True),
        ("play next song",       "music",         {"action": "next"},         True),
        ("take screenshot",      "screenshot",    {},                         True),
        ("open chrome",          "open_app",      {"app_name": "chrome"},    True),
        ("open downloads folder","open_folder",   {"name": "downloads"},      False),
    ]

    for user_text, fn, args, ok in test_commands:
        think_t = random.uniform(180, 600)
        exec_t  = random.uniform(50, 400)
        log_command(session, user_text, fn, args, think_t, exec_t, ok,
                    error_msg="" if ok else "Simulated error")
        print(f"  ✓ logged: {fn}")

    print_session_summary(session)
    print_all_time_report()
    end_session(session)