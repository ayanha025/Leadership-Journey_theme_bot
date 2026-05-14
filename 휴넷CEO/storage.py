import json
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def load_confirmed(path: str) -> list:
    if not os.path.exists(path):
        _write(path, [])
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def append_confirmed(item: dict, path: str) -> None:
    data = load_confirmed(path)
    data.append({**item, "confirmed_at": datetime.now(KST).isoformat()})
    _write(path, data)


def _write(path: str, data: list) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
