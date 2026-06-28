#!/usr/bin/env python3
"""Shared helpers for data-analyst agent."""
import sys
import logging
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime, date

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import LOGS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "data_analyst.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def to_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2, default=json_default)
