"""Uses an AI model (Gemini or Groq) to write a real answer to a question,
grounded in our search results."""

import os
import re
from typing import Optional

import requests
from dotenv import load_dotenv

from app.search.models import DEFAULT_MODEL_ID, get_model

load_dotenv()

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"

MAX_ITEMS_PER_SOURCE = 5
MAX_HISTORY_TURNS = 5

# Matches a browser-produced data URL, e.g. "data:image/png;base64,iVBORw0KG...".
DATA_URL_RE = re.compile(r"^data:(?P<mime_type>[\w/+-]+);base64,(?P<data>.+)$", re.DOTALL)

# Groq's reasoning models (e.g. Qwen) prepend a <think>...</think> block showing
# their internal reasoning before the real answer — not something our chat UI
# is built to display, so we strip it out.
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def format_history(turns: list) -> str:
    """Formats the last few Q&A turns from this conversation so the AI can read
    them as background — this is what lets follow-up questions make sense."""
    recent = [t for t in turns if not t.get("error")][-MAX_HISTORY_TURNS:]
    if not recent:
        return ""
    lines = []
    for t in recent:
        lines.append(f"User asked: {t['question']}")
        lines.append(f"You answered: {t['answer']}")
    return "\n".join(lines)


def build_context(results_by_repo: list, jira_matches: list, slack_matches: list) -> str:
    """Formats already-fetched search results into text for the AI to read."""
    parts = []

    for owner, repo, file_matches, commit_matches in results_by_repo:
        for path, who, snippet_lines in file_matches[:MAX_ITEMS_PER_SOURCE]:
            snippet = " / ".join(snippet_lines)
            parts.append(f"[GitHub file — {owner}/{repo}] {path} (touched by {who}): {snippet}")
        for commit in commit_matches[:MAX_ITEMS_PER_SOURCE]:
            parts.append(
                f"[GitHub commit — {owner}/{repo}] {commit['date'][:10]} by {commit['author_name']}: "
                f"{commit['message']}"
            )

    for issue in jira_matches[:MAX_ITEMS_PER_SOURCE]:
        comments = " | ".join(c["text"] for c in issue.get("comments", []))
        parts.append(
            f"[Jira {issue['key']}] {issue['summary']} — status: {issue['status']}. "
            f"{issue.get('description', '')} Comments: {comments}"
        )

    for msg in slack_matches[:MAX_ITEMS_PER_SOURCE]:
        replies = " | ".join(r["text"] for r in msg.get("replies", []))
        parts.append(f"[Slack — {msg['timestamp'][:10]}] {msg['user']}: {msg['text']} Replies: {replies}")

    return "\n\n".join(parts)


def _parse_data_url(data_url: str) -> tuple:
    """Splits a browser-produced data URL into (mime_type, base64_data), the
    shape Gemini's API expects an inline image in."""
    match = DATA_URL_RE.match(data_url)
    if not match:
        raise ValueError("image must be a base64 data URL, e.g. 'data:image/png;base64,...'")
    return match.group("mime_type"), match.group("data")


def _build_prompt(question: str, context: str, history: str = "", image: Optional[str] = None) -> str:
    history_block = f"Earlier in this same conversation:\n{history}\n\n" if history else ""
    image_note = (
        "An image is attached to this question — look at it and factor what you see "
        "into your answer, even if the context below doesn't mention it.\n\n"
        if image
        else ""
    )
    return (
        "You are answering a question about a software team's work, using their GitHub, Jira, "
        "and Slack activity below. Use ONLY the context below — if it doesn't contain the answer, say so "
        "honestly instead of guessing. Write a plain, natural answer like a normal chat assistant — do NOT "
        "cite which source(s) you drew from, list ticket numbers, file names, or commit references unless "
        "the question specifically asks for that kind of detail (e.g. 'what's the Jira ticket for this', "
        "'which file', 'who said that in Slack') — only then give the specific identifier. If this "
        "question is a follow-up to the earlier conversation (e.g. it says 'that one', 'what about', "
        "'who else'), use the earlier conversation to understand what's being asked, but still base the "
        "actual answer only on the context below, not on the earlier conversation's content.\n\n"
        f"{image_note}"
        f"{history_block}"
        f"Context for this question:\n{context}\n\n"
        f"Question: {question}"
    )


def ask(question: str, context: str, history: str = "", image: Optional[str] = None) -> str:
    prompt = _build_prompt(question, context, history, image)

    parts = [{"text": prompt}]
    if image:
        mime_type, image_data = _parse_data_url(image)
        parts.append({"inline_data": {"mime_type": mime_type, "data": image_data}})

    resp = requests.post(
        GEMINI_API,
        params={"key": os.getenv("GEMINI_API_KEY")},
        json={"contents": [{"parts": parts}]},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def ask_groq(
    question: str, context: str, history: str = "", image: Optional[str] = None, model: str = "openai/gpt-oss-20b"
) -> str:
    prompt = _build_prompt(question, context, history, image)

    if image:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image}},
        ]
    else:
        content = prompt

    resp = requests.post(
        GROQ_API,
        headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
        json={"model": model, "messages": [{"role": "user", "content": content}]},
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return THINK_BLOCK_RE.sub("", text).strip()


def answer_question(
    question: str,
    context: str,
    history: str = "",
    image: Optional[str] = None,
    model_id: Optional[str] = None,
) -> str:
    """Routes to the right provider's adapter based on which model was chosen."""
    model = get_model(model_id or DEFAULT_MODEL_ID)
    if model["provider"] == "gemini":
        return ask(question, context, history, image)
    if model["provider"] == "groq":
        return ask_groq(question, context, history, image, model=model["id"])
    raise ValueError(f"No adapter wired up for provider '{model['provider']}'")
