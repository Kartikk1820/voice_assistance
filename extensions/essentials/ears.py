"""
ears.py  —  Wake Word + Command Listening
==========================================
Wake word engine : OpenWakeWord (free, offline, knows "hey jarvis" natively)
Command engine   : Google Speech Recognition (high accuracy for commands)

Install:
    pip install openwakeword pyaudio speechrecognition

No API key needed. No device limits. Works forever.
"""

import os
import sys
import time
import threading
import struct

import numpy as np
import rich
import pyaudio
import speech_recognition as sr
from dotenv import load_dotenv
load_dotenv()

DEBUG: bool = os.getenv("DEBUG") == "True"

# ── wake word config ──────────────────────────────────────────────────────────

# OpenWakeWord built-in model names — pick one:
#   "hey_jarvis"        ← best for your project
#   "alexa"
#   "hey_mycroft"
#   "timer"
WAKE_WORD_MODEL   = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")

# Detection threshold — 0.0 to 1.0
# Higher = fewer false triggers but might miss quiet speech
# Lower  = more sensitive but may false-trigger on similar sounds
# 0.5 is a good starting point
DETECTION_THRESHOLD = float(os.getenv("WAKE_THRESHOLD", "0.3"))

# Audio config — must match what OpenWakeWord expects
SAMPLE_RATE = 16_000
CHUNK_SIZE  = 1_280   # 80ms chunks — required by OpenWakeWord

# ── shared recognizer (reused across calls) ───────────────────────────────────

_sr_recognizer = sr.Recognizer()
_calibrated    = False

def _ensure_calibrated(source):
    global _calibrated
    if not _calibrated:
        rich.print("[ears] Calibrating microphone (once)...")
        _sr_recognizer.adjust_for_ambient_noise(source, duration=1)
        _calibrated = True


# ── listen() — one command via Google STT ────────────────────────────────────

