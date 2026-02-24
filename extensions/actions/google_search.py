defination = '''
function google_search(query: str) -> str:

arguments:
- query: The search query to search on Google.

Example usage:
google_search("python tutorials")
google_search("weather today")
'''

import os
import webbrowser
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

def google_search(query: str) -> str:
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    if DEBUG:
        print(f"Searching Google: {query}")
    webbrowser.open(url)
    return f"Searching Google for: {query}"


if __name__ == "__main__":
    print(google_search("python tutorials"))