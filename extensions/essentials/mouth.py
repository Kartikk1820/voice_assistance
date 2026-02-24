import os
import asyncio
import edge_tts
import inflect
from just_playback import Playback
import time
import re
from dotenv import load_dotenv
import random
import json

load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"


VOICE = "en-US-ChristopherNeural" 
OUTPUT_FILE = "test.mp3"
cache_file_path = os.path.join(os.getcwd(), "music","memo_cache.json")
p = inflect.engine()

def load_memo_from_disk():
    """Load the memo cache from disk if it exists."""
    if os.path.exists(cache_file_path):
        with open(cache_file_path, "r") as f:
            return json.load(f)
    return {}

memo = load_memo_from_disk()  # A simple in-memory cache to store previously spoken texts and their corresponding audio files.

def save_memo_to_disk():
    """Save the memo cache to disk."""
    with open(cache_file_path, "w") as f:
        json.dump(memo, f)

def _play_audio(file_path: str) -> None:
    """Helper function to play an audio file."""
    try:
        playback = Playback()
        playback.load_file(file_path)
        playback.play()
        while playback.active:
            time.sleep(0.1)
    except Exception as e:
        print(f"Error playing audio: {e}")

def _process_text(text: str) -> str:
    """Internal helper to convert digits to words."""
    words = []
    for word in text.split():
        # Strip punctuation to check if it is a number
        clean_word = re.sub(r'[^\d]', '', word)
        
        if clean_word.isdigit():
            # Convert "10" -> "ten"
            word_val = p.number_to_words(clean_word)
            words.append(word_val)
        else:
            # Keep the original word (preserves punctuation for non-numbers)
            words.append(word)
            
    return " ".join(words)

async def convert_text_to_audio(text , output_file=OUTPUT_FILE):
    # Generate the audio file
    communicate = edge_tts.Communicate(text, VOICE, volume="+0%", rate="+0%")
    await communicate.save(output_file)
    

def say(text: str) -> None:
    """Synchronous wrapper for the async speak function."""
    pt = _process_text(text)
    output_file = os.path.join(os.getcwd(), "music", f"audio_{random.randint(1000,9999)}.mp3")  # Generate a unique filename for each audio output

    if DEBUG:
        print(f"[say] Speaking: {pt}")
    
    if not pt in memo:

        if DEBUG:
            print(f"[say] Cache miss for: {pt}")

        # If we've not generated this audio, generate it
        try:
            asyncio.run(convert_text_to_audio(pt, output_file=output_file))
            memo[pt] = output_file  # Update cache with new file
        except Exception as e:
            print(f"Error generating audio: {e}")

    else:
        if DEBUG:
            print(f"[say] Cache hit for: {pt}")

    try:
        _play_audio(memo[pt])
    except Exception as e:
        print(f"Error playing cached audio: {e}")
        # If there's an error playing the cached audio, we can attempt to regenerate it
        try:
            if DEBUG:
                print(f"[say] Regenerating audio for: {pt}")
            asyncio.run(convert_text_to_audio(pt, output_file=output_file))
            memo[pt] = output_file  # Update cache with new file

        except Exception as e:
            print(f"Error regenerating audio: {e}")



if __name__ == "__main__":
    say("Hello! This is a test.")
    say("I can now speak multiple sentences without crashing.")
    say("The event loop is now managed correctly.")