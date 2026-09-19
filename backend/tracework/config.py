import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("TRACE_DATA_DIR", str(ROOT / "data")))
DB = DATA / "trace.db"
MODEL = os.getenv("TRACE_MODEL", "qwen3:4b")
OLLAMA = "http://127.0.0.1:11434"  # local-only: no paid provider fallback
TG_URL = os.getenv("TG_MCP_URL", "")
TG_GRAPH = os.getenv("TG_GRAPH", "Trace")
