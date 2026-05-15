import json
import os
import re
import time

import requests

CACHE_PATH = "data/existing_articles.json"
CACHE_TTL = 86400  # 24시간
URL = "https://ceo.hunet.co.kr/membership/business-review"


def fetch_existing_titles(cache_path: str = CACHE_PATH) -> list:
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("fetched_at", 0) < CACHE_TTL:
            return data.get("titles", [])

    try:
        resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        titles = re.findall(
            r'class="group-hover/content:underline"[^>]*>(.*?)</',
            resp.text, re.DOTALL,
        )
        titles = [t.strip() for t in titles if t.strip()]
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": time.time(), "titles": titles}, f,
                      ensure_ascii=False, indent=2)
        return titles
    except Exception:
        return []
