"""
리더십저니 테마 자동화 Slack Bolt 앱
"""
import json
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from scraper import run_scraping
from theme_engine import generate_theme, match_contents, get_direction

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])
TARGET_USER_ID = os.environ["TARGET_USER_ID"]
THEME_HISTORY_PATH = os.getenv("THEME_HISTORY_PATH", "data/theme_history.json")

# 프로세스 메모리 세션
session = {
    "suggested_keywords": [],
    "current": {"keyword": None, "titles": {}, "contents": []},
    "last_ts": None,
    "last_channel": None,
}


# ── 유틸 ────────────────────────────────────────────────────────────────────

def _build_message_text(month, direction, keyword, titles, contents):
    lines = [
        f":date: *{month}월 기획 방향*",
        direction,
        "",
        "─────────────────────────",
        ":clapper: *1. 유튜브 스타일*",
    ]
    for i, t in enumerate(titles.get("youtube", [])[:5]):
        lines.append(f"{i + 1}. {t}")

    lines += ["", "─────────────────────────", ":books: *2. 교육적 스타일*"]
    for i, t in enumerate(titles.get("educational", [])[:5]):
        lines.append(f"{i + 6}. {t}")

    lines += ["", "─────────────────────────", ":fire: *3. 밈/유행어 스타일*"]
    for i, t in enumerate(titles.get("meme", [])[:5]):
        lines.append(f"{i + 11}. {t}")

    lines += ["", "─────────────────────────", ":zap: *4. 어그로 스타일*"]
    for i, t in enumerate(titles.get("aggro", [])[:5]):
        lines.append(f"{i + 16}. {t}")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━━━━", ":books: *추천 콘텐츠 (아티클 · 영상)*"]
    for c in contents:
        icon = ":page_facing_up:" if c.get("type") == "아티클" else ":clapper:"
        lines.append(f"{icon} {c.get('title', '')}")

    return "\n".join(lines)


def _build_blocks(text, titles=None):
    all_titles = []
    if titles:
        all_titles = (
            titles.get("youtube", []) +
            titles.get("educational", []) +
            titles.get("meme", []) +
            titles.get("aggro", [])
        )
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔄 테마 재생성"},
                    "action_id": "regenerate_theme",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 이 테마로 확정"},
                    "action_id": "confirm_theme",
                    "value": json.dumps(all_titles, ensure_ascii=False),
                },
            ],
        },
    ]


def _get_dm_channel():
    result = app.client.conversations_open(users=TARGET_USER_ID)
    return result["channel"]["id"]


def _save_confirmed_theme(keyword):
    path = THEME_HISTORY_PATH
    data = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    if keyword not in data:
        data.append(keyword)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _run_and_send(channel=None, update_ts=None):
    """테마 생성 후 DM 발송 또는 메시지 업데이트"""
    scrape_warnings = run_scraping()

    result = generate_theme(extra_forbidden=session["suggested_keywords"])
    keyword = result["keyword"]
    titles = {k: result[k] for k in ["youtube", "educational", "meme", "aggro"]}
    contents = match_contents(keyword)

    session["current"] = {"keyword": keyword, "titles": titles, "contents": contents}

    month = datetime.now().month
    direction = get_direction(month)
    text = _build_message_text(month, direction, keyword, titles, contents)
    blocks = _build_blocks(text, titles)

    dm_channel = channel or _get_dm_channel()

    if update_ts:
        app.client.chat_update(channel=dm_channel, ts=update_ts, text=text, blocks=blocks)
        session["last_ts"] = update_ts
    else:
        resp = app.client.chat_postMessage(channel=dm_channel, text=text, blocks=blocks)
        session["last_ts"] = resp["ts"]
        session["last_channel"] = dm_channel

    if scrape_warnings:
        app.client.chat_postMessage(
            channel=dm_channel,
            text=":warning: " + " | ".join(scrape_warnings),
        )


# ── 이벤트 핸들러 ────────────────────────────────────────────────────────────

@app.message("테마기획")
def handle_message_trigger(message, client):
    user_id = message.get("user")
    dm = client.conversations_open(users=user_id)["channel"]["id"]
    try:
        _run_and_send(channel=dm)
    except Exception as e:
        client.chat_postMessage(channel=dm, text=f":x: 테마 생성 중 오류가 발생했습니다: {e}")


@app.command("/테마기획")
def handle_slash_command(ack, command):
    ack()
    channel = command["channel_id"]
    try:
        _run_and_send(channel=channel)
    except Exception as e:
        app.client.chat_postMessage(
            channel=channel,
            text=f":x: 테마 생성 중 오류가 발생했습니다: {e}",
        )


@app.action("regenerate_theme")
def handle_regenerate_button(ack, body):
    ack()
    current_kw = session["current"].get("keyword")
    if current_kw and current_kw not in session["suggested_keywords"]:
        session["suggested_keywords"].append(current_kw)

    try:
        _run_and_send(
            channel=session.get("last_channel") or body["channel"]["id"],
            update_ts=session.get("last_ts"),
        )
    except Exception as e:
        dm = session.get("last_channel") or body["channel"]["id"]
        app.client.chat_postMessage(channel=dm, text=f":x: 재생성 오류: {e}")


@app.action("confirm_theme")
def handle_confirm(ack, body):
    ack()
    try:
        all_titles = json.loads(body["actions"][0].get("value", "[]"))
    except Exception:
        all_titles = []

    options = [
        {
            "text": {"type": "plain_text", "text": f"{i + 1}. {t}"[:75]},
            "value": t,
        }
        for i, t in enumerate(all_titles)
    ]

    channel = session.get("last_channel") or body["channel"]["id"]
    app.client.chat_postMessage(
        channel=channel,
        text="확정할 제목을 선택해주세요.",
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": ":pencil: *확정할 제목을 선택해주세요.*"},
                "accessory": {
                    "type": "static_select",
                    "placeholder": {"type": "plain_text", "text": "제목 선택"},
                    "options": options,
                    "action_id": "select_title",
                },
            }
        ],
    )


@app.action("select_title")
def handle_title_select(ack, body):
    ack()
    selected_title = body["actions"][0]["selected_option"]["value"]
    _save_confirmed_theme(selected_title)

    channel = body["channel"]["id"]
    ts = body["message"]["ts"]

    confirm_text = f":white_check_mark: 확정되었습니다.\n선정 테마 제목: *{selected_title}*"
    app.client.chat_update(
        channel=channel,
        ts=ts,
        text=confirm_text,
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": confirm_text}}],
    )

    session["suggested_keywords"] = []
    session["current"] = {"keyword": None, "titles": {}, "contents": []}
    session["last_ts"] = None
    session["last_channel"] = None


# ── 실행 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("리더십저니 Slack 앱 시작")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
