"""Structured JSONL event logger — single point for all business events."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOG_FILE = Path(os.getenv("LOG_FILE", "logs/app.jsonl"))
_lock = threading.Lock()


def mask_email(email: str) -> str:
    """al***@example.com — скрывает большую часть local-части."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return local[:2] + "***@" + domain


def log_event(event: str, **fields) -> None:
    """Append one structured event to the JSONL log.
    Never raises, never breaks the calling code.
    None-значения не записываются, чтобы не захламлять лог.
    """
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            **{k: v for k, v in fields.items() if v is not None},
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with _lock:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        pass
