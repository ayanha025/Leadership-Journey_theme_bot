import logging
import os
import threading

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import content_engine
import storage

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])
TARGET_USER_ID = os.environ["TARGET_USER_ID"]
CONFIRMED_PATH = os.getenv("CONFIRMED_ARTICLES_PATH", "data/confirmed_articles.json")
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "perplexity/sonar-pro")

sessions: dict[str, dict] = {}


def _get_session(user_id: str) -> dict:
    if user_id not in sessions:
        sessions[user_id] = {
            "articles": [], "articles_used_keywords": [],
            "articles_last_ts": None, "articles_last_channel": None,
            "series": [], "series_used_keywords": [],
            "series_last_ts": None, "series_last_channel": None,
        }
    return sessions[user_id]


def _open_dm(client, user_id: str) -> str:
    return client.conversations_open(users=user_id)["channel"]["id"]


def _run_article_search(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = _open_dm(client, user_id)
    loading = client.chat_postMessage(
        channel=dm,
        text="AI가 최신 소재를 서치하고 있습니다… 약 20~40초 소요됩니다 :hourglass_flowing_sand:",
    )
    try:
        prompt = content_engine.build_article_prompt(sess["articles_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        articles = content_engine.parse_articles(raw)
    except Exception as e:
        logger.error("소재 서치 오류: %s", e)
        client.chat_update(channel=dm, ts=loading["ts"],
                           text="소재 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_article_blocks(articles, today)
    result = client.chat_update(channel=dm, ts=loading["ts"],
                                text=f"소재 후보 {len(articles)}건", blocks=blocks)
    sess["articles"] = articles
    sess["articles_used_keywords"].extend(a["keyword"] for a in articles)
    sess["articles_last_ts"] = result["ts"]
    sess["articles_last_channel"] = dm


def _run_series_search(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = _open_dm(client, user_id)
    loading = client.chat_postMessage(
        channel=dm,
        text="AI가 시리즈 기획안을 서치하고 있습니다… 약 20~40초 소요됩니다 :hourglass_flowing_sand:",
    )
    try:
        prompt = content_engine.build_series_prompt(sess["series_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        series = content_engine.parse_series(raw)
    except Exception as e:
        logger.error("시리즈 서치 오류: %s", e)
        client.chat_update(channel=dm, ts=loading["ts"],
                           text="시리즈 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_series_blocks(series, today)
    result = client.chat_update(channel=dm, ts=loading["ts"],
                                text=f"시리즈 기획안 {len(series)}건", blocks=blocks)
    sess["series"] = series
    sess["series_used_keywords"].extend(s["keyword"] for s in series)
    sess["series_last_ts"] = result["ts"]
    sess["series_last_channel"] = dm


def _get_selected_index(state_values: dict, action_id: str) -> int | None:
    for block in state_values.values():
        if action_id in block:
            selected = block[action_id].get("selected_option")
            if selected:
                return int(selected["value"])
    return None


def _do_regenerate_article(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = sess["articles_last_channel"] or _open_dm(client, user_id)
    ts = sess["articles_last_ts"]
    if ts:
        client.chat_update(channel=dm, ts=ts, blocks=[],
                           text="AI가 새 소재를 서치하고 있습니다… :hourglass_flowing_sand:")
    try:
        prompt = content_engine.build_article_prompt(sess["articles_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        articles = content_engine.parse_articles(raw)
    except Exception as e:
        logger.error("소재 재생성 오류: %s", e)
        client.chat_postMessage(channel=dm,
                                text="소재 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_article_blocks(articles, today)
    if ts:
        result = client.chat_update(channel=dm, ts=ts,
                                    text=f"소재 후보 {len(articles)}건", blocks=blocks)
    else:
        result = client.chat_postMessage(channel=dm,
                                         text=f"소재 후보 {len(articles)}건", blocks=blocks)
    sess["articles"] = articles
    sess["articles_used_keywords"].extend(a["keyword"] for a in articles)
    sess["articles_last_ts"] = result["ts"]
    sess["articles_last_channel"] = dm


def _do_regenerate_series(client, user_id: str) -> None:
    sess = _get_session(user_id)
    dm = sess["series_last_channel"] or _open_dm(client, user_id)
    ts = sess["series_last_ts"]
    if ts:
        client.chat_update(channel=dm, ts=ts, blocks=[],
                           text="AI가 새 시리즈 기획안을 서치하고 있습니다… :hourglass_flowing_sand:")
    try:
        prompt = content_engine.build_series_prompt(sess["series_used_keywords"])
        raw = content_engine.call_openrouter(prompt, OPENROUTER_API_KEY, OPENROUTER_MODEL)
        series = content_engine.parse_series(raw)
    except Exception as e:
        logger.error("시리즈 재생성 오류: %s", e)
        client.chat_postMessage(channel=dm,
                                text="시리즈 서치 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return
    today = content_engine.build_dates()[0]
    blocks = content_engine.format_series_blocks(series, today)
    if ts:
        result = client.chat_update(channel=dm, ts=ts,
                                    text=f"시리즈 기획안 {len(series)}건", blocks=blocks)
    else:
        result = client.chat_postMessage(channel=dm,
                                         text=f"시리즈 기획안 {len(series)}건", blocks=blocks)
    sess["series"] = series
    sess["series_used_keywords"].extend(s["keyword"] for s in series)
    sess["series_last_ts"] = result["ts"]
    sess["series_last_channel"] = dm


# ── 메시지 리스너 ──────────────────────────────────────────────

@app.message("소재서치")
def handle_article_search(message, client):
    if message.get("user") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_article_search, args=(client, TARGET_USER_ID)).start()


@app.message("시리즈서치")
def handle_series_search(message, client):
    if message.get("user") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_series_search, args=(client, TARGET_USER_ID)).start()


# ── 슬래시 커맨드 ──────────────────────────────────────────────

@app.command("/소재서치")
def slash_article_search(ack, command, client):
    ack()
    if command.get("user_id") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_article_search, args=(client, TARGET_USER_ID)).start()


@app.command("/시리즈서치")
def slash_series_search(ack, command, client):
    ack()
    if command.get("user_id") != TARGET_USER_ID:
        return
    threading.Thread(target=_run_series_search, args=(client, TARGET_USER_ID)).start()


# ── 버튼 액션 핸들러 ──────────────────────────────────────────

@app.action("regenerate_article")
def handle_regenerate_article(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    threading.Thread(target=_do_regenerate_article, args=(client, TARGET_USER_ID)).start()


@app.action("regenerate_series")
def handle_regenerate_series(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    threading.Thread(target=_do_regenerate_series, args=(client, TARGET_USER_ID)).start()


@app.action("select_article")
def handle_select_article(ack):
    ack()


@app.action("select_series")
def handle_select_series(ack):
    ack()


@app.action("confirm_article")
def handle_confirm_article(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    sess = _get_session(TARGET_USER_ID)
    if not sess["articles"]:
        return
    idx = _get_selected_index(body.get("state", {}).get("values", {}), "select_article")
    if idx is None:
        client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                                text="확정할 소재를 먼저 선택해주세요.")
        return
    item = {**sess["articles"][idx], "type": "article"}
    storage.append_confirmed(item, CONFIRMED_PATH)
    client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                            text=f"✅ 확정 완료: *{item['keyword']}* — {item['title']}")


@app.action("confirm_series")
def handle_confirm_series(ack, body, client):
    ack()
    if body["user"]["id"] != TARGET_USER_ID:
        return
    sess = _get_session(TARGET_USER_ID)
    if not sess["series"]:
        return
    idx = _get_selected_index(body.get("state", {}).get("values", {}), "select_series")
    if idx is None:
        client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                                text="확정할 시리즈를 먼저 선택해주세요.")
        return
    item = {**sess["series"][idx], "type": "series"}
    storage.append_confirmed(item, CONFIRMED_PATH)
    client.chat_postMessage(channel=_open_dm(client, TARGET_USER_ID),
                            text=f"✅ 확정 완료: *{item['keyword']}* — {item['seriesTitle']}")


# ── 진입점 ────────────────────────────────────────────────────

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
