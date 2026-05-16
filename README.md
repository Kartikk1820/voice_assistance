# Voice Assistant

An intelligent, extensible, and modern Python-based voice assistant powered by advanced speech recognition and LLM APIs. Designed with a modular architecture and dynamic action system, this assistant can understand natural language commands, execute custom actions, and provide an interactive desktop experience through a sleek graphical interface.

---

## ✨ Features

* **Real-Time Speech Recognition**
  Powered by [Vosk](https://alphacephei.com/vosk/) for fast and accurate voice-to-text transcription.

* **LLM-Powered Command Processing**
  Uses powerful LLM APIs to understand natural language, interpret intent, and dynamically trigger actions.

* **Dynamic Extension System**
  Easily add new capabilities by creating action modules inside the `extensions/actions/` directory without modifying the core engine.

* **Modern Interactive GUI**
  Beautiful Tkinter-based interface with animated state transitions:

  * Idle
  * Listening
  * Thinking
  * Executing

* **Modular Architecture**
  Organized into scalable components:

  * `ears` → Speech recognition
  * `brain` → LLM processing & intent handling
  * `mouth` → Voice/text responses
  * `extensions` → Custom actions and integrations

* **Developer Friendly**
  Clean and maintainable codebase designed for rapid feature development and experimentation.

---

# 📂 Project Structure

```bash
voice-assistant/
│
├── brain/                  # LLM processing & intent handling
├── ears/                   # Speech recognition modules
├── mouth/                  # Response generation modules
├── extensions/
│   └── actions/            # Custom dynamic actions
│
├── gui.py                  # GUI entry point
├── main.py                 # CLI entry point
├── requirements.txt
└── README.md
```

---

# 🚀 Getting Started

## Prerequisites

Before running the project, make sure you have:

* **Python 3.10+**
* **LLM API Key** (OpenAI, Gemini, or compatible provider)
* **Vosk Speech Model**

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/yourusername/voice-assistant.git
cd voice-assistant
```

---

## 2. Create a Virtual Environment (Recommended)

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
DEBUG=True

# Speech Recognition Model Path
VOSK_MODEL_PATH=model

# LLM API Keys
OPENAI_API_KEY=your_api_key_here
# or
GEMINI_API_KEY=your_api_key_here
```

---

## 5. Download Speech Recognition Model

Download a compatible model from:

👉 [https://alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)

Example:

```bash
vosk-model-small-en-us-0.15
```

Extract the downloaded model and place it in the project root directory:

```bash
/voice-assistant/model
```

---

# ▶️ Usage

## Launch GUI Mode (Recommended)

```bash
python gui.py
```

### Controls

| Action          | Function          |
| --------------- | ----------------- |
| Hold `SPACE`    | Start voice input |
| Release `SPACE` | Process command   |
| Say `"goodbye"` | Exit assistant    |

---

## Launch CLI Mode

```bash
python main.py
```

### Workflow

1. Wait for the microphone prompt
2. Speak your command
3. The assistant processes the request
4. Corresponding action is executed automatically

---

# 🧩 Creating Custom Extensions

One of the most powerful features of this assistant is its dynamic extension system.

To create a new capability:

1. Add a new Python file inside:

```bash
extensions/actions/
```

2. Define the action metadata and implementation.

---

## Example Extension

```python
definition = """
Action: tell_joke
Description: Tells a programming joke.
Arguments: None
"""

def tell_joke():
    return "Why do programmers prefer dark mode? Because light attracts bugs!"
```

The assistant automatically:

* Discovers the module
* Registers the action
* Makes it available through natural language commands

No core modifications required.

---

# 🛠 Tech Stack

* **Python**
* **Tkinter**
* **Vosk**
* **LLM APIs**
* **dotenv**
* **Modular Plugin Architecture**

---

# 📌 Future Improvements

* Multi-language support
* Wake-word activation
* Web automation actions
* Smart home integrations
* Memory & conversation history
* Voice synthesis improvements
* Cross-platform packaging

---

# 🤝 Contributing

Contributions are welcome.

If you'd like to improve the project:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a pull request

---

# 📄 License

This project is licensed under the MIT License.

See the [LICENSE](LICENSE) file for more information.

---

# ⭐ Support

If you found this project useful, consider giving it a star on GitHub to support development and future improvements.
