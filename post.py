
import urllib.request
import zipfile
import shutil
import os
from dotenv import load_dotenv
load_dotenv()
DEBUG:bool = os.getenv("DEBUG") == "True"



import extensions.actions.register as rg
import shutil
from pathlib import Path

register = rg.import_all_from_current_directory()

files_to_clean_up_from_debugging = [
    "test.mp3",
    "notes.json"
]

def cleanup_debug_files(file_list: list, base_path: str = None) -> None:
    """
    Remove files and folders mentioned in the cleanup list.
    
    Args:
        file_list: List of file/folder names to remove
        base_path: Base directory to search in (defaults to current directory)
    """
    if base_path is None:
        base_path = os.getcwd()
    
    for item in file_list:
        item_path = Path(base_path) / item
        
        try:
            if item_path.exists():
                if item_path.is_file():
                    item_path.unlink()
                    print(f"Removed file: {item_path}")
                elif item_path.is_dir():
                    shutil.rmtree(item_path)
                    print(f"Removed directory: {item_path}")
            else:
                print(f"Not found: {item_path}")
        except Exception as e:
            print(f"Error removing {item_path}: {e}")


def create_env_file(base_path: str = None) -> None:
    """
    Create a .env file with default configuration if it doesn't exist.
    
    Args:
        base_path: Base directory to create .env in (defaults to current directory)
    """
    if base_path is None:
        base_path = os.getcwd()
    
    env_path = Path(base_path) / ".env"
    
    if env_path.exists():
        print(f".env file already exists at {env_path}")
        return
    
    try:
        with open(env_path, 'w') as f:
            f.write("DEBUG = False\n")
            f.write("GEMINI_API_KEY = \"\"\n")
        print(f"Created .env file at {env_path}")
    except Exception as e:
        print(f"Error creating .env file: {e}")


def check_gemini_api_key() -> None:
    """
    Check if GEMINI_API_KEY exists and has a value in .env file.
    If not, run the geminiAPISetup module.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key or api_key.strip() == "":
        print("GEMINI_API_KEY not found or is empty. Running setup...")
        try:
            import extensions.essentials.geminiAPISetup as gemini_setup
            gemini_setup.setup_gemini()
        except Exception as e:
            print(f"Error importing geminiAPISetup: {e}")
    else:
        print(f"GEMINI_API_KEY found: {api_key[:10]}...")


def ensure_vosk_model(model_path: str = "model"):
    """
    Checks if the Vosk model exists. If not, downloads and extracts it.
    """
    # 1. Check if the model folder exists and isn't empty
    if os.path.exists(model_path) and os.listdir(model_path):
        print(f"✓ Vosk model found at '{model_path}'.")
        return

    print(f"Vosk model not found. Downloading to '{model_path}'...")
    
    url = "https://huggingface.co/ambind/vosk-model-small-en-us-0.15/resolve/main/vosk-model-small-en-us-0.15_c_.zip?download=true"
    zip_path = "temp_model.zip"
    extract_dir = "temp_extracted"

    # 2. Download the zip file
    try:
        urllib.request.urlretrieve(url, zip_path)
        print("✓ Download complete. Extracting...")
    except Exception as e:
        print(f"ERROR: Failed to download the model. {e}")
        return

    # 3. Extract the zip
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # 4. Move the contents from the inner folder to the target model folder
    inner_folder_name = "vosk-model-small-en-us-0.15"
    inner_folder_path = os.path.join(extract_dir, inner_folder_name)

    os.makedirs(model_path, exist_ok=True)

    if os.path.exists(inner_folder_path):
        for item in os.listdir(inner_folder_path):
            source = os.path.join(inner_folder_path, item)
            destination = os.path.join(model_path, item)
            shutil.move(source, destination)
    else:
        print(f"Warning: Expected inner folder '{inner_folder_name}' not found in zip.")

    # 5. Cleanup the temporary files
    print("Cleaning up temporary files...")
    os.remove(zip_path)
    shutil.rmtree(extract_dir)

    print(f"✓ Model successfully installed to '{model_path}'.")


if __name__ == "__main__":
    cleanup_debug_files(files_to_clean_up_from_debugging)
    create_env_file()
    check_gemini_api_key()
    ensure_vosk_model()
    # register["tell_time"]()
    # register["music"]("play")
    
    # cmd = ""
    # while cmd != "stop":
    #     cmd = input("Enter command (pause/resume/next/prev/stop): ").strip()
    #     print(register["music"](cmd))
    # register["link_open"]("https://youtube.com/")

    # register["open_app"]("calculator")
    # register["google_search"]("python tutorials")
    # register["window_control"]("minimize")
    # print(register["system_info"]("battery"))
    # register["reminder"]("set", message="Drink water", seconds=20)
    # register["screenshot"]()
    # register["notes"]("list")
    # print(register["file_search"]("screenshot_20260219_033600.png"))
    # register["open_folder"](("downloads"))
    # print(register["calculator"]("12 * 6"))