"""가변 상태 파일 경로와 JSON 입출력 공용 유틸.

app.py·scraper.py·theme_engine.py가 공유한다.
가변 상태(수집·확정 이력)는 재배포에도 살아남아야 하므로 STORAGE_DIR 한 곳에 모은다.
로컬은 기본값 storage/, Railway는 볼륨 마운트 경로(예: /app/storage)를 STORAGE_DIR로 지정.
seed/csv 등 읽기 전용 리소스는 리포의 data/ 에서 읽는다.
개별 경로 env(SCRAPED_CONTENTS_PATH 등)를 주면 여전히 우선 적용되어 하위 호환.
"""
import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

STORAGE_DIR = os.getenv("STORAGE_DIR", "storage")


def _mutable_path(env_key, filename):
    return os.getenv(env_key) or os.path.join(STORAGE_DIR, filename)


# 가변 상태 (볼륨/STORAGE_DIR)
SCRAPED_CONTENTS_PATH = _mutable_path("SCRAPED_CONTENTS_PATH", "scraped_contents.json")
THEME_HISTORY_PATH = _mutable_path("THEME_HISTORY_PATH", "theme_history.json")
CONTENT_HISTORY_PATH = _mutable_path("CONTENT_HISTORY_PATH", "content_history.json")

# 읽기 전용 리소스 (리포 data/)
CONTENT_CSV_PATH = os.getenv("CONTENT_CSV_PATH", "data/contents.csv")
THEME_HISTORY_SEED_PATH = os.getenv("THEME_HISTORY_SEED_PATH", "data/theme_history_seed.json")
CONTENT_HISTORY_SEED_PATH = os.getenv("CONTENT_HISTORY_SEED_PATH", "data/content_history_seed.json")
MONTHLY_DIRECTION_PATH = os.getenv("MONTHLY_DIRECTION_PATH", "data/monthly_direction.json")

# 가변 상태 디렉터리를 부팅 시 보장 (save_json도 개별 write마다 보장하지만 조기 확보)
os.makedirs(STORAGE_DIR, exist_ok=True)


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("JSON 읽기 실패, 기본값 사용: %s", path)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
