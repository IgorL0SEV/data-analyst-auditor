"""Central configuration for portfolio data-analyst agent."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = Path(os.getenv("DATA_ANALYST_ROOT", BASE_DIR))
load_dotenv(WORKSPACE_ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_ANALYST_DATA_DIR", BASE_DIR / "data"))
LOGS_DIR = Path(os.getenv("DATA_ANALYST_LOGS_DIR", BASE_DIR / "logs"))
TEMP_DIR = Path(os.getenv("DATA_ANALYST_TEMP_DIR", BASE_DIR / "temp"))

DATABASE_URL = os.getenv("DATABASE_URL", "")
NOCODB_BASE_URL = os.getenv("NOCODB_BASE_URL", "")
NOCODB_API_TOKEN = ***"NOCODB_API_TOKEN", "")

# LLM settings
LLM_BACKEND = os.getenv("LLM_BACKEND", "openai")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_API_TOKEN = ***"OLLAMA_API_TOKEN", "")
OPENAI_API_KEY = ***"OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
