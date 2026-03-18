import os
import asyncio
import edge_tts
import inflect
from just_playback import Playback
import time
import re
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

VOICE = "en-US-ChristopherNeural"

# TTS cache in its own folder — away from music/ so music player won't pick it up
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR       = os.path.join(BASE_DIR, "tts_cache")
CACHE_INDEX     = os.path.join(CACHE_DIR, "index.json")
os.makedirs(CACHE_DIR, exist_ok=True)

p = inflect.engine()

# Reuse a single event loop — never recreate it on every say() call
_loop = asyncio.new_event_loop()

# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if os.path.exists(CACHE_INDEX):
        with open(CACHE_INDEX, "r") as f:
            return json.load(f)
    return {}

def _save_cache(data: dict):
    with open(CACHE_INDEX, "w") as f:
        json.dump(data, f)

memo = _load_cache()

def save_memo_to_disk():
    """Call this on exit to persist cache."""
    _save_cache(memo)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _text_to_filename(text: str) -> str:
    """
    Stable filename from text hash.
    Same text → always same file → true cache hits across restarts.
    (Old code used random int → different file every restart = cache always missed)
    """
    return hashlib.md5(text.encode()).hexdigest() + ".mp3"

def _process_text(text: str) -> str:
    """Convert digits to words so TTS sounds natural."""
    words = []
    for word in text.split():
        clean_word = re.sub(r'[^\d]', '', word)
        if clean_word.isdigit():
            words.append(p.number_to_words(clean_word))
        else:
            words.append(word)
    return " ".join(words)

async def _generate_audio(text: str, output_file: str):
    communicate = edge_tts.Communicate(text, VOICE, volume="+0%", rate="+0%")
    await communicate.save(output_file)

def _play_audio(file_path: str) -> None:
    try:
        playback = Playback()
        playback.load_file(file_path)
        playback.play()
        while playback.active:
            time.sleep(0.05)   # tighter poll = more responsive finish detection
    except Exception as e:
        print(f"Error playing audio: {e}")

# ── Public API ────────────────────────────────────────────────────────────────

def say(text: str) -> None:
    pt = _process_text(text)
    if not pt:
        return

    if DEBUG:
        print(f"[say] Speaking: {pt}")

    # Stable path — same text always maps to same file
    output_file = os.path.join(CACHE_DIR, _text_to_filename(pt))

    # Cache miss OR file was deleted
    if pt not in memo or not os.path.exists(output_file):
        if DEBUG:
            print(f"[say] Cache miss — generating audio")
        try:
            # Reuse existing loop — no overhead of creating new one each call
            _loop.run_until_complete(_generate_audio(pt, output_file))
            memo[pt] = output_file
        except Exception as e:
            print(f"Error generating audio: {e}")
            return

    else:
        if DEBUG:
            print(f"[say] Cache hit")

    _play_audio(memo[pt])


if __name__ == "__main__":
    say("Hello! This is a test.")
    say("I can now speak multiple sentences without crashing.")
    say("The event loop is now managed correctly.")
    save_memo_to_disk()