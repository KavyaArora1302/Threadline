"""Searches ingested Slack messages for one or more words.

Messages matching more of the words are ranked first.

Usage:
    python -m app.search.slack_search engineering "some words"
"""

import argparse
import json
from pathlib import Path

from app.search.terms import search_terms as _words

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def matching_replies(message: dict, query: str) -> list[dict]:
    """Which of this message's thread replies contain the query words."""
    words = _words(query)
    return [r for r in message.get("replies", []) if any(w in r["text"].lower() for w in words)]


def search_messages(channel: str, query: str) -> list[dict]:
    messages_path = RAW_DIR / f"slack_{channel}.json"
    data = json.loads(messages_path.read_text())

    words = _words(query)
    scored = []
    for msg in data["messages"]:
        reply_text = " ".join(r["text"] for r in msg.get("replies", []))
        haystack = f"{msg['text']} {reply_text}".lower()
        match_count = sum(1 for w in words if w in haystack)
        if match_count > 0:
            scored.append((match_count, msg))

    scored.sort(key=lambda pair: -pair[0])
    return [msg for _, msg in scored]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Slack messages for one or more words.")
    parser.add_argument("channel", help="Slack channel name (without #), e.g. engineering")
    parser.add_argument("query", help="one or more words to search for, e.g. \"payment webhook\"")
    args = parser.parse_args()

    matches = search_messages(args.channel, args.query)
    print(f"Found '{args.query}' in {len(matches)} message(s):")
    for msg in matches:
        print(f"  [{msg['timestamp'][:10]}] {msg['user']}: {msg['text']}")
        for r in matching_replies(msg, args.query):
            print(f"    reply — {r['user']}: {r['text']}")


if __name__ == "__main__":
    main()
