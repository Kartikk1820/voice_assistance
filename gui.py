"""
VoiceAssistantGUI  —  gui.py
═════════════════════════════
Wake word mode (new):
  App starts → detector listens silently in background
  "Hey Jarvis" / "Hello Jarvis" → GUI activates, records command, executes

Manual mode (still works):
  Hold SPACE → record → release → execute

Analytics:
  Every command is timed and logged via analytics module.
  Session summary printed to terminal on close.
"""

import os
import sys
import json
import queue
import threading
import importlib
import tkinter as tk
import math
import time

import sounddevice as sd
from vosk import Model, KaldiRecognizer

from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

import extensions.essentials.mouth    as mouth
import extensions.essentials.brain    as brain
import extensions.essentials.ears     as ears
from   extensions.essentials.analytics import analytics
import extensions.actions.register    as rg

function_register = rg.import_all_from_current_directory()

# ── Vosk model ────────────────────────────────────────────────────────────────

MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "model")
try:
    _vosk_model = Model(MODEL_PATH)
except Exception:
    print(f"ERROR: Could not load Vosk model at '{MODEL_PATH}'.")
    print("Download from https://alphacephei.com/vosk/models")
    sys.exit(1)

SAMPLE_RATE = 16_000
BLOCK_SIZE  = 1_600


# ── helpers ───────────────────────────────────────────────────────────────────

def extract_function_descriptions(actions_dir: str = "extensions/actions") -> str:
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


# ── GUI ───────────────────────────────────────────────────────────────────────

