import re
import json
import os
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

# Initialize the Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def _process_text(text: str) -> str:
    """Remove multiple continous spaces and multiple newlines for a single space and single newline respectively."""
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    return text.strip()

def clean_json_response(response_text: str) -> dict:
    """
    Sanitizes the AI's output to ensure it is valid JSON.
    Removes markdown code blocks (```json ... ```) if present.
    """
    # Remove markdown code blocks if they exist
    cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text, flags=re.IGNORECASE).strip()
    
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        if DEBUG:
            print(f"Error decoding JSON: {e}")
            print(f"Raw Output: {response_text}")
        # Return a safe error structure if parsing fails
        return {"function_name": "error", "args": {"message": "Invalid JSON from AI"}}

def think(user_input: str, tools_definations: str) -> dict:
    """
    Decodes the natural-language user command into a structured Python dictionary.
    
    Args:
        user_input (str): The text spoken by the user.
        tools_definations (str): A large string containing the definations of all available functions.
    
    Returns:
        dict: A dictionary containing 'function_name' and 'args'.
    """
    
    # We construct a strict prompt that acts as the "System Instruction"
    prompt = f"""
    ### ROLE
    You are the 'Brain' of a voice assistant. Your specialized job is to map user requests to specific Python functions.
    
    ### AVAILABLE TOOLS
    Here are the definations of the functions you can use:
    {tools_definations}
    
    ### INSTRUCTIONS
    1. Analyze the USER REQUEST.
    2. Select the most appropriate function from the AVAILABLE TOOLS.
    3. Extract the necessary arguments from the request.
    4. Return ONLY a raw JSON object. Do not include markdown formatting or explanations.
    
    ### OUTPUT SCHEMA
    {{
        "function_name": "exact_function_name_from_defination",
        "args": {{
            "argument_name": "value"
        }}
    }}
    
    ### USER REQUEST
    "{user_input}"
    """

    if DEBUG:
        print(f"--- Sending Prompt to AI ---\nLength: {len(prompt)} chars")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Extract text and parse it into a real Python dictionary
        return clean_json_response(response.text)

    except Exception as e:
        if DEBUG:
            print(f"API Error: {e}")
        return {"function_name": "error", "args": {"message": str(e)}}



# --- TEST AREA (Simulating how the main system will use this) ---
if __name__ == "__main__":
    
    # 1. Gather definations (In the real app, these come from your module imports)
    
    link_open_def = '''
    function link_open(url: str) -> None:
    arguments:
    - url: The URL to open (must be a valid http/https link).
    Example usage: link_open("[https://google.com](https://google.com)")
    '''

    tell_time_def = '''
    function tell_time() -> None
    arguments: None
    description: Retrieves system time and speaks it naturally.
    '''
    
    # Combine them into one context block
    all_tools = link_open_def + "\n\n" + tell_time_def

    # 2. Test Cases
    print("\n--- Test 1: Time ---")
    response_1 = think("What time is it right now?", all_tools)
    print("AI Response:", response_1) 
    # Expected: {'function_name': 'tell_time', 'args': {}}

    print("\n--- Test 2: Browser ---")
    response_2 = think("Open youtube for me", all_tools)
    print("AI Response:", response_2)
    # Expected: {'function_name': 'link_open', 'args': {'url': '[https://youtube.com](https://youtube.com)'}}
