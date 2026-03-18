import re
import json
import os
from dotenv import load_dotenv

load_dotenv()
DEBUG: bool = os.getenv("DEBUG") == "True"

# ── Provider selection ────────────────────────────────────────────────────────

AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")  # "groq" | "gemini" | "openrouter" | "ollama"

# ── Client initialization ─────────────────────────────────────────────────────

def _init_client():
    if AI_PROVIDER == "groq":
        from groq import Groq
        return Groq(api_key=os.getenv("GROQ_API_KEY"))

    elif AI_PROVIDER == "gemini":
        from google import genai
        return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    elif AI_PROVIDER == "openrouter":
        from openai import OpenAI
        return OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )

    elif AI_PROVIDER == "ollama":
        from openai import OpenAI
        return OpenAI(
            api_key="ollama",
            base_url="http://localhost:11434/v1"
        )

client = _init_client()

# ── Model map ─────────────────────────────────────────────────────────────────

MODEL_MAP = {
    "groq":        "llama-3.1-8b-instant",   # fastest, free
    "gemini":      "gemini-2.0-flash",
    "openrouter":  "meta-llama/llama-3.3-70b-instruct:free",
    "ollama":      "llama3.2",
}
MODEL = os.getenv("AI_MODEL", MODEL_MAP[AI_PROVIDER])

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_HISTORY  = 10
SUMMARY_KEEP = 3
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_FILE  = os.path.join(BASE_DIR, "memory.json")

# ── Cached prompt prefix ──────────────────────────────────────────────────────

_cached_prompt_prefix = None
_cached_tools_hash    = None

# ── Memory helpers ────────────────────────────────────────────────────────────

def _load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {"summary": "", "history": []}

def _save_memory(memory: dict):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

_memory = _load_memory()

def clear_memory():
    global _memory
    _memory = {"summary": "", "history": []}
    _save_memory(_memory)
    if DEBUG:
        print("[brain] Memory cleared.")

# ── AI call (unified for all providers) ──────────────────────────────────────

def _call_ai(prompt: str) -> str:
    """Single function that works for Groq, OpenRouter, Ollama (all OpenAI-compatible)."""
    if AI_PROVIDER == "gemini":
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={"temperature": 0, "max_output_tokens": 150}
        )
        return response.text

    else:
        # Groq, OpenRouter, Ollama all use OpenAI-compatible API
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )
        return response.choices[0].message.content

# ── Summarization ─────────────────────────────────────────────────────────────

def _summarize() -> str:
    if not _memory["history"]:
        return ""

    history_text = "\n".join(
        f"User: {turn['user']}\nCalled: {turn['function']}({json.dumps(turn['args'])})"
        for turn in _memory["history"]
    )
    existing = _memory.get("summary", "")
    context  = f"Previous summary:\n{existing}\n\n" if existing else ""

    prompt = f"""{context}Summarize this voice assistant conversation in 2-3 sentences.
Focus on: what user asked, actions taken, preferences shown.
Be concise — used as context for future commands.

CONVERSATION:
{history_text}

Return ONLY the summary text."""

    try:
        summary = _call_ai(prompt).strip()
        if DEBUG:
            print(f"[brain] Summary: {summary}")
        return summary
    except Exception as e:
        if DEBUG:
            print(f"[brain] Summarization failed: {e}")
        return existing

def _maybe_summarize():
    if len(_memory["history"]) >= MAX_HISTORY:
        if DEBUG:
            print(f"[brain] Summarizing at {MAX_HISTORY} turns...")
        _memory["summary"] = _summarize()
        _memory["history"] = _memory["history"][-SUMMARY_KEEP:]
        _save_memory(_memory)

# ── JSON cleanup ──────────────────────────────────────────────────────────────

def clean_json_response(response_text: str) -> dict:
    cleaned = re.sub(r"```json\s*|\s*```", "", response_text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        if DEBUG:
            print(f"JSON Error: {e}\nRaw: {response_text}")
        return {"function_name": "error", "args": {"message": "Invalid JSON from AI"}}

# ── Core think function ───────────────────────────────────────────────────────

def think(user_input: str, tools_definations: str) -> dict:
    global _cached_prompt_prefix, _cached_tools_hash

    tools_hash = hash(tools_definations)
    if tools_hash != _cached_tools_hash:
        _cached_tools_hash    = tools_hash
        _cached_prompt_prefix = f"""You are the Brain of a voice assistant. Map user requests to Python functions.

AVAILABLE TOOLS:
{tools_definations}

RULES:
- Return ONLY raw JSON, no markdown, no explanation.
- FORMAT: {{"function_name": "exact_name", "args": {{"key": "value"}}}}
- If no args: "args": {{}}
- Use conversation context to resolve follow-ups like "play it", "open that", "search again".
"""
        if DEBUG:
            print(f"[brain] Tools cached | Provider: {AI_PROVIDER} | Model: {MODEL}")

    # Build context from memory
    context_block = ""
    if _memory.get("summary"):
        context_block += f"CONVERSATION SUMMARY:\n{_memory['summary']}\n\n"
    if _memory["history"]:
        recent = "\n".join(
            f"  \"{t['user']}\" → {t['function']}({json.dumps(t['args'])})"
            for t in _memory["history"]
        )
        context_block += f"RECENT TURNS:\n{recent}\n\n"

    prompt = _cached_prompt_prefix
    if context_block:
        prompt += f"\nCONTEXT:\n{context_block}"
    prompt += f'\nUSER REQUEST: "{user_input}"'

    if DEBUG:
        print(f"[brain] {AI_PROVIDER}/{MODEL} | {len(prompt)} chars | {len(_memory['history'])} turns")

    try:
        result = clean_json_response(_call_ai(prompt))

        if result.get("function_name") != "error":
            _memory["history"].append({
                "user":     user_input,
                "function": result["function_name"],
                "args":     result.get("args", {})
            })
            _maybe_summarize()
            _save_memory(_memory)

        return result

    except Exception as e:
        if DEBUG:
            print(f"[brain] Error: {e}")
        return {"function_name": "error", "args": {"message": str(e)}}


# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tools = '''
    function link_open(url: str) -> None:
    arguments:
    - url: URL to open
    Example: link_open("https://youtube.com")

    function music(action: str) -> str:
    arguments:
    - action: "play", "pause", "next", "stop"
    Example: music("play")
    '''

    print(think("open youtube", tools))
    print(think("now open github", tools))
    print(think("play music", tools))
    print(think("skip to next song", tools))
    print("\nMemory:", json.dumps(_memory, indent=2))