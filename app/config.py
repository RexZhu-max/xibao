from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = os.getenv("VERCEL", "").strip() == "1"
DEFAULT_DATA_DIR = Path("/tmp/sales_mvp_data") if IS_VERCEL else (BASE_DIR / "data")
DATA_DIR = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
UPLOAD_DIR = DATA_DIR / "uploads"
POSTER_DIR = DATA_DIR / "posters"
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "sales_mvp.db")))

KIMI_API_KEY = os.getenv("KIMI_API_KEY", "").strip()
KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-latest")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "4000000"))

POSTER_FONT_PATH = os.getenv("POSTER_FONT_PATH", "").strip()

for directory in [DATA_DIR, UPLOAD_DIR, POSTER_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
