import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
SAFE_DIR = Path.cwd()

logging.basicConfig(level=logging.WARN, format="%(levelname)s: %(message)s")