def listen() -> str | None:
    """Record one voice command and return transcribed text."""
    with sr.Microphone() as source:
        _ensure_calibrated(source)
        rich.print("[ears] 🎤  Listening for command...")
        try:
            audio = _sr_recognizer.listen(source, timeout=10, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            rich.print("[ears] No speech detected.")
            return None
    try:
        text = _sr_recognizer.recognize_google(audio)
        if DEBUG:
            rich.print(f"[ears] Recognized: [bold]{text}[/bold]")
        return text
    except sr.UnknownValueError:
        rich.print("[ears] Could not understand audio.")
        return None
    except sr.RequestError as e:
        rich.print(f"[ears] Google STT error: {e}")
        return None


# ── OpenWakeWord detector ─────────────────────────────────────────────────────

class WakeWordDetector:
    """
    Always-on wake word detector using OpenWakeWord.
    Completely free, offline, no API key, no device limits.
    Natively supports "hey_jarvis" model.
    """

    def __init__(self, on_wake):
        self._on_wake     = on_wake
        self._running     = False
        self._paused      = False
        self._thread      = None
        self._pa          = None
        self._stream      = None
        self._oww         = None
        self._pause_event = threading.Event()
        self._pause_event.set()   # start unpaused
        self._score_buffer = []   # rolling window for debounce

    def start(self):
        """Start background wake word detection. Non-blocking."""
        # Try to import — give clear error if not installed
        try:
            from openwakeword.model import Model
        except ImportError:
            rich.print("[bold red][ears] OpenWakeWord not installed![/bold red]")
            rich.print("       Run: pip install openwakeword pyaudio")
            return

        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True, name="WakeWordThread")
        self._thread.start()
        rich.print(f"[ears] 👂  OpenWakeWord listening for: '[bold]{WAKE_WORD_MODEL}[/bold]' "
                   f"(threshold={DETECTION_THRESHOLD})")

    def stop(self):
        """Clean shutdown."""
        self._running = False
        self._pause_event.set()
        if self._stream:
            try: self._stream.stop_stream(); self._stream.close()
            except: pass
        if self._pa:
            try: self._pa.terminate()
            except: pass
        if self._thread:
            self._thread.join(timeout=2)

    def pause(self):
        """Pause detection while command is being processed."""
        self._paused = True
        self._pause_event.clear()
        if DEBUG:
            print("[ears] Wake word detector paused")

    def resume(self):
        """Resume after pipeline. 2s delay stops TTS re-triggering wake word."""
        def _delayed():
            time.sleep(4.0)
            if hasattr(self, '_oww') and self._oww:
                self._oww.reset()
            self._paused = False
            self._pause_event.set()
            if DEBUG:
                print("[ears] Wake word detector resumed")
        threading.Thread(target=_delayed, daemon=True).start()

    def _loop(self):
        try:
            from openwakeword.model import Model

            # Load the model — downloads automatically on first run (~5MB)
            rich.print(f"[ears] Loading OpenWakeWord model '{WAKE_WORD_MODEL}'...")
            self._oww = Model(wakeword_models=[WAKE_WORD_MODEL], inference_framework="onnx")
            rich.print(f"[ears] ✓ Model loaded")

            # Open mic stream via PyAudio
            self._pa     = pyaudio.PyAudio()
            self._stream = self._pa.open(
                rate          = SAMPLE_RATE,
                channels      = 1,
                format        = pyaudio.paInt16,
                input         = True,
                frames_per_buffer = CHUNK_SIZE,
            )

            rich.print(f"[ears] ✓ Microphone open — ready for wake word")

            while self._running:
                # Block here while paused
                self._pause_event.wait()
                if not self._running:
                    break

                # Read audio chunk
                try:
                    audio_chunk = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                except Exception as e:
                    if DEBUG:
                        print(f"[ears] Audio read error: {e}")
                    continue

                # Convert bytes → numpy int16 array (required by OpenWakeWord)
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)

                # Run inference
                prediction = self._oww.predict(audio_data)

                score = prediction.get(WAKE_WORD_MODEL, 0.0)
                if score is None:
                    score = 0.0

                # Rolling buffer — require 2 consecutive frames above threshold
                # prevents single-frame noise spikes from triggering
                self._score_buffer.append(score)
                if len(self._score_buffer) > 2:
                    self._score_buffer.pop(0)

                avg_score = sum(self._score_buffer) / len(self._score_buffer)

                if avg_score > 0.05:
                    print(f"[ears] score={avg_score:.3f} / threshold={DETECTION_THRESHOLD}", end="\r")

                if avg_score >= DETECTION_THRESHOLD and len(self._score_buffer) == 2:
                    rich.print(f"\n[ears] 🔔  Wake word! score={avg_score:.3f}")

                    self.pause()
                    self._score_buffer = []   # clear buffer
                    self._oww.reset()
                    self._on_wake(WAKE_WORD_MODEL)

        except Exception as e:
            rich.print(f"[bold red][ears] Wake word error: {e}[/bold red]")
            if DEBUG:
                import traceback; traceback.print_exc()
        finally:
            if self._stream:
                try: self._stream.stop_stream(); self._stream.close()
                except: pass
            if self._pa:
                try: self._pa.terminate()
                except: pass


# ── module-level singleton ────────────────────────────────────────────────────

_detector: WakeWordDetector | None = None

def start_wake_word_detection(on_wake) -> WakeWordDetector:
    global _detector
    _detector = WakeWordDetector(on_wake=on_wake)
    _detector.start()
    return _detector

def get_detector() -> WakeWordDetector | None:
    return _detector


# ── standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    rich.print(f"[bold cyan]ears.py — OpenWakeWord test[/bold cyan]")
    rich.print(f"Model: {WAKE_WORD_MODEL} | Threshold: {DETECTION_THRESHOLD}\n")

    def on_wake(word: str):
        rich.print(f"\n[bold green]✓ Wake word detected![/bold green]")
        rich.print("Listening for command...")
        command = listen()
        if command:
            rich.print(f"[bold]Command:[/bold] {command}")
        else:
            rich.print("No command heard.")
        if _detector:
            _detector.resume()

    det = start_wake_word_detection(on_wake)

    try:
        rich.print(f"Say 'Hey Jarvis' — press Ctrl+C to stop\n")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        det.stop()
        rich.print("\n[bold]Stopped.[/bold]")