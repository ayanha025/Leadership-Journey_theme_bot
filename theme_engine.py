"""
OpenRouter API로 테마 키워드 + 제목 20개 생성, 콘텐츠 풀에서 관련 항목 선별
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")
FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-7b-instruct",
    "mistralai/mistral-nemo",
    "google/gemma-3-27b-it",
]
CONTENT_CSV_PATH = os.getenv("CONTENT_CSV_PATH", "data/contents.csv")
SCRAPED_CONTENTS_PATH = os.getenv("SCRAPED_CONTENTS_PATH", "storage/scraped_contents.json")
THEME_HISTORY_PATH = os.getenv("THEME_HISTORY_PATH", "storage/theme_history.json")
THEME_HISTORY_SEED_PATH = os.getenv("THEME_HISTORY_SEED_PATH", "data/theme_history_seed.json")
CONTENT_HISTORY_PATH = os.getenv("CONTENT_HISTORY_PATH", "storage/content_history.json")
CONTENT_HISTORY_SEED_PATH = os.getenv("CONTENT_HISTORY_SEED_PATH", "data/content_history_seed.json")
MONTHLY_DIRECTION_PATH = os.getenv("MONTHLY_DIRECTION_PATH", "data/monthly_direction.json")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """당신은 리더십 교육 콘텐츠 큐레이터입니다.
주어진 월별 기획 방향에서 핵심 키워드 하나를 선정하고,
그 키워드를 주제로 4가지 스타일별 5개씩 총 20개 제목을 생성합니다.

규칙:
- keyword: 월별 기획 방향에서 선정한 핵심 주제 키워드 (10자 이내)
- 각 스타일별 5개, 총 20개 제목 생성
- 각 제목은 20자 이내
- 금지 목록의 키워드와 주제가 중복되지 않도록 할 것
- 반드시 아래 JSON 형식만 출력 (설명 없이)

스타일 정의:
- youtube: 직관적이고 클릭을 유도하는 제목 (예: 팀원 마음이 닫히는 순간)
- educational: 학습 목적이 명확한 제목 (예: 심리적 안전감 구축 실천법)
- meme: 가볍고 재미있는 밈/유행어 스타일 (예: 팀원 신뢰 레벨 MAX 찍기)
- aggro: 불편하지만 공감되는 어그로성 제목 (예: 그 결정이 팀을 망치고 있습니다)

출력 형식:
{
  "keyword": "선정된 핵심 키워드",
  "youtube": ["제목1", "제목2", "제목3", "제목4", "제목5"],
  "educational": ["제목1", "제목2", "제목3", "제목4", "제목5"],
  "meme": ["제목1", "제목2", "제목3", "제목4", "제목5"],
  "aggro": ["제목1", "제목2", "제목3", "제목4", "제목5"]
}"""


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("JSON 읽기 실패, 기본값 사용: %s", path)
    return default


def _get_monthly_direction():
    month = str(datetime.now().month)
    directions = _load_json(MONTHLY_DIRECTION_PATH, {})
    return month, directions.get(month, "리더십 역량 개발")


def _get_forbidden_list(extra_keywords=None):
    history = _load_json(THEME_HISTORY_PATH, [])
    seed = _load_json(THEME_HISTORY_SEED_PATH, [])
    combined = list(dict.fromkeys(history + seed))  # 중복 제거, 순서 유지
    if extra_keywords:
        combined = combined + extra_keywords
    return combined


def _get_content_keywords():
    """contents.csv에서 tags/cat 상위 빈도 키워드 50개 추출"""
    if not os.path.exists(CONTENT_CSV_PATH):
        return ""
    df = pd.read_csv(CONTENT_CSV_PATH)
    words = []
    for col in ["tags", "cat"]:
        if col in df.columns:
            for val in df[col].dropna():
                words.extend(w for w in re.split(r'[#\s]+', str(val)) if w)
    top = [w for w, _ in Counter(words).most_common(50) if len(w) >= 2 and w != "#"]
    return " ".join(top)


def _call_openrouter(user_prompt):
    """모델 목록을 순서대로 시도, HTTP 오류·JSON 파싱 실패 모두 다음 모델로 넘어감"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    models = ([OPENROUTER_MODEL] if OPENROUTER_MODEL else []) + FALLBACK_MODELS
    last_error = None
    for model in models:
        for attempt in range(2):  # 429 rate limit일 때만 한 번 재시도
            try:
                body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=30)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                result = _parse_response(content)
                logger.info("OpenRouter 모델 사용: %s", model)
                return result
            except requests.exceptions.HTTPError as e:
                last_error = e
                body_text = ""
                if e.response is not None:
                    try:
                        body_text = e.response.json()
                    except Exception:
                        body_text = e.response.text[:300]
                if e.response is not None and e.response.status_code == 429 and attempt == 0:
                    logger.warning("모델 %s 요청 한도 초과, 20초 대기...", model)
                    time.sleep(20)
                    continue
                logger.warning("모델 %s HTTP 오류 (%s) 응답: %s, 다음 모델 시도...", model, e, body_text)
                break
            except Exception as e:
                last_error = e
                logger.warning("모델 %s 실패 (%s), 다음 모델 시도...", model, e)
                break
    raise RuntimeError(f"모든 모델 실패: {last_error}")


def _parse_response(text):
    """JSON 블록 추출 및 키 검증"""
    clean = re.sub(r"```json|```", "", text).strip()
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    if not match:
        raise ValueError("JSON 블록을 찾을 수 없습니다")
    result = json.loads(match.group(0))
    required = {"keyword", "youtube", "educational", "meme", "aggro"}
    if not required.issubset(result.keys()):
        raise ValueError(f"필수 키 누락: {required - result.keys()}")
    for key in ["youtube", "educational", "meme", "aggro"]:
        if not isinstance(result[key], list) or len(result[key]) < 5:
            raise ValueError(f"{key} 항목이 5개 미만입니다")
    return result


def generate_theme(extra_forbidden=None):
    """
    OpenRouter API를 호출해 테마 기획안 생성
    Returns: {"keyword": str, "youtube": [...], "educational": [...], "meme": [...], "aggro": [...]}
    """
    month, direction = _get_monthly_direction()
    forbidden = _get_forbidden_list(extra_forbidden)
    keywords_sample = _get_content_keywords()

    user_prompt = (
        f"이번 달({month}월) 기획 방향: {direction}\n\n"
        f"금지 키워드/주제 목록 ({len(forbidden)}개):\n"
        + "\n".join(f"- {t}" for t in forbidden)
        + f"\n\n콘텐츠 풀 주요 키워드:\n{keywords_sample}\n\n"
        "위 조건에 맞는 테마 기획안을 JSON으로 생성하세요."
    )

    return _call_openrouter(user_prompt)


def _get_used_content_titles():
    """runtime + seed에서 이미 사용된 콘텐츠 제목 목록 반환"""
    runtime = _load_json(CONTENT_HISTORY_PATH, [])
    seed = _load_json(CONTENT_HISTORY_SEED_PATH, [])
    return set(runtime + seed)


def _parse_direction_groups(direction):
    """월별 기획 방향을 서브 키워드 그룹으로 분리 (과/와/·/및 기준)
    과/와는 앞에 한글 2글자 이상이 붙은 경우만 구분자로 인식 (성과·결과 등 복합어 오분리 방지)
    """
    parts = re.split(r'\s*·\s*|\s*및\s*|(?<=[가-힣][가-힣])(?:과|와)(?=\s)', direction)
    return [p.strip() for p in parts if p.strip()]


def match_contents(keyword, min_count=5):
    """
    월별 기획 방향의 서브 그룹별로 콘텐츠를 스코어링하고
    라운드로빈으로 고르게 선별해 아티클/영상 혼합 min_count개 반환
    """
    df = pd.read_csv(CONTENT_CSV_PATH)
    used = _get_used_content_titles()
    if used:
        df = df[~df["title"].isin(used)]

    scraped = _load_json(SCRAPED_CONTENTS_PATH, [])
    if scraped:
        extras = pd.DataFrame({
            "type": ["신규"] * len(scraped),
            "title": scraped,
            "cat": [""] * len(scraped),
            "tags": [""] * len(scraped),
        })
        df = pd.concat([df, extras], ignore_index=True)
        if used:
            df = df[~df["title"].isin(used)]

    _, direction = _get_monthly_direction()
    groups = _parse_direction_groups(direction)

    def score_tokens(row, tokens):
        text = " ".join([
            str(row.get("tags", "") or ""),
            str(row.get("cat", "") or ""),
            str(row.get("title", "") or ""),
        ])
        return sum(1 for t in tokens if t in text)

    # 그룹별로 아티클/영상 혼합 후보 목록 생성
    group_candidates = []
    for group in groups:
        tokens = set(group.split())
        scored = df.copy()
        scored["_score"] = scored.apply(lambda r: score_tokens(r, tokens), axis=1)
        scored = scored[scored["_score"] > 0].sort_values("_score", ascending=False)
        arts = scored[scored["type"] == "아티클"].reset_index(drop=True)
        vids = scored[scored["type"] == "영상"].reset_index(drop=True)
        mixed = []
        ai, vi = 0, 0
        while ai < len(arts) or vi < len(vids):
            if ai < len(arts):
                mixed.append(arts.iloc[ai].to_dict())
                ai += 1
            if vi < len(vids):
                mixed.append(vids.iloc[vi].to_dict())
                vi += 1
        group_candidates.append(mixed)

    # 라운드로빈으로 그룹 간 고르게 선별
    result = []
    seen = set()
    indices = [0] * len(group_candidates)

    while len(result) < min_count:
        added = False
        for i, candidates in enumerate(group_candidates):
            if len(result) >= min_count:
                break
            while indices[i] < len(candidates):
                item = candidates[indices[i]]
                indices[i] += 1
                if item["title"] not in seen:
                    result.append(item)
                    seen.add(item["title"])
                    added = True
                    break
        if not added:
            break

    # 부족하면 전체 풀에서 채움
    if len(result) < min_count:
        df_fill = df[~df["title"].isin(seen)]
        for _, row in df_fill.iterrows():
            if len(result) >= min_count:
                break
            result.append(row.to_dict())

    return result


def get_direction(month):
    """월 번호(int)를 받아 기획 방향 문자열 반환"""
    directions = _load_json(MONTHLY_DIRECTION_PATH, {})
    return directions.get(str(month), "리더십 역량 개발")
