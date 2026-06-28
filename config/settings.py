"""Central configuration for data-analyst agent."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
AGENT_NAME = BASE_DIR.name

WORKSPACE_ROOT = BASE_DIR.parent.parent
load_dotenv(WORKSPACE_ROOT / ".env")

DATA_DIR = Path(os.getenv(
    AGENT_NAME.upper().replace("-", "_") + "_DATA_DIR",
    BASE_DIR / "data"
))
LOGS_DIR = Path(os.getenv(
    AGENT_NAME.upper().replace("-", "_") + "_LOGS_DIR",
    BASE_DIR / "logs"
))
TEMP_DIR = Path(os.getenv(
    AGENT_NAME.upper().replace("-", "_") + "_TEMP_DIR",
    BASE_DIR / "temp"
))

DATABASE_URL = os.getenv("DATABASE_URL", "")
NOCODB_BASE_URL = os.getenv("NOCODB_BASE_URL", "")
NOCODB_API_TOKEN = os.getenv("NOCODB_API_TOKEN", "")

# LLM settings
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.7-code:cloud")
OLLAMA_API_TOKEN = os.getenv("OLLAMA_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
