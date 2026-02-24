defination = '''
function music(action: str) -> str:

arguments:
- action: The action to perform. One of: "play", "pause", "resume", "next", "prev", "stop"

Example usage:
music("play")
music("pause")
music("next")
'''

import os
import glob
import threading
import pygame
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

from pathlib import Path
MUSIC_FOLDER = str(Path(__file__).resolve().parent.parent.parent / "music")

MUSIC_END = pygame.USEREVENT + 1

_state = {
    "tracks": [],
    "index": 0,
    "paused": False,
    "stopped": False,
    "thread_running": False,
}

def _event_loop():
    """Single persistent thread — listens for song end and auto plays next."""
    _state["thread_running"] = True
    clock = pygame.time.Clock()

    while not _state["stopped"]:
        for event in pygame.event.get():
            if event.type == MUSIC_END:
                if not _state["stopped"]:
                    _state["index"] = (_state["index"] + 1) % len(_state["tracks"])
                    track = _state["tracks"][_state["index"]]
                    pygame.mixer.music.load(track)
                    pygame.mixer.music.play()
                    if DEBUG:
                        print(f"Auto-playing: {os.path.basename(track)}")
        clock.tick(10)

    _state["thread_running"] = False

def _ensure_event_loop():
    """Start event loop thread only once."""
    if not _state["thread_running"]:
        t = threading.Thread(target=_event_loop, daemon=False)
        t.start()

def music(action: str) -> str:
    if not pygame.get_init():
        pygame.init()
    if not pygame.mixer.get_init():
        pygame.mixer.init()

    # Register end-of-song event
    pygame.mixer.music.set_endevent(MUSIC_END)

    if not _state["tracks"]:
        exts = ("*.mp3", "*.wav", "*.ogg", "*.flac")
        tracks = []
        for ext in exts:
            tracks.extend(glob.glob(os.path.join(MUSIC_FOLDER, ext)))
        tracks = sorted(tracks)
        if not tracks:
            return f"No music files found in: {MUSIC_FOLDER}"
        _state["tracks"] = tracks
        if DEBUG:
            print(f"Loaded {len(tracks)} tracks from {MUSIC_FOLDER}")

    tracks = _state["tracks"]
    action = action.lower().strip()

    if action == "play":
        _state["stopped"] = False
        pygame.mixer.music.load(tracks[_state["index"]])
        pygame.mixer.music.play()
        _state["paused"] = False
        _ensure_event_loop()
        return f"Playing: {os.path.basename(tracks[_state['index']])}"

    elif action == "pause":
        if pygame.mixer.music.get_busy() and not _state["paused"]:
            pygame.mixer.music.pause()
            _state["paused"] = True
            return "Music paused."
        return "Nothing is currently playing."

    elif action == "resume":
        if _state["paused"]:
            pygame.mixer.music.unpause()
            _state["paused"] = False
            return "Music resumed."
        return "Music is not paused."

    elif action == "next":
        _state["stopped"] = False
        _state["index"] = (_state["index"] + 1) % len(tracks)
        pygame.mixer.music.load(tracks[_state["index"]])
        pygame.mixer.music.play()
        _state["paused"] = False
        _ensure_event_loop()
        return f"Next: {os.path.basename(tracks[_state['index']])}"

    elif action == "prev":
        _state["stopped"] = False
        _state["index"] = (_state["index"] - 1) % len(tracks)
        pygame.mixer.music.load(tracks[_state["index"]])
        pygame.mixer.music.play()
        _state["paused"] = False
        _ensure_event_loop()
        return f"Previous: {os.path.basename(tracks[_state['index']])}"

    elif action == "stop":
        _state["stopped"] = True
        _state["paused"] = False
        pygame.mixer.music.stop()
        return "Music stopped."

    else:
        return f"Unknown action '{action}'. Use: play, pause, resume, next, prev, stop."


if __name__ == "__main__":
    print(music("play"))

    cmd = ""
    while cmd != "stop":
        cmd = input("Enter command (pause/resume/next/prev/stop): ").strip()
        print(music(cmd))