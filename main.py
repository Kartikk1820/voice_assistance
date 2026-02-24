import os
from dotenv import load_dotenv
load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"


import importlib
import extensions.essentials.ears as ears
import extensions.essentials.mouth as mouth
import extensions.essentials.brain as brain

import extensions.actions.register as rg
function_register = rg.import_all_from_current_directory()

def extract_function_descriptions(actions_dir: str = "extensions/actions") -> str:
    """
    Scans all .py files in the actions directory, extracts their `defination`
    variable, and returns them concatenated as a single multiline string.
    """
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
    else:
        raise ValueError(f"Function '{function_name}' not found in the register.")

def main():
    print("Voice Assistant is running... (say 'goodbye' to exit)")
    all_tools_description = extract_function_descriptions()

    while True:
        mouth.say("Please dictate the next command after beep")
        print(" \n")
        print("Listening for user input...")
        mouth.say("BEEP")
        sound = ears.listen()
        print("processing...")
        
        if DEBUG: print(f"User said: {sound}")
        if not sound:
            continue

        if "good" in sound.lower() and "bye" in sound.lower():
            mouth.say("Goodbye! Have a great day.")
            print("Exiting...")
            mouth.save_memo_to_disk()  # Ensure we save the memo cache before exiting
            break

        try:
            thoughts = brain.think(sound, all_tools_description)
            if DEBUG: print(f"Brain thought: {thoughts}")
            call_function_by_name(thoughts['function_name'], thoughts['args'])
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
if __name__ == "__main__":
    main()