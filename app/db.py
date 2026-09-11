"""Database persistence for chat threads, so they survive a server restart.

A chat thread is a `Chat` row plus its ordered `Turn` rows (one row per
question+answer pair) — mirrors the in-memory {"id", "title", "turns"}
shape `app/main.py` uses today, so Step 3c can swap one for the other
without changing what a "chat" or a "turn" means. The functions below
return plain dicts, not ORM objects, for that same reason.

Usage (manual demo against the real database):
    python -m app.db
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.search.models import DEFAULT_MODEL_ID

# Read .env here rather than relying on some other import having done it —
# `python -m app.db` and `python -m app.auth` both start at this module, with
# no web app around them to have loaded the environment first.
load_dotenv()

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "threadline.db"


def _database_url() -> str:
    """Where the database lives.

    No DATABASE_URL set — a dev machine straight out of git — means the local
    SQLite file, so running Threadline locally needs no configuration at all.
    Set it, as the deployed app does to point at hosted Postgres, and that is
    used instead.

    Hosted Postgres providers hand out URLs beginning `postgres://` or
    `postgresql://`, and SQLAlchemy reads both as "use psycopg2". Threadline
    installs psycopg (v3), so name that in the scheme explicitly — which means
    the URL can be pasted in exactly as the provider printed it.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{DB_PATH}"
    scheme, _, rest = url.partition("://")
    if scheme in ("postgres", "postgresql"):
        return f"postgresql+psycopg://{rest}"
    return url


DATABASE_URL = _database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")
engine = create_engine(DATABASE_URL)


class Chat(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model: str = Field(default=DEFAULT_MODEL_ID)


class Turn(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: str = Field(foreign_key="chat.id", index=True)
    question: str
    answer: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = Field(default="")
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # create_all() only creates missing tables, not missing columns on tables
    # that already exist — the `model` column was added after the `chat`
    # table was first created (and `name` after the `user` table), so a
    # pre-existing database needs them added by hand. New databases already
    # have them via the models above, so this is a no-op there.
    #
    # Only the local SQLite file is old enough to need that patch-up, and
    # PRAGMA is SQLite-only syntax that errors on Postgres — so on any other
    # database there is nothing to do here.
    if not IS_SQLITE:
        return

    with Session(engine) as session:
        columns = session.exec(text("PRAGMA table_info(chat)")).all()
        has_model_column = any(col[1] == "model" for col in columns)
        if not has_model_column:
            session.exec(text(f"ALTER TABLE chat ADD COLUMN model TEXT DEFAULT '{DEFAULT_MODEL_ID}'"))
            session.commit()

        user_columns = session.exec(text("PRAGMA table_info(user)")).all()
        has_name_column = any(col[1] == "name" for col in user_columns)
        if not has_name_column:
            session.exec(text("ALTER TABLE user ADD COLUMN name TEXT DEFAULT ''"))
            session.commit()


def _turn_to_dict(turn: Turn) -> dict:
    return {"question": turn.question, "answer": turn.answer}


def _chat_to_dict(chat: Chat, turns: list) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at,
        "model": chat.model,
        "turns": [_turn_to_dict(t) for t in turns],
    }


def create_chat(model_id: Optional[str] = None) -> dict:
    chat = Chat(id=uuid.uuid4().hex, model=model_id or DEFAULT_MODEL_ID)
    with Session(engine) as session:
        session.add(chat)
        session.commit()
        session.refresh(chat)
    return _chat_to_dict(chat, [])


def get_chat(chat_id: str) -> Optional[dict]:
    with Session(engine) as session:
        chat = session.get(Chat, chat_id)
        if chat is None:
            return None
        turns = session.exec(select(Turn).where(Turn.chat_id == chat_id).order_by(Turn.id)).all()
        return _chat_to_dict(chat, turns)


def list_chats() -> list:
    """Every chat, most recently created first — what a sidebar lists."""
    with Session(engine) as session:
        chats = session.exec(select(Chat).order_by(Chat.created_at.desc())).all()
        return [{"id": c.id, "title": c.title, "created_at": c.created_at, "model": c.model} for c in chats]


def add_turn(chat_id: str, question: str, answer: Optional[str]) -> dict:
    turn = Turn(chat_id=chat_id, question=question, answer=answer)
    with Session(engine) as session:
        session.add(turn)
        session.commit()
        session.refresh(turn)
    return _turn_to_dict(turn)


def delete_chat(chat_id: str) -> None:
    """Removes a chat and all its turns. No-ops if the chat doesn't exist."""
    with Session(engine) as session:
        for turn in session.exec(select(Turn).where(Turn.chat_id == chat_id)).all():
            session.delete(turn)
        chat = session.get(Chat, chat_id)
        if chat is not None:
            session.delete(chat)
        session.commit()


def set_title(chat_id: str, title: str) -> None:
    with Session(engine) as session:
        chat = session.get(Chat, chat_id)
        chat.title = title
        session.add(chat)
        session.commit()


def set_model(chat_id: str, model_id: str) -> None:
    with Session(engine) as session:
        chat = session.get(Chat, chat_id)
        chat.model = model_id
        session.add(chat)
        session.commit()


def create_user(email: str, password_hash: str, name: str) -> dict:
    user = User(id=uuid.uuid4().hex, email=email, name=name, password_hash=password_hash)
    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name}


def get_user_by_email(email: str) -> Optional[dict]:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            return None
        return {"id": user.id, "email": user.email, "name": user.name, "password_hash": user.password_hash}


def get_user_by_id(user_id: str) -> Optional[dict]:
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        return {"id": user.id, "email": user.email, "name": user.name}


def _demo() -> None:
    """Manual test: create a chat, add turns, list/read it back from the DB."""
    init_db()

    chat = create_chat()
    print(f"Created chat: {chat}")

    set_title(chat["id"], "Demo chat about the checkout flow")
    add_turn(chat["id"], "What does the checkout flow do?", "It does X, Y, Z.")
    add_turn(chat["id"], "Who wrote it?", "Kavya, mostly.")

    print(f"All chats: {list_chats()}")
    print(f"Chat reloaded from DB: {get_chat(chat['id'])}")
    print(f"Missing chat: {get_chat('does-not-exist')}")

    throwaway = create_chat()
    add_turn(throwaway["id"], "Should this survive?", "No.")
    delete_chat(throwaway["id"])
    print(f"Deleted chat, now: {get_chat(throwaway['id'])}")


if __name__ == "__main__":
    _demo()
