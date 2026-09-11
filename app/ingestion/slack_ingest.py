"""Pulls messages from a Slack channel and saves them as local JSON.

Usage:
    python -m app.ingestion.slack_ingest engineering
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

SLACK_API = "https://slack.com/api"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"
    return session


def _find_channel_id(session: requests.Session, channel_name: str) -> str:
    resp = session.get(f"{SLACK_API}/conversations.list")
    resp.raise_for_status()
    data = resp.json()
    for channel in data["channels"]:
        if channel["name"] == channel_name:
            return channel["id"]
    raise ValueError(f"Channel '{channel_name}' not found (or the bot hasn't been invited to it)")


def _list_messages(session: requests.Session, channel_id: str) -> list[dict]:
    messages = []
    cursor = None
    while True:
        params = {"channel": channel_id, "limit": 200}
        if cursor:
            params["cursor"] = cursor

        resp = session.get(f"{SLACK_API}/conversations.history", params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error"))

        messages.extend(data.get("messages", []))
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return messages


def _user_display_names(session: requests.Session) -> dict:
    resp = session.get(f"{SLACK_API}/users.list")
    resp.raise_for_status()
    data = resp.json()
    return {u["id"]: u.get("real_name") or u.get("name") for u in data.get("members", [])}


def _list_replies(session: requests.Session, channel_id: str, thread_ts: str) -> list[dict]:
    resp = session.get(
        f"{SLACK_API}/conversations.replies",
        params={"channel": channel_id, "ts": thread_ts},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error"))
    return data.get("messages", [])[1:]  # first item is the parent message itself


def _to_message(msg: dict, user_names: dict) -> dict:
    return {
        "user": user_names.get(msg.get("user"), msg.get("user")),
        "timestamp": datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc).isoformat(),
        "text": msg.get("text", ""),
    }


def ingest_channel(channel_name: str) -> Path:
    session = _session()
    channel_id = _find_channel_id(session, channel_name)
    raw_messages = _list_messages(session, channel_id)
    user_names = _user_display_names(session)

    messages = []
    for msg in raw_messages:
        if msg.get("subtype"):
            continue  # skip system messages like joins/renames — not real conversation

        entry = _to_message(msg, user_names)

        raw_replies = _list_replies(session, channel_id, msg["ts"]) if msg.get("reply_count") else []
        entry["replies"] = [_to_message(r, user_names) for r in raw_replies]

        messages.append(entry)
        print(f"  fetched message from {entry['user']}: {entry['text'][:60]} ({len(entry['replies'])} repl(y/ies))")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"slack_{channel_name}.json"
    out_path.write_text(json.dumps({
        "channel": channel_name,
        "messages": messages,
    }, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a Slack channel's messages into local JSON.")
    parser.add_argument("channel", help="Slack channel name (without #), e.g. engineering")
    args = parser.parse_args()

    print(f"Ingesting Slack channel #{args.channel} ...")
    out_path = ingest_channel(args.channel)
    print(f"Done. Saved to {out_path}")


if __name__ == "__main__":
    main()
