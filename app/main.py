"""Chat API for Threadline — ask questions across GitHub, Jira, and Slack.

Usage:
    uvicorn app.main:app --reload
    then run the frontend (see frontend/README.md) and open it in a browser
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()  # before anything below reads os.environ

from app import auth, db
from app.graph.query import load_graph, people_who_touched
from app.search.ai_answer import answer_question, build_context, format_history
from app.search.models import MODELS, get_model
from app.search.jira_search import search_issues
from app.search.keyword_search import matching_lines, search_commits, search_files
from app.search.slack_search import search_messages

# Deployed or on a laptop? The host is expected to set ENVIRONMENT=production;
# RENDER is a fallback Render sets by itself, so forgetting the first one can't
# silently leave a live site with development-grade cookie settings.
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production" or bool(os.getenv("RENDER"))

app = FastAPI(title="Threadline")
db.init_db()  # creates the tables on first run, no-op after

# Threadline has no self-serve signup (see app/auth.py) — every /api/* route
# below requires a logged-in session except the handful needed to log in.
PUBLIC_PATHS = {"/api/login", "/api/ping"}


@app.middleware("http")
async def require_login(request: Request, call_next):
    if request.url.path.startswith("/api") and request.url.path not in PUBLIC_PATHS:
        if "user_id" not in request.session:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return await call_next(request)


# Registered after require_login: Starlette's add_middleware() inserts at the
# front of the stack, so the *last* middleware added runs *first* — this
# ordering is what makes request.session exist by the time require_login
# reads it, instead of raising "SessionMiddleware must be installed".
# https_only keeps the session cookie off plain HTTP once deployed; locally
# there is no HTTPS, so setting it there would stop login working at all.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET_KEY"],
    same_site="lax",
    https_only=IS_PRODUCTION,
)

# Threadline is deployed per team, one repo per team. The repo is fixed at
# setup time, not chosen at runtime — to point this at a different repo,
# ingest it via the CLI (`python -m app.ingestion.github_ingest owner/repo`,
# then `app.graph.build_edges`), then update these constants.
OWNER = "KavyaArora1302"
REPO = "FlagHouse"
CURRENT_REPO = f"{OWNER}/{REPO}"
JIRA_PROJECT_KEY = "SCRUM"
SLACK_CHANNEL = "engineering"

# Threadline is a single local tool for one team, shared by every logged-in
# teammate rather than scoped per-user. Chats are multiple independent
# conversation threads, each with its own question/answer history, persisted
# to data/threadline.db (see app/db.py) so they survive a server restart.


def _make_title(question: str, max_len: int = 48) -> str:
    """A chat's title is just its first question, trimmed — good enough to
    recognize it in a sidebar without asking the AI to summarize anything."""
    collapsed = " ".join(question.split())
    return collapsed if len(collapsed) <= max_len else collapsed[: max_len - 1].rstrip() + "…"


def _get_chat(chat_id: str) -> dict:
    chat = db.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail=f"No chat with id '{chat_id}'")
    return chat


def chat_summary(chat: dict) -> dict:
    # created_at is stored as naive UTC (db.py's Chat.created_at defaults to
    # datetime.utcnow()) — the trailing "Z" tells the frontend to read it as
    # UTC instead of misinterpreting it as local time when bucketing by day.
    return {
        "id": chat["id"],
        "title": chat["title"] or "New chat",
        "created_at": chat["created_at"].isoformat() + "Z",
        "model": chat["model"],
    }


def run_search(q: str, history: str = "", image: Optional[str] = None, model_id: Optional[str] = None) -> dict:
    """Runs the search-and-answer pipeline for one question. `history` carries a
    summary of earlier Q&A turns in this conversation so the AI can understand
    follow-up questions — the search step itself still only uses this question's
    own words. `image` is an optional base64 data URL attached to the question —
    it's handed straight to the AI, not searched against, so it can still ground
    an answer even when there's no matching GitHub/Jira/Slack context. `model_id`
    picks which AI model answers (see app/search/models.py); defaults to Gemini
    when not given."""
    graph = load_graph(OWNER, REPO)
    file_docs = search_files(OWNER, REPO, q)
    file_matches = [
        (
            doc["path"],
            ", ".join(people_who_touched(graph, doc["path"])) or "(unknown)",
            matching_lines(doc, q),
        )
        for doc in file_docs
    ]
    commit_matches = search_commits(OWNER, REPO, q)
    results_by_repo = [(OWNER, REPO, file_matches, commit_matches)]

    jira_matches = search_issues(JIRA_PROJECT_KEY, q)
    slack_matches = search_messages(SLACK_CHANNEL, q)

    answer = ""
    context = build_context(results_by_repo, jira_matches, slack_matches)
    if context.strip() or image:
        try:
            answer = answer_question(q, context, history, image, model_id)
        except Exception as e:
            answer = f"Couldn't get an AI answer right now ({e})."

    return {
        "results_by_repo": results_by_repo,
        "jira_matches": jira_matches,
        "slack_matches": slack_matches,
        "answer": answer,
    }


@app.get("/api/ping")
def ping():
    """First real endpoint for the new React frontend to call — proves the
    frontend/backend split works before any real feature moves over."""
    return {"status": "ok", "repo": CURRENT_REPO}


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/login")
def api_login(body: LoginRequest, request: Request):
    user = db.get_user_by_email(body.email)
    if user is None or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    request.session["user_id"] = user["id"]
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


@app.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"status": "logged_out"}


@app.get("/api/me")
def api_me(request: Request):
    user = db.get_user_by_id(request.session["user_id"])
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class AskRequest(BaseModel):
    question: str
    chat_id: str
    image: Optional[str] = None  # base64 data URL, e.g. "data:image/png;base64,..."


@app.get("/api/state")
def api_state():
    """Everything the React frontend needs to draw the page on load: the
    configured repo, every chat thread (for a sidebar), and the most
    recently created thread's messages to show by default."""
    chats = db.list_chats()
    if not chats:
        # create_chat() already returns the full shape chat_summary() needs
        # (id, title, created_at, model) — rebuilding a partial dict here
        # dropped two of those keys and 500'd on an empty database, which is
        # exactly the state a freshly deployed instance starts in.
        chats = [db.create_chat()]
    current = _get_chat(chats[0]["id"])  # list_chats() is most-recent-first
    return {
        "current_repo": CURRENT_REPO,
        "chats": [chat_summary(c) for c in chats],
        "current_chat_id": current["id"],
        "conversation": current["turns"],
    }


@app.get("/api/models")
def api_list_models():
    """Every AI model Threadline can answer with, across providers — what a
    per-chat model picker lists."""
    return {"models": MODELS}


@app.get("/api/chats")
def api_list_chats():
    """Every chat thread, most recently created first — what a sidebar lists."""
    return {"chats": [chat_summary(c) for c in db.list_chats()]}


@app.post("/api/chats")
def api_create_chat():
    """Starts a new, empty chat thread, independent of every other thread."""
    return chat_summary(db.create_chat())


@app.get("/api/chats/{chat_id}")
def api_get_chat(chat_id: str):
    """One chat thread's full history, for loading it when it's selected."""
    chat = _get_chat(chat_id)
    return {
        "id": chat["id"],
        "title": chat["title"] or "New chat",
        "model": chat["model"],
        "conversation": chat["turns"],
    }


class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None


@app.patch("/api/chats/{chat_id}")
def api_update_chat(chat_id: str, body: UpdateChatRequest):
    """Renames a chat and/or changes which AI model it uses. Either field can
    be sent alone — only what's provided gets updated."""
    _get_chat(chat_id)  # 404s if it doesn't exist

    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title is required")
        db.set_title(chat_id, title)

    if body.model is not None:
        try:
            get_model(body.model)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown model id '{body.model}'")
        db.set_model(chat_id, body.model)

    return chat_summary(_get_chat(chat_id))


@app.delete("/api/chats/{chat_id}")
def api_delete_chat(chat_id: str):
    """Permanently removes a chat thread and all its turns."""
    _get_chat(chat_id)  # 404s if it doesn't exist
    db.delete_chat(chat_id)
    return {"status": "deleted"}


@app.post("/api/ask")
def api_ask(body: AskRequest):
    q = body.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question is required")

    chat = _get_chat(body.chat_id)
    history = format_history(chat["turns"])
    result = run_search(q, history, body.image, chat["model"])
    turn = db.add_turn(body.chat_id, q, result["answer"])
    if chat["title"] is None:
        db.set_title(body.chat_id, _make_title(q))
    return turn


# ---------------------------------------------------------------------------
# The built React app. In development this is skipped entirely (no dist/ until
# something runs `npm run build`) and Vite serves the frontend itself, proxying
# /api here. In production there is no Vite: this process serves both, which is
# what lets the session cookie work — a cookie only goes back to the origin it
# came from, so the page and the API have to share one.
#
# Everything here is registered after every /api route above, because FastAPI
# matches in registration order and the catch-all would otherwise swallow them.
# ---------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    if (FRONTEND_DIST / "assets").is_dir():
        # Hashed filenames, so these can be served straight off disk.
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        """Any address that isn't an API route returns the React app.

        Threadline's routes (`/`, `/login`) exist only inside React, so a
        browser asking the server for `/login` directly — typed in, or just
        refreshed — has to get index.html back rather than a 404, and let
        React work out which page that is.
        """
        # An unknown /api path is a genuine 404, not a page. Without this it
        # would return the React shell with a 200 and the frontend would try
        # to parse HTML as JSON.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Resolve before trusting it: `full_path` comes from the URL, and
        # without this check a crafted path could walk out of dist/ and read
        # arbitrary files off the server.
        root = FRONTEND_DIST.resolve()
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)

        return FileResponse(root / "index.html")


if __name__ == "__main__":
    # Hosts assign a port and expect the app on every interface; both differ
    # from the local defaults, so neither is hardcoded.
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8001")))
