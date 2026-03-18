"""
main.py  —  Terminal entry point
"""

import os
import sys
import time
import threading

from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

import extensions.essentials.ears   as ears
import extensions.essentials.mouth  as mouth
import extensions.essentials.brain  as brain
import extensions.essentials.analytics as analytics

import extensions.actions.register as rg
function_register = rg.import_all_from_current_directory()

# How many seconds of silence before Jarvis goes back to sleep
ACTIVE_WINDOW_SEC = int(os.getenv("ACTIVE_WINDOW_SEC", "60"))

# ── helpers ───────────────────────────────────────────────────────────────────

def extract_function_descriptions() -> str:
    definitions = []
    for name, func in function_register.items():
        module = sys.modules.get(func.__module__)
        if module and hasattr(module, "defination"):
            definitions.append(module.defination.strip())
    return "\n\n".join(definitions)

def call_function_by_name(function_name: str, args: dict):
    func = function_register.get(function_name)
    if func:
        return func(**args)
    raise ValueError(f"Function '{function_name}' not found.")

# ── listen with custom silence timeout ───────────────────────────────────────

def _listen_with_timeout(timeout_sec: int) -> str | None:
    import speech_recognition as sr
    r = ears._sr_recognizer
    with sr.Microphone() as source:
        ears._ensure_calibrated(source)
        try:
            audio = r.listen(source, timeout=timeout_sec, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            return None
    try:
        return r.recognize_google(audio)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"[ears] STT error: {e}")
        return None

# ── single command pipeline ───────────────────────────────────────────────────

def run_command(text: str, session_id: str, all_tools: str) -> str:
    """Returns: 'goodbye' | 'ok' | 'error'"""
    if "good" in text.lower() and "bye" in text.lower():
        mouth.say("Goodbye! Have a great day.")
        return "goodbye"

    t_start = time.perf_counter()
    try:
        thoughts = brain.think(text, all_tools)
        if DEBUG:
            print(f"[main] Brain: {thoughts}")
    except Exception as e:
        mouth.say("Sorry, I had trouble understanding that.")
        return "error"
    think_ms = (time.perf_counter() - t_start) * 1000

    fn   = thoughts.get("function_name", "error")
    args = thoughts.get("args", {})

    if fn == "error":
        mouth.say("Sorry, I could not figure out what to do.")
        analytics.log_command(session_id, text, fn, args, think_ms, 0, False,
                              error_msg=args.get("message", ""))
        return "error"

    try:
        with analytics.track(session_id, text, fn, args, think_ms=think_ms):
            call_function_by_name(fn, args)
    except Exception as e:
        print(f"[main] Execution error: {e}")
        mouth.say("Something went wrong.")

    return "ok"

# ── active listening loop ─────────────────────────────────────────────────────

def active_listening_loop(session_id: str, all_tools: str, should_exit: threading.Event):
    """
    Runs in its OWN thread (not the Porcupine detector thread).
    Keeps listening until ACTIVE_WINDOW_SEC silence or goodbye.
    """
    print(f"\n[Jarvis] Active — {ACTIVE_WINDOW_SEC}s silence → sleep\n")

    while True:
        print(f"[Jarvis] Listening...")
        command = _listen_with_timeout(ACTIVE_WINDOW_SEC)

        if command is None:
            print(f"\n[Jarvis] Silence — going to sleep.")
            mouth.say("Going to sleep. Say Hey Jarvis to wake me.")
            # Resume the detector — it was paused when wake word fired
            detector = ears.get_detector()
            if detector:
                detector.resume()
            print(f"\n[Jarvis] Sleeping... say 'Hey Jarvis' to wake me.\n")
            return

        print(f"[Jarvis] Heard: {command!r}")
        result = run_command(command, session_id, all_tools)

        if result == "goodbye":
            should_exit.set()
            return

        # "ok" or "error" → loop back immediately, listen for next command

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════╗")
    print("║        JARVIS  —  Voice Assistant        ║")
    print(f"║   Active window: {ACTIVE_WINDOW_SEC}s silence → sleep   ║")
    print("╚══════════════════════════════════════════╝")

    session_id  = analytics.start_session()
    all_tools   = extract_function_descriptions()
    should_exit = threading.Event()

    def on_wake(wake_word: str):
        """
        Called from Porcupine detector thread.
        MUST return quickly — never block this thread.
        We immediately spawn a new thread for the active listening loop.
        """
        print(f"\n[Jarvis] Wake word: '{wake_word}'")
        mouth.say("Yes?")

        # Spawn separate thread so Porcupine's thread is freed immediately
        t = threading.Thread(
            target=active_listening_loop,
            args=(session_id, all_tools, should_exit),
            daemon=True,
            name="ActiveListeningThread"
        )
        t.start()
        # on_wake returns instantly — Porcupine is happy, no buffer overflow

    ears.start_wake_word_detection(on_wake)

    print(f"\nSay 'Hey Jarvis' to activate.")
    print(f"Keep talking — stays active for {ACTIVE_WINDOW_SEC}s of silence.")
    print("Say 'Goodbye' to exit.\n")

    try:
        while not should_exit.is_set():
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n[main] Interrupted.")

    detector = ears.get_detector()
    if detector:
        detector.stop()
    mouth.save_memo_to_disk()
    brain.clear_memory()
    analytics.end_session(session_id)
    analytics.print_session_summary(session_id)
    print("Goodbye!")

if __name__ == "__main__":
    main()