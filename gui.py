"""
Voice Assistant GUI
───────────────────
Hold SPACE  → mic opens, Vosk streams words live to screen
Release SPACE → finalises transcript, runs brain → executes action
Hold SPACE again at any point → cancels current pipeline, starts fresh
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

import extensions.essentials.mouth as mouth
import extensions.essentials.brain as brain
import extensions.actions.register as rg

function_register = rg.import_all_from_current_directory()


# ── Vosk model (loaded once at startup) ──────────────────────────────────────

MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "model")
try:
    _vosk_model = Model(MODEL_PATH)
except Exception:
    print(f"ERROR: Could not load Vosk model at '{MODEL_PATH}'.")
    print("Download a model from https://alphacephei.com/vosk/models and point")
    print("VOSK_MODEL_PATH at the extracted folder (or name it 'model').")
    sys.exit(1)

SAMPLE_RATE = 16000
BLOCK_SIZE  = 1600          # ~0.1 s chunks


# ── helpers ───────────────────────────────────────────────────────────────────

def extract_function_descriptions(actions_dir: str = "extensions/actions") -> str:
    definitions = []
    for filename in os.listdir(actions_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            filepath = os.path.join(actions_dir, filename)
            spec = importlib.util.spec_from_file_location(filename[:-3], filepath)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                if hasattr(module, "defination"):
                    definitions.append(module.defination.strip())
            except Exception as e:
                print(f"Warning: Could not load {filename}: {e}")
    return "\n\n".join(definitions)


def call_function_by_name(function_name: str, args: dict):
    func = function_register.get(function_name)
    if func:
        return func(**args)
    raise ValueError(f"Function '{function_name}' not found.")


# ── GUI ───────────────────────────────────────────────────────────────────────

class VoiceAssistantGUI:

    # palette
    BG         = "#0a0a0f"
    IDLE_MIC   = "#1e1e2e"
    IDLE_RIM   = "#2a2a3d"
    LISTEN_MIC = "#0d2137"
    LISTEN_RIM = "#00aaff"
    THINK_MIC  = "#1a0d2e"
    THINK_RIM  = "#9b5de5"
    EXEC_MIC   = "#1a1200"
    EXEC_RIM   = "#f5a623"
    TEXT_DIM   = "#4a4a6a"
    TEXT_MID   = "#8888aa"
    ACCENT     = "#00aaff"
    SUCCESS    = "#00e5a0"
    ERROR      = "#ff4466"

    SIZE   = 580
    MIC_R  = 90
    RING_R = 130

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Voice Assistant")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)
        self.root.geometry(f"{self.SIZE}x{self.SIZE}")

        self.all_tools = extract_function_descriptions()

        # Pin the window to the top of the screen!
        self.root.attributes("-topmost", True)
        
        # ── state machine ──
        # idle | listening | thinking | executing
        self.state = "idle"

        # ── recording state ──
        self._recording       = False
        self._audio_q         = queue.Queue()
        self._audio_stream    = None
        self._listen_thread   = None
        self._key_debounce    = None   # after() id for release debounce

        # ── pipeline interrupt ──
        self._interrupt = threading.Event()

        # ── main-thread message queue ──
        self._msg_q = queue.Queue()

        # ── spinner angle ──
        self._spin_angle = 0.0

        self._build_ui()
        self._bind_keys()
        self._tick()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        W  = self.SIZE
        cx = W // 2
        cy = W // 2 - 30   # raised: transcript lives below

        self.canvas = tk.Canvas(self.root, width=W, height=W,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack()

        # static deco rings
        for r in (160, 192, 224):
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                    outline=self.IDLE_RIM, width=1)

        # animated ring
        self._ring = self.canvas.create_oval(
            cx-self.RING_R, cy-self.RING_R,
            cx+self.RING_R, cy+self.RING_R,
            outline=self.IDLE_RIM, width=2)

        # spinner arc (executing state)
        sr = self.RING_R + 5
        self._spinner = self.canvas.create_arc(
            cx-sr, cy-sr, cx+sr, cy+sr,
            start=0, extent=80,
            outline=self.EXEC_RIM, width=4,
            style="arc", state="hidden")

        # mic body
        self._mic_body = self.canvas.create_oval(
            cx-self.MIC_R, cy-self.MIC_R,
            cx+self.MIC_R, cy+self.MIC_R,
            fill=self.IDLE_MIC, outline=self.IDLE_RIM, width=2)

        self._draw_mic_icon(cx, cy)

        # fn name label (shown inside circle during execute)
        self._fn_label = self.canvas.create_text(
            cx, cy, text="",
            fill=self.EXEC_RIM,
            font=("Courier", 10, "bold"),
            anchor="center",
            width=self.MIC_R * 2 - 12,
            justify="center",
            state="hidden")

        # status
        self._status = self.canvas.create_text(
            cx, cy + self.MIC_R + 28,
            text="HOLD SPACE TO SPEAK",
            fill=self.TEXT_DIM,
            font=("Courier", 11, "bold"),
            anchor="center")

        # live transcript box — dark pill behind the text
        pad = 10
        box_y1 = cy + self.MIC_R + 50
        box_y2 = cy + self.MIC_R + 110
        self._trans_box = self.canvas.create_rectangle(
            cx - (W//2 - 30), box_y1,
            cx + (W//2 - 30), box_y2,
            fill="#0d0d18", outline=self.IDLE_RIM, width=1)

        # transcript text inside the box
        self._transcript = self.canvas.create_text(
            cx, (box_y1 + box_y2) // 2,
            text="",
            fill=self.TEXT_MID,
            font=("Courier", 11),
            anchor="center",
            width=W - 80,
            justify="center")

        # bottom hint
        self.canvas.create_text(
            cx, W - 14,
            text='hold SPACE to speak  •  release to send  •  say "goodbye" to exit',
            fill=self.TEXT_DIM,
            font=("Courier", 7),
            anchor="center")

        self._cx, self._cy = cx, cy
        self._box_y1 = box_y1
        self._box_y2 = box_y2

    def _draw_mic_icon(self, cx, cy):
        mw, mh = 20, 34
        self._mic_rect = self.canvas.create_rectangle(
            cx-mw, cy-mh, cx+mw, cy+mh, fill=self.TEXT_DIM, outline="")
        self._mic_oval = self.canvas.create_oval(
            cx-mw, cy-mh-mw, cx+mw, cy-mh+mw, fill=self.TEXT_DIM, outline="")
        self._mic_stem = self.canvas.create_line(
            cx, cy+mh+10, cx, cy+mh+22, fill=self.TEXT_DIM, width=3)
        self._mic_foot = self.canvas.create_line(
            cx-16, cy+mh+22, cx+16, cy+mh+22, fill=self.TEXT_DIM, width=3)
        self._mic_parts = [self._mic_rect, self._mic_oval,
                           self._mic_stem, self._mic_foot]

    # ── key bindings ──────────────────────────────────────────────────────────

    def _bind_keys(self):
        self.root.bind("<KeyPress-space>",   self._on_press)
        self.root.bind("<KeyRelease-space>", self._on_release)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_press(self, event=None):
        # Cancel any pending release debounce (OS key-repeat fires press+release rapidly)
        if self._key_debounce:
            self.root.after_cancel(self._key_debounce)
            self._key_debounce = None

        if self._recording:
            return  # already recording, ignore OS repeat

        # Interrupt any running pipeline before starting fresh
        self._interrupt.set()
        self._msg_q.put(("interrupted", ""))

        # Start recording immediately
        self._start_recording()

    def _on_release(self, event=None):
        # Debounce: wait 50 ms to confirm this isn't OS key-repeat
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
        mouth.save_memo_to_disk()
        self.root.destroy()

    # ── recording ─────────────────────────────────────────────────────────────

    def _start_recording(self):
        self._recording = True
        # flush stale audio
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

        self._set_state("listening")

        # open sounddevice stream
        self._audio_stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=1,
            callback=self._audio_callback)
        self._audio_stream.start()

        # Vosk transcription thread
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
        """Close mic, collect final transcript, then hand off to pipeline."""
        self._recording = False
        self._stop_audio_stream()
        # pipeline thread picks up the final text via _vosk_loop finishing

    def _audio_callback(self, indata, frames, time_info, status):
        if status and DEBUG:
            print("sd status:", status)
        self._audio_q.put(bytes(indata))

    # ── Vosk loop (runs in background thread while recording) ─────────────────

    def _vosk_loop(self):
        """
        Reads audio from _audio_q, streams partial results to the transcript box,
        then — once recording stops — finalises and hands the text to the pipeline.
        """
        rec = KaldiRecognizer(_vosk_model, SAMPLE_RATE)
        confirmed = ""   # text from completed phrase chunks
        final_text = ""

        while self._recording:
            try:
                data = self._audio_q.get(timeout=0.1)
            except queue.Empty:
                continue

            if rec.AcceptWaveform(data):
                # phrase boundary detected
                result = json.loads(rec.Result())
                chunk = result.get("text", "").strip()
                if chunk:
                    confirmed += (" " if confirmed else "") + chunk
                    self._msg_q.put(("transcript_live", confirmed))
            else:
                partial = json.loads(rec.PartialResult()).get("partial", "").strip()
                live = (confirmed + (" " if confirmed else "") + partial).strip()
                if live:
                    self._msg_q.put(("transcript_live", live))

        # drain whatever's left after stream closed
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
        self._run_pipeline(final_text)

    # ── pipeline ──────────────────────────────────────────────────────────────

    def _run_pipeline(self, text: str):
        """Think → execute. Checks _interrupt between stages."""
        self._interrupt.clear()

        # goodbye shortcut
        if "good" in text.lower() and "bye" in text.lower():
            self._msg_q.put(("goodbye", text))
            return

        # think
        self._msg_q.put(("thinking", ""))
        try:
            thoughts = brain.think(text, self.all_tools)
            if DEBUG:
                print(f"Brain: {thoughts}")
        except Exception as e:
            self._msg_q.put(("error", str(e)))
            return

        if self._interrupt.is_set():
            return

        # execute
        fn = thoughts["function_name"]
        self._msg_q.put(("executing", fn))
        try:
            call_function_by_name(fn, thoughts["args"])
        except Exception as e:
            self._msg_q.put(("error", str(e)))
            return

        if self._interrupt.is_set():
            return

        self._msg_q.put(("done", fn))

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
        if msg == "transcript_live":
            self._set_transcript(data, self.LISTEN_RIM)

        elif msg == "heard":
            # transcript stays on screen while thinking
            self._set_transcript(data, self.TEXT_MID)

        elif msg == "thinking":
            self._set_state("thinking")

        elif msg == "executing":
            self._set_state("executing", fn_name=data)

        elif msg == "done":
            self._update(self._status, f"✓  {data}", self.SUCCESS)
            self._set_transcript("", self.TEXT_MID)
            self.root.after(1800, self._return_idle)

        elif msg == "error":
            self._update(self._status, "ERROR", self.ERROR)
            self._set_transcript(data, self.ERROR)
            self.root.after(2500, self._return_idle)

        elif msg == "no_speech":
            self._set_transcript("(no speech detected)", self.TEXT_DIM)
            self.root.after(1200, self._return_idle)

        elif msg == "interrupted":
            # wipe transcript immediately so the new recording starts clean
            self._set_transcript("", self.TEXT_MID)
            # state will be set to listening by _start_recording right after

        elif msg == "goodbye":
            self._update(self._status, "GOODBYE!", self.ACCENT)
            mouth.say("Goodbye! Have a great day.")
            mouth.save_memo_to_disk()
            self.root.after(1000, self.root.destroy)

    # ── state ─────────────────────────────────────────────────────────────────

    def _set_state(self, state: str, fn_name: str = ""):
        self.state = state

        spin_vis = "normal" if state == "executing" else "hidden"
        self.canvas.itemconfig(self._spinner, state=spin_vis)

        mic_vis = "hidden" if state == "executing" else "normal"
        for p in self._mic_parts:
            self.canvas.itemconfig(p, state=mic_vis)

        fn_vis = "normal" if state == "executing" else "hidden"
        self.canvas.itemconfig(self._fn_label, state=fn_vis)
        if fn_name:
            self.canvas.itemconfig(self._fn_label,
                                   text=fn_name.replace("_", " ").upper())

        if state == "idle":
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

    def _return_idle(self):
        self._set_state("idle")
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

        if self.state == "listening":
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
            sr = self.RING_R + 5
            self.canvas.coords(self._spinner, cx-sr, cy-sr, cx+sr, cy+sr)
            self.canvas.itemconfig(self._spinner, start=self._spin_angle)

        else:  # idle
            pulse = 0.5 + 0.5 * math.sin(t * 1.5)
            r = self.RING_R + 4 * pulse
            self.canvas.coords(self._ring, cx-r, cy-r, cx+r, cy+r)
            self.canvas.itemconfig(self._ring, outline=self.IDLE_RIM, width=1)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app = VoiceAssistantGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()