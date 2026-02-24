defination = '''
function talk(text: str) -> None
arguments : text (str)
description : This function takes a string input and uses the say() function to vocalize it.
Use this when the AI wants to respond to the user with a spoken message, answer a question,
confirm an action, or communicate anything back to the user verbally.
example usage: talk("I have opened YouTube for you.")
'''

import os
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

from extensions.essentials.mouth import say

def talk(text: str) -> None:
    if DEBUG:
        print(f"[talk] Speaking: {text}")
    say(text)

if __name__ == "__main__":
    talk("Hello! I am your voice assistant. How can I help you today?")