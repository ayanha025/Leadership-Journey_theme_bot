"""
OpenRouter API로 테마 키워드 + 제목 20개 생성, 콘텐츠 풀에서 관련 항목 선별
"""
import concurrent.futures
import json
import logging
import os
import re
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")
# 품질 상위 3개 모델만 동시(병렬) 호출. mistral-nemo·qwen-7b는 지시 이행력이
# 크게 떨어져(키워드 반복 등) 병렬 후보에서 제외.
PARALLEL_MODELS = [
    "meta-llama/llama-3.3-70b-instruct",  # 70B
    "google/gemma-3-27b-it",              # 27B
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
- 제목에 keyword 단어 자체를 그대로 반복해서 쓰지 말 것. 대신 그 키워드의 원인, 증상, 예방법, 회복 전략, 관련 감정·행동, 조직 차원의 대응 등 서로 다른 하위 주제로 폭넓게 표현할 것
  (예: keyword가 "번아웃"이면 "번아웃"이라는 단어 없이 "퇴근해도 꺼지지 않는 알림", "오늘도 방전된 채 출근", "쉬어도 쉰 것 같지 않다면" 처럼 연관 주제로 작성)
- 20개 제목이 비슷한 문장 패턴("~하는 법", "~을 예방하려면" 등)으로 몰리지 않도록 각기 다른 소재·각도·표현 방식을 사용할 것
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


class _QualityError(ValueError):
    """모델 응답이 형식은 맞지만 품질 기준(비정상 문자·키워드 반복·중복 제목 등)을 충족하지 못했을 때"""


class _GarbledTitleError(_QualityError):
    """생성된 제목에 한글/영문 외 비정상 문자(외국어 잔재, 코드 토큰 등)가 섞였을 때"""


class _KeywordRepeatedError(_QualityError):
    """제목 대다수가 keyword 단어를 그대로 반복해서 다양성이 없을 때"""


class _DuplicateTitleError(_QualityError):
    """20개 제목 중 완전히 동일한 제목이 중복 등장할 때"""


MAX_KEYWORD_REPEATS = 4  # 20개 제목 중 keyword 문자열을 그대로 포함해도 되는 최대 개수
MAX_DUPLICATE_TITLES = 0  # 20개 제목 중 다른 제목과 완전히 동일해도 되는 최대 개수

_GARBLED_CHARS = re.compile(
    "["
    "฀-๿"                             # 태국어
    "一-鿿㐀-䶿豈-﫿"    # 한자
    "぀-ヿ"                              # 일본어(히라가나/가타카나)
    "Ḁ-ỿ"                              # 베트남어 확장 라틴
    "Ѐ-ӿ"                              # 키릴
    "؀-ۿ"                              # 아랍어
    "ऀ-ॿ"                              # 데바나가리
    "_"                                          # 코드 토큰(스네이크 케이스) 흔적
    "]"
)


def _find_garbled_title(result):
    """4개 스타일 제목 중 외국어 잔재·코드 토큰이 섞인 첫 번째 제목 반환 (없으면 None).
    이모지 등은 허용 목록에 없어도 정상 제목이므로 차단 대상에서 제외."""
    for key in ["youtube", "educational", "meme", "aggro"]:
        for title in result.get(key, []):
            if _GARBLED_CHARS.search(title):
                return title
    return None


def _count_keyword_repeats(result):
    """20개 제목 중 keyword 문자열을 그대로 포함한 제목 수"""
    keyword = result.get("keyword", "")
    if not keyword:
        return 0
    return sum(
        1
        for key in ["youtube", "educational", "meme", "aggro"]
        for title in result.get(key, [])
        if keyword in title
    )


def _count_duplicate_titles(result):
    """20개 제목 중 앞서 나온 제목과 완전히 동일하게 중복되는 제목 수"""
    seen = set()
    dup_count = 0
    for key in ["youtube", "educational", "meme", "aggro"]:
        for title in result.get(key, []):
            if title in seen:
                dup_count += 1
            else:
                seen.add(title)
    return dup_count


def _request_model(model, user_prompt, headers):
    """모델 1곳에 1회 요청 + 파싱 + 품질 점수 계산. 성공하면 (result, score), 실패하면 (None, error) 반환"""
    try:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        result = _parse_response(content)

        garbled = _find_garbled_title(result)
        repeats = _count_keyword_repeats(result)
        dupes = _count_duplicate_titles(result)
        # 낮을수록 좋음. 비정상 문자 > 중복 제목 > 키워드 반복 순으로 크게 감점
        score = (1000 if garbled else 0) + dupes * 100 + repeats
        return result, score
    except requests.exceptions.HTTPError as e:
        body_text = ""
        if e.response is not None:
            try:
                body_text = e.response.json()
            except Exception:
                body_text = e.response.text[:300]
        logger.warning("모델 %s HTTP 오류 (%s) 응답: %s", model, e, body_text)
        return None, e
    except Exception as e:
        logger.warning("모델 %s 실패 (%s)", model, e)
        return None, e


def _call_openrouter(user_prompt):
    """품질 상위 모델들을 동시에(병렬) 호출해 순차 대기 시간을 없애고,
    우선순위(품질) 순으로 완전히 품질 기준을 통과한 첫 결과를 채택한다.
    어떤 응답도 기준을 완전히 만족 못 해도, 구조적으로 유효한 응답 중 가장 나은 것을
    최후 수단으로 반환해 품질 게이트 때문에 슬랙 명령 자체가 죽는 것을 방지한다."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    models = ([OPENROUTER_MODEL] if OPENROUTER_MODEL else []) + PARALLEL_MODELS
    last_error = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as executor:
        future_to_model = {
            executor.submit(_request_model, model, user_prompt, headers): model
            for model in models
        }
        outcomes = {}
        for future in concurrent.futures.as_completed(future_to_model):
            model = future_to_model[future]
            result, score_or_error = future.result()
            if result is None:
                last_error = score_or_error
                continue
            outcomes[model] = (result, score_or_error)
            logger.info("모델 %s 응답 수신 (score=%s)", model, score_or_error)

    # 우선순위(모델 목록 순서) 상 완전히 품질 기준을 통과한(score=0) 첫 결과를 채택
    for model in models:
        if model in outcomes:
            result, score = outcomes[model]
            if score == 0:
                logger.info("OpenRouter 모델 사용: %s", model)
                return result

    # 완전히 통과한 게 없으면 그중 점수가 가장 좋은 것을 최후 수단으로 사용
    fallback_result, fallback_score = None, None
    for model in models:
        if model in outcomes:
            result, score = outcomes[model]
            if fallback_result is None or score < fallback_score:
                fallback_result, fallback_score = result, score
    if fallback_result is not None:
        logger.warning(
            "병렬 호출한 모델 모두 품질 기준을 완전히 충족하지 못해 최선의 결과 사용 (score=%s)",
            fallback_score,
        )
        return fallback_result
    raise RuntimeError(f"모든 모델 실패: {last_error}")


def _extract_first_json_object(text):
    """중괄호 카운팅으로 첫 번째 완전한 JSON 객체 추출"""
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i, c in enumerate(text[start:], start):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # 국기(지역 표시자)
    "\U0001F300-\U0001FAFF"  # 이모티콘·기호·교통·부속 기호
    "☀-➿"          # 기타 기호 및 딩뱃
    "️"                 # variation selector
    "‍"                 # ZWJ (이모지 조합)
    "]+"
)


def _strip_emoji(text):
    return _EMOJI_PATTERN.sub("", text).strip()


def _parse_response(text):
    """JSON 블록 추출 및 키 검증"""
    clean = re.sub(r"```json|```", "", text).strip()
    json_str = _extract_first_json_object(clean)
    if not json_str:
        raise ValueError("JSON 블록을 찾을 수 없습니다")
    result = json.loads(json_str)
    required = {"keyword", "youtube", "educational", "meme", "aggro"}
    if not required.issubset(result.keys()):
        raise ValueError(f"필수 키 누락: {required - result.keys()}")
    for key in ["youtube", "educational", "meme", "aggro"]:
        if not isinstance(result[key], list) or len(result[key]) < 5:
            raise ValueError(f"{key} 항목이 5개 미만입니다")
        result[key] = [_strip_emoji(str(title)) for title in result[key]]
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


_SEASONAL_RULES = [
    ({"연초"}, range(1, 4)),        # 1-3월만
    ({"연말"}, range(10, 13)),      # 10-12월만
    ({"신년", "새해"}, range(1, 3)), # 1-2월만
]


def _is_seasonal_mismatch(title: str, month: int) -> bool:
    """제목에 계절 고정 키워드가 있고 현재 월이 유효 범위 밖이면 True"""
    for keywords, valid_months in _SEASONAL_RULES:
        if any(kw in title for kw in keywords):
            if month not in valid_months:
                return True
    return False


EXCLUDED_TITLE_KEYWORDS = ["AI몬데이", "티키타카 한 판", "다시 쓰는 리력서", "리더십라디오", "2025 회고"]


def _is_excluded_title(title: str) -> bool:
    """제목에 EXCLUDED_TITLE_KEYWORDS 중 하나라도 포함되면 True (추천 대상에서 항상 제외)"""
    return any(kw in title for kw in EXCLUDED_TITLE_KEYWORDS)


def match_contents(keyword, min_count=5):
    """
    월별 기획 방향의 서브 그룹별로 콘텐츠를 스코어링하고
    라운드로빈으로 고르게 선별해 아티클/영상 혼합 min_count개 반환
    """
    current_month = datetime.now().month
    df = pd.read_csv(CONTENT_CSV_PATH)
    df = df[~df["title"].apply(lambda t: _is_seasonal_mismatch(str(t), current_month))]
    df = df[~df["title"].apply(lambda t: _is_excluded_title(str(t)))]
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
        df = df[~df["title"].apply(lambda t: _is_excluded_title(str(t)))]
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
