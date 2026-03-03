import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
SAFE_DIR = Path.cwd()
APP_NAME = "agentic-code-assistant"
LOG_DIR = Path(f"~/.local/share/{APP_NAME}").expanduser()
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_path = LOG_DIR / "app.log"

handler = RotatingFileHandler(
    filename=log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logging.root.setLevel(logging.WARN)
logging.root.addHandler(handler)
