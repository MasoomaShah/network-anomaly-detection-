"""
config.py — Modular LLM & Path Configuration
=============================================
Swap LLM provider by changing LLM_PROVIDER in .env
Supported: groq (default, free), ollama (local), openai
"""

import os
import platform

from dotenv import load_dotenv

# ── Load .env from multiple possible locations ──────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)

# Try project root first, then current working directory
for _env_path in [
    os.path.join(_PROJECT_ROOT, ".env"),
    os.path.join(os.getcwd(), ".env"),
]:
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)
        break

# ── Platform Detection ──────────────────────────────────
IS_WINDOWS = (platform.system() == "Windows")

def get_active_interface():
    """Detects the primary network interface name."""
    if IS_WINDOWS:
        return "Wi-Fi"
    try:
        # Use 'ip route' to find the interface used for the default gateway
        result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
        for line in result.stdout.split("\n"):
            if "dev" in line:
                return line.split("dev")[1].strip().split()[0]
    except:
        pass
    return "wlan0" # fallback

ACTIVE_INTERFACE = get_active_interface()

IS_LINUX   = platform.system() == "Linux"

# ── Paths ───────────────────────────────────────────────────────────────
BASE_DIR          = _PROJECT_ROOT
DATA_DIR          = os.path.join(BASE_DIR, "data")
ALERTS_PATH       = os.path.join(DATA_DIR, "alerts.json")
AGENT_LOG_PATH    = os.path.join(DATA_DIR, "agent_log.json")
AGENT_STATE_PATH  = os.path.join(DATA_DIR, "agent_state.json")
LIVE_METRICS_PATH = os.path.join(DATA_DIR, "live_metrics.json")
KNOWN_DEVICES_PATH = os.path.join(_THIS_DIR, "known_devices.json")

# ── Network ─────────────────────────────────────────────────────────────
GATEWAY   = os.getenv("GATEWAY",   "192.168.1.1")
NETWORK   = os.getenv("NETWORK",   "192.168.1.0/24")
PING_HOST = os.getenv("PING_HOST", "8.8.8.8")
PI_HOST   = os.getenv("PI_HOST",   "")
PI_PORT   = int(os.getenv("PI_PORT", "5000"))


# ── LLM (keys read lazily in get_llm to avoid import-time cache bugs) ──
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()


def get_llm():
    """Factory — returns the configured LangChain ChatModel.
    Reads API keys fresh from env each call (avoids Streamlit cache issues).
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "groq":
        from langchain_groq import ChatGroq
        key   = os.getenv("GROQ_API_KEY", "")
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        if not key:
            raise ValueError(
                "GROQ_API_KEY not set.\n"
                "  1. Get a FREE key → https://console.groq.com\n"
                "  2. Add  GROQ_API_KEY=gsk_...  to your .env file"
            )
        return ChatGroq(model=model, api_key=key, temperature=0)

    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        model = os.getenv("OLLAMA_MODEL", "llama3")
        url   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ChatOllama(model=model, base_url=url, temperature=0)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        key   = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return ChatOpenAI(model=model, api_key=key, temperature=0)

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            "Set to: groq, ollama, or openai in .env"
        )


def get_llm_display_name() -> str:
    """Human-readable name for the active LLM (shown on dashboard)."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    names = {
        "groq":   f"Groq / {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}",
        "ollama": f"Ollama / {os.getenv('OLLAMA_MODEL', 'llama3')}",
        "openai": f"OpenAI / {os.getenv('OPENAI_MODEL', 'gpt-4o')}",
    }
    return names.get(provider, provider)