class VoiceAssistantGUI:

    # ── palette ───────────────────────────────────────────────────────────────
    BG          = "#0a0a0f"
    IDLE_MIC    = "#1e1e2e"
    IDLE_RIM    = "#2a2a3d"
    WAKE_MIC    = "#0d1f0d"        # dark green — waiting for wake word
    WAKE_RIM    = "#00cc44"        # green ring
    LISTEN_MIC  = "#0d2137"
    LISTEN_RIM  = "#00aaff"
    THINK_MIC   = "#1a0d2e"
    THINK_RIM   = "#9b5de5"
    EXEC_MIC    = "#1a1200"
    EXEC_RIM    = "#f5a623"
    TEXT_DIM    = "#4a4a6a"
    TEXT_MID    = "#8888aa"
    ACCENT      = "#00aaff"
    SUCCESS     = "#00e5a0"
    ERROR       = "#ff4466"
    WAKE_ACCENT = "#00cc44"

    SIZE   = 580
    MIC_R  = 90
    RING_R = 130

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Jarvis — Voice Assistant")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)
        self.root.geometry(f"{self.SIZE}x{self.SIZE}")
        self.root.attributes("-topmost", True)

        self.all_tools  = extract_function_descriptions()
        self.session_id = analytics.start_session()

        # state machine:  wake_standby | idle | listening | thinking | executing
        self.state = "wake_standby"

        # recording state (manual SPACE mode)
        self._recording     = False
        self._audio_q       : queue.Queue = queue.Queue()
        self._audio_stream  = None
        self._listen_thread = None
        self._key_debounce  = None

        # pipeline interrupt
        self._interrupt = threading.Event()

        # main-thread message queue
        self._msg_q : queue.Queue = queue.Queue()

        # spinner angle
        self._spin_angle = 0.0

        # wake word detector reference
        self._detector = None

        self._build_ui()
        self._bind_keys()
        self._start_wake_detector()
        self._tick()

    # ── wake word integration ─────────────────────────────────────────────────

    def _start_wake_detector(self):
        """Start the always-on wake word detector."""
        self._detector = ears.start_wake_word_detection(self._on_wake_word)
        self._set_state("wake_standby")

    def _on_wake_word(self, wake_word: str):
        """
        Called from the WakeWordDetector background thread.
        Post a message to the main thread via _msg_q — never touch Tk directly
        from a background thread.
        """
        self._msg_q.put(("wake_word_heard", wake_word))
        # Block the detector thread here until command pipeline finishes
        self._wake_done_event = threading.Event()
        self._wake_done_event.wait()   # released by _finish_wake_pipeline()

    def _finish_wake_pipeline(self):
        """Resume the wake detector after command finishes."""
        if self._detector:
            self._detector.resume()
        if hasattr(self, "_wake_done_event"):
            self._wake_done_event.set()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        W  = self.SIZE
        cx = W // 2
        cy = W // 2 - 30

        self.canvas = tk.Canvas(self.root, width=W, height=W,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack()

        for r in (160, 192, 224):
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                    outline=self.IDLE_RIM, width=1)

        self._ring = self.canvas.create_oval(
            cx-self.RING_R, cy-self.RING_R,
            cx+self.RING_R, cy+self.RING_R,
            outline=self.IDLE_RIM, width=2)

        sr_ = self.RING_R + 5
        self._spinner = self.canvas.create_arc(
            cx-sr_, cy-sr_, cx+sr_, cy+sr_,
            start=0, extent=80,
            outline=self.EXEC_RIM, width=4,
            style="arc", state="hidden")

        self._mic_body = self.canvas.create_oval(
            cx-self.MIC_R, cy-self.MIC_R,
            cx+self.MIC_R, cy+self.MIC_R,
            fill=self.IDLE_MIC, outline=self.IDLE_RIM, width=2)

        self._draw_mic_icon(cx, cy)

        # wake word indicator dot (top-right of circle)
        dot_x = cx + self.MIC_R - 12
        dot_y = cy - self.MIC_R + 12
        self._wake_dot = self.canvas.create_oval(
            dot_x-8, dot_y-8, dot_x+8, dot_y+8,
            fill=self.WAKE_ACCENT, outline="", state="normal")
        self._wake_dot_label = self.canvas.create_text(
            dot_x, dot_y - 20,
            text="WAKE", fill=self.WAKE_ACCENT,
            font=("Courier", 7, "bold"), anchor="center")

        self._fn_label = self.canvas.create_text(
            cx, cy, text="",
            fill=self.EXEC_RIM,
            font=("Courier", 10, "bold"),
            anchor="center",
            width=self.MIC_R * 2 - 12,
            justify="center",
            state="hidden")

        self._status = self.canvas.create_text(
            cx, cy + self.MIC_R + 28,
            text='SAY "HEY JARVIS" TO ACTIVATE',
            fill=self.WAKE_ACCENT,
            font=("Courier", 11, "bold"),
            anchor="center")

        pad    = 10
        box_y1 = cy + self.MIC_R + 50
        box_y2 = cy + self.MIC_R + 110
        self._trans_box = self.canvas.create_rectangle(
            cx - (W//2 - 30), box_y1,
            cx + (W//2 - 30), box_y2,
            fill="#0d0d18", outline=self.IDLE_RIM, width=1)

        self._transcript = self.canvas.create_text(
            cx, (box_y1 + box_y2) // 2,
            text="",
            fill=self.TEXT_MID,
            font=("Courier", 11),
            anchor="center",
            width=W - 80,
            justify="center")

        self.canvas.create_text(
            cx, W - 14,
            text='say "hey jarvis" to activate  •  or hold SPACE  •  say "goodbye" to exit',
            fill=self.TEXT_DIM,
            font=("Courier", 7),
            anchor="center")

        self._cx, self._cy = cx, cy
        self._box_y1 = box_y1
        self._box_y2 = box_y2

    def _draw_mic_icon(self, cx, cy):
        mw, mh = 20, 34
        self._mic_rect  = self.canvas.create_rectangle(
            cx-mw, cy-mh, cx+mw, cy+mh, fill=self.TEXT_DIM, outline="")
        self._mic_oval  = self.canvas.create_oval(
            cx-mw, cy-mh-mw, cx+mw, cy-mh+mw, fill=self.TEXT_DIM, outline="")
        self._mic_stem  = self.canvas.create_line(
            cx, cy+mh+10, cx, cy+mh+22, fill=self.TEXT_DIM, width=3)
        self._mic_foot  = self.canvas.create_line(
            cx-16, cy+mh+22, cx+16, cy+mh+22, fill=self.TEXT_DIM, width=3)
        self._mic_parts = [self._mic_rect, self._mic_oval,
                           self._mic_stem, self._mic_foot]

    # ── key bindings ──────────────────────────────────────────────────────────

    def _bind_keys(self):
        self.root.bind("<KeyPress-space>",   self._on_press)
        self.root.bind("<KeyRelease-space>", self._on_release)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_press(self, event=None):
        if self._key_debounce:
            self.root.after_cancel(self._key_debounce)
            self._key_debounce = None
        if self._recording:
            return
        # Pause wake detector when user manually holds SPACE
        if self._detector:
            self._detector.pause()
        self._interrupt.set()
        self._msg_q.put(("interrupted", ""))
        self._start_recording()

    def _on_release(self, event=None):
        if self._key_debounce:
            self.root.after_cancel(self._key_debounce)
        self._key_debounce = self.root.after(50, self._confirmed_release)

    def _confirmed_release(self):
        self._key_debounce = None
        if self._recording:
            self._stop_recording_and_run()

    def _on_close(self):
        self._interrupt.set()
        self._stop_audio_stream()
        if self._detector:
            self._detector.stop()
        mouth.save_memo_to_disk()
        brain.clear_memory()
        analytics.end_session(self.session_id)
        analytics.print_session_summary(self.session_id)
        self.root.destroy()

    # ── recording (SPACE mode) ────────────────────────────────────────────────

    def _start_recording(self):
        self._recording = True
        while not self._audio_q.empty():
            try: self._audio_q.get_nowait()
            except queue.Empty: break

        self._set_state("listening")

        self._audio_stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
            dtype="int16", channels=1,
            callback=self._audio_callback)
        self._audio_stream.start()

        self._listen_thread = threading.Thread(
            target=self._vosk_loop, daemon=True)
        self._listen_thread.start()

    def _stop_audio_stream(self):
        if self._audio_stream:
            try:
                self._audio_stream.stop()
                self._audio_stream.close()
            except Exception:
                pass
            self._audio_stream = None

    def _stop_recording_and_run(self):
        self._recording = False
        self._stop_audio_stream()

    def _audio_callback(self, indata, frames, time_info, status):
        if status and DEBUG:
            print("sd status:", status)
        self._audio_q.put(bytes(indata))

    # ── Vosk loop (SPACE mode) ────────────────────────────────────────────────

    def _vosk_loop(self):
        rec       = KaldiRecognizer(_vosk_model, SAMPLE_RATE)
        confirmed = ""

        while self._recording:
            try:
                data = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                continue

            if rec.AcceptWaveform(data):
                chunk = json.loads(rec.Result()).get("text", "").strip()
                if chunk:
                    confirmed += (" " if confirmed else "") + chunk
                    self._msg_q.put(("transcript_live", confirmed))
            else:
                partial = json.loads(rec.PartialResult()).get("partial", "").strip()
                live = (confirmed + (" " if confirmed else "") + partial).strip()
                if live:
                    self._msg_q.put(("transcript_live", live))

        while True:
            try:
                data = self._audio_q.get_nowait()
                rec.AcceptWaveform(data)
            except queue.Empty:
                break

        last = json.loads(rec.FinalResult()).get("text", "").strip()
        if last:
            confirmed += (" " if confirmed else "") + last
        final_text = confirmed.strip()

        if not final_text:
            self._msg_q.put(("no_speech", ""))
            return

        self._msg_q.put(("heard", final_text))
        self._run_pipeline(final_text, from_wake=False)

    # ── pipeline ──────────────────────────────────────────────────────────────

    def _run_pipeline(self, text: str, from_wake: bool = False):
        """
        Think → execute. Runs in a background thread.
        from_wake=True: resumes wake detector + unblocks detector thread when done.
        from_wake=False (SPACE): resumes wake detector when done.
        """
        self._interrupt.clear()

        if "good" in text.lower() and "bye" in text.lower():
            self._msg_q.put(("goodbye", text))
            return

        # ── think ──
        self._msg_q.put(("thinking", ""))
        t_think = time.perf_counter()
        try:
            thoughts = brain.think(text, self.all_tools)
            if DEBUG:
                print(f"[gui] Brain: {thoughts}")
        except Exception as e:
            self._msg_q.put(("error", str(e)))
            if from_wake:
                self._finish_wake_pipeline()
            return
        think_ms = (time.perf_counter() - t_think) * 1000

        if self._interrupt.is_set():
            if from_wake:
                self._finish_wake_pipeline()
            return

        fn   = thoughts.get("function_name", "error")
        args = thoughts.get("args", {})

        if fn == "error":
            self._msg_q.put(("error", args.get("message", "Unknown error")))
            analytics.log_command(self.session_id, text, fn, args, think_ms, 0, False,
                                  error_msg=args.get("message", ""))
            if from_wake:
                self._finish_wake_pipeline()
            return

        # ── execute ──
        self._msg_q.put(("executing", fn))
        try:
            with analytics.track(self.session_id, text, fn, args, think_ms=think_ms):
                call_function_by_name(fn, args)
        except Exception as e:
            self._msg_q.put(("error", str(e)))
            if from_wake:
                self._finish_wake_pipeline()
            return

        if self._interrupt.is_set():
            if from_wake:
                self._finish_wake_pipeline()
            return

        self._msg_q.put(("done", fn))

        # Resume wake detector in both modes
        if from_wake:
            self._msg_q.put(("resume_wake", ""))
        else:
            # Manual SPACE mode: resume wake detector after executing
            if self._detector:
                self._detector.resume()

    # ── tick (animation + message drain) ──────────────────────────────────────

    def _tick(self):
        try:
            while True:
                self._handle(*self._msg_q.get_nowait())
        except queue.Empty:
            pass
        self._animate()
        self.root.after(30, self._tick)

    def _handle(self, msg, data):
        if msg == "wake_word_heard":
            # Wake word triggered — switch to listening via Google STT
            self._set_state("listening")
            self._update(self._status, f"🔔  '{data.upper()}' — LISTENING…", self.WAKE_ACCENT)
            self._set_transcript("", self.TEXT_MID)
            # Run Google STT + pipeline in background thread
            threading.Thread(
                target=self._wake_pipeline_thread,
                args=(data,), daemon=True
            ).start()

        elif msg == "transcript_live":
            self._set_transcript(data, self.LISTEN_RIM)

        elif msg == "heard":
            self._set_transcript(data, self.TEXT_MID)

        elif msg == "thinking":
            self._set_state("thinking")

        elif msg == "executing":
            self._set_state("executing", fn_name=data)

        elif msg == "done":
            self._update(self._status, f"✓  {data}", self.SUCCESS)
            self._set_transcript("", self.TEXT_MID)
            self.root.after(1800, self._return_wake_standby)

        elif msg == "error":
            self._update(self._status, "ERROR", self.ERROR)
            self._set_transcript(data, self.ERROR)
            self.root.after(2500, self._return_wake_standby)

        elif msg == "no_speech":
            self._set_transcript("(no speech detected)", self.TEXT_DIM)
            self.root.after(1200, self._return_wake_standby)

        elif msg == "interrupted":
            self._set_transcript("", self.TEXT_MID)

        elif msg == "resume_wake":
            self._finish_wake_pipeline()
            self._return_wake_standby()

        elif msg == "goodbye":
            self._update(self._status, "GOODBYE!", self.ACCENT)
            mouth.say("Goodbye! Have a great day.")
            mouth.save_memo_to_disk()
            brain.clear_memory()
            analytics.end_session(self.session_id)
            analytics.print_session_summary(self.session_id)
            self.root.after(1000, self.root.destroy)

    def _wake_pipeline_thread(self, wake_word: str):
        """
        Runs in background thread after wake word fires.
        Uses Google STT (high accuracy) for the command.
        """
        mouth.say("Yes?")
        command = ears.listen()
        if DEBUG:
            print(f"[gui] Wake command: {command!r}")

        if not command:
            self._msg_q.put(("no_speech", ""))
            self._finish_wake_pipeline()
            return

        self._msg_q.put(("heard", command))
        self._run_pipeline(command, from_wake=True)

    # ── state ─────────────────────────────────────────────────────────────────

    def _set_state(self, state: str, fn_name: str = ""):
        self.state = state

        spin_vis = "normal" if state == "executing"                else "hidden"
        self.canvas.itemconfig(self._spinner, state=spin_vis)

        mic_vis  = "hidden" if state == "executing"                else "normal"
        for p in self._mic_parts:
            self.canvas.itemconfig(p, state=mic_vis)

        fn_vis   = "normal" if state == "executing"                else "hidden"
        self.canvas.itemconfig(self._fn_label, state=fn_vis)
        if fn_name:
            self.canvas.itemconfig(self._fn_label,
                                   text=fn_name.replace("_", " ").upper())

        # Wake dot: visible in wake_standby only
        dot_vis = "normal" if state == "wake_standby" else "hidden"
        self.canvas.itemconfig(self._wake_dot,       state=dot_vis)
        self.canvas.itemconfig(self._wake_dot_label, state=dot_vis)

        if state == "wake_standby":
            self.canvas.itemconfig(self._mic_body,
                                   fill=self.WAKE_MIC, outline=self.WAKE_RIM)
            self.canvas.itemconfig(self._ring, outline=self.WAKE_RIM)
            self.canvas.itemconfig(self._trans_box, outline=self.WAKE_RIM)
            self._recolor_mic(self.WAKE_RIM)
            self._update(self._status, 'SAY "HEY JARVIS" TO ACTIVATE', self.WAKE_ACCENT)

        elif state == "idle":
            self.canvas.itemconfig(self._mic_body,
                                   fill=self.IDLE_MIC, outline=self.IDLE_RIM)
            self.canvas.itemconfig(self._ring, outline=self.IDLE_RIM)
            self.canvas.itemconfig(self._trans_box, outline=self.IDLE_RIM)
            self._recolor_mic(self.TEXT_DIM)
            self._update(self._status, "HOLD SPACE TO SPEAK", self.TEXT_DIM)

        elif state == "listening":
            self.canvas.itemconfig(self._mic_body,
                                   fill=self.LISTEN_MIC, outline=self.LISTEN_RIM)
            self.canvas.itemconfig(self._trans_box, outline=self.LISTEN_RIM)
            self._recolor_mic(self.LISTEN_RIM)
            self._update(self._status, "● LISTENING…", self.ACCENT)

        elif state == "thinking":
            self.canvas.itemconfig(self._mic_body,
                                   fill=self.THINK_MIC, outline=self.THINK_RIM)
            self.canvas.itemconfig(self._trans_box, outline=self.THINK_RIM)
            self._recolor_mic(self.THINK_RIM)
            self._update(self._status, "⟳ THINKING…", "#9b5de5")

        elif state == "executing":
            self.canvas.itemconfig(self._mic_body,
                                   fill=self.EXEC_MIC, outline=self.EXEC_RIM)
            self.canvas.itemconfig(self._trans_box, outline=self.EXEC_RIM)
            self._update(self._status, "⚙  EXECUTING", self.EXEC_RIM)
            self._spin_angle = 0.0

    def _return_wake_standby(self):
        self._set_state("wake_standby")
        self._set_transcript("", self.TEXT_MID)

    def _recolor_mic(self, color):
        for p in self._mic_parts:
            self.canvas.itemconfig(p, fill=color)

    def _update(self, item, text, color):
        self.canvas.itemconfig(item, text=text, fill=color)

    def _set_transcript(self, text, color):
        self.canvas.itemconfig(self._transcript, text=text, fill=color)

    # ── animation ─────────────────────────────────────────────────────────────

    def _animate(self):
        cx, cy = self._cx, self._cy
        t = time.time()

        if self.state == "wake_standby":
            # slow gentle pulse — green, calm
            pulse = 0.5 + 0.5 * math.sin(t * 1.2)
            r = self.RING_R + 6 * pulse
            self.canvas.coords(self._ring, cx-r, cy-r, cx+r, cy+r)
            self.canvas.itemconfig(self._ring, outline=self.WAKE_RIM,
                                   width=1 + pulse)

        elif self.state == "listening":
            pulse = 0.5 + 0.5 * math.sin(t * 6)
            r = self.RING_R + 18 * pulse
            self.canvas.coords(self._ring, cx-r, cy-r, cx+r, cy+r)
            self.canvas.itemconfig(self._ring, outline=self.LISTEN_RIM,
                                   width=2 + pulse * 2)

        elif self.state == "thinking":
            pulse = 0.5 + 0.5 * math.sin(t * 4)
            r = self.RING_R + 8 * pulse
            self.canvas.coords(self._ring, cx-r, cy-r, cx+r, cy+r)
            self.canvas.itemconfig(self._ring, outline=self.THINK_RIM, width=2)

        elif self.state == "executing":
            r = self.RING_R
            self.canvas.coords(self._ring, cx-r, cy-r, cx+r, cy+r)
            self.canvas.itemconfig(self._ring, outline=self.EXEC_RIM, width=1)
            self._spin_angle = (self._spin_angle + 8) % 360
            sr_ = self.RING_R + 5
            self.canvas.coords(self._spinner, cx-sr_, cy-sr_, cx+sr_, cy+sr_)
            self.canvas.itemconfig(self._spinner, start=self._spin_angle)

        else:  # idle
            pulse = 0.5 + 0.5 * math.sin(t * 1.5)
            r = self.RING_R + 4 * pulse
            self.canvas.coords(self._ring, cx-r, cy-r, cx+r, cy+r)
            self.canvas.itemconfig(self._ring, outline=self.IDLE_RIM, width=1)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app  = VoiceAssistantGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()