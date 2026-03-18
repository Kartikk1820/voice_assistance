defination = '''
function weather(city: str) -> str:

arguments:
- city: Name of the city to get weather for. Use empty string "" for current location.

Example usage:
weather("Delhi")
weather("London")
weather("New York")
weather("")
weather("Mumbai")
'''

import os
import requests
import extensions.essentials.mouth as mouth
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

def weather(city: str = "") -> str:
    city = city.strip()

    try:
        url      = f"https://wttr.in/{city}?format=3&lang=en"
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            result = f"Could not get weather for '{city}'. Try again later."
            mouth.say(result)
            return result

        raw = response.text.strip()

        if DEBUG:
            print(f"[weather] raw: {raw}")

        # Replace emojis with words so TTS speaks naturally
        emoji_map = {
            "☀️":  "sunny",
            "🌤️": "partly cloudy",
            "⛅":  "partly cloudy",
            "🌥️": "cloudy",
            "☁️":  "cloudy",
            "🌦️": "light rain",
            "🌧️": "rainy",
            "⛈️":  "thunderstorm",
            "🌩️": "thunderstorm",
            "🌨️": "snowing",
            "❄️":  "snowy",
            "🌫️": "foggy",
            "🌬️": "windy",
            "🥵":  "very hot",
            "🥶":  "very cold",
        }
        spoken = raw
        for emoji, word in emoji_map.items():
            spoken = spoken.replace(emoji, word)

        # Strip remaining non-ASCII for clean TTS
        spoken_clean = spoken.encode("ascii", "ignore").decode().strip()
        spoken_clean = " ".join(spoken_clean.split())

        if DEBUG:
            print(f"[weather] spoken: {spoken_clean}")

        mouth.say(spoken_clean if spoken_clean else raw)
        return raw

    except requests.Timeout:
        result = "Weather request timed out. Check your internet connection."
        mouth.say(result)
        return result
    except requests.ConnectionError:
        result = "No internet connection. Cannot fetch weather."
        mouth.say(result)
        return result
    except Exception as e:
        result = f"Weather error: {e}"
        if DEBUG:
            print(f"[weather] {result}")
        mouth.say("Sorry, I could not get the weather right now.")
        return result


if __name__ == "__main__":
    print(weather("Delhi"))
    print(weather("London"))
    print(weather(""))