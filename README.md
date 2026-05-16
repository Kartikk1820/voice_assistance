# Voice Assistant

A highly extensible, Python-based desktop voice assistant featuring a dynamic extension system and a sleek graphical user interface. Inspired by advanced personal assistants, this project focuses on fast offline speech recognition and a modular architecture that makes adding new features incredibly easy.

## Features

- **Local Offline Speech Recognition**: Uses [Vosk](https://alphacephei.com/vosk/) for fast, private, and offline speech-to-text.
- **Dynamic Extension System**: The `brain` automatically registers and interprets actions inside the `extensions/actions/` directory, allowing you to add new skills seamlessly without modifying the core logic.
- **Interactive GUI**: A modern, animated Tkinter-based graphical interface that provides visual feedback across different states (Idle, Listening, Thinking, Executing).
- **Extensible Architecture**: Divided into core essentials (`ears`, `mouth`, `brain`) and actionable extensions for maintainable, clean code.

## Prerequisites

- **Python 3.10+** (Recommended)
- **Vosk Language Model**: You need to download a Vosk model to run offline speech recognition.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/voice-assistant.git
   cd voice-assistant
   ```

2. **Set up a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Download the Vosk Model:**
   - Download a compatible model from [Vosk Models](https://alphacephei.com/vosk/models) (e.g., `vosk-model-small-en-us-0.15`).
   - Extract the contents and place the folder in the project root directory. Rename the extracted folder to `model` (or specify the path in your `.env` file).

5. **Environment Configuration:**
   Create a `.env` file in the root directory:
   ```env
   DEBUG=True
   VOSK_MODEL_PATH=model
   ```

## Usage

You can run the assistant in either GUI mode or CLI mode.

### Running with the GUI (Recommended)

```bash
python gui.py
```
- **Hold SPACE**: Activates the microphone and streams live transcription to the screen.
- **Release SPACE**: Finalizes the transcript and executes the mapped action.
- Say **"goodbye"** or close the window to exit.

### Running in CLI Mode

```bash
python main.py
```
- Wait for the beep, then dictate your command.
- The assistant will process your speech and execute the appropriate action.
- Say **"goodbye"** to exit.

## Adding New Skills (Extensions)

The true power of this assistant lies in its modularity. To add a new skill, simply create a new Python file in the `extensions/actions/` directory. 

The `brain` will automatically discover your file, read the `defination` variable, and register the action for use.

Example (`extensions/actions/my_custom_action.py`):
```python
defination = """
Action: my_custom_action
Description: Tells the user a joke.
Arguments: None
"""

def my_custom_action():
    print("Why do programmers prefer dark mode? Because light attracts bugs!")
    return "Joke delivered."
```

## License

This project is open-source and available under the terms of the MIT License. See the [LICENSE](LICENSE) file for more information.
