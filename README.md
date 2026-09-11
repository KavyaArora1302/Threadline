# Threadline

Ask a question in plain English and get an answer grounded in your team's
GitHub repo, Jira project, and Slack channel — with the code, tickets, and
conversations it drew from shown alongside it.

The premise: the answer to "why is the checkout page slow?" is rarely in one
place. Part of it is in a commit, part in a Jira ticket, part in something
someone said in Slack three weeks ago. Threadline searches all three, works out
who has actually touched the relevant code, and hands the lot to an AI model to
answer from.

> **Note:** this repository ships with **demo data** — a sample repo, Jira
> project, and Slack channel. It is a portfolio project, not a product.

<!-- screenshot goes here -->

## How it works

```
  GitHub ─┐
  Jira   ─┼─→  ingest to JSON  ─→  keyword search  ─┐
  Slack  ─┘         (data/)                        ├─→  AI answer  ─→  chat
                         │                         │
                         └─→  authorship graph  ───┘
                                 (who touched what)
```

1. **Ingest** — `app/ingestion/` pulls files and commits from GitHub, issues
   from Jira, and messages from Slack into `data/raw/*.json`. Run by hand, not
   on a schedule; the data is a snapshot.
2. **Graph** — `app/graph/` turns commit history into person-to-file edges, so
   Threadline can say *who* has worked on a file, not just that it matched.
3. **Search** — `app/search/` matches a question's meaningful words (filler
   words are stripped in `terms.py`, or short words like "is" would match
   everything) against all three sources.
4. **Answer** — the matches become context for Gemini or Groq, chosen per chat.
   Questions can carry an image too.

Answers, questions, and chat threads persist, so conversations survive a
restart and follow-up questions understand what came before.

## Stack

| | |
|---|---|
| Backend | FastAPI, SQLModel, NetworkX |
| Frontend | React 19, Vite, Redux Toolkit, Tailwind 4 |
| Database | SQLite locally, Postgres in production — same code either way |
| AI | Gemini 3 Flash, Qwen3.6 27B via Groq |

## Running it locally

Requires Python 3.12 and Node 20+.

```bash
# 1. Backend dependencies
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Configuration
cp .env.example .env
# then fill in SESSION_SECRET_KEY, GEMINI_API_KEY and GROQ_API_KEY.
# Leave DATABASE_URL blank — it falls back to SQLite with no setup.

# 3. Create an account (there is no signup page — see below)
.venv/bin/python -m app.auth you@example.com "Your Name"

# 4. Run it
.venv/bin/uvicorn app.main:app --reload --port 8001   # backend
cd frontend && npm install && npm run dev             # frontend, port 5176
```

Open the frontend and log in. In development Vite serves the UI and forwards
`/api` to the backend; in production one FastAPI process serves both.

### Refreshing the data

```bash
python -m app.ingestion.github_ingest owner/repo
python -m app.graph.build_edges owner/repo
python -m app.ingestion.jira_ingest SCRUM
python -m app.ingestion.slack_ingest engineering
```

Which repo, project, and channel are answered from is fixed in `app/main.py` —
Threadline is deployed one instance per team, not configured at runtime.

## Accounts

There is no sign-up page. Accounts are created from the command line:

```bash
python -m app.auth teammate@example.com "Their Name"
```

Passwords are hashed with bcrypt; sessions are a signed cookie.

## Deploying

`render.yaml` deploys to [Render](https://render.com) with a
[Neon](https://neon.tech) Postgres database, both on free tiers. One service
serves the frontend and the API together — the session cookie only travels back
to the origin it came from, so splitting them across two hosts would break
login.

Set `DATABASE_URL`, `SESSION_SECRET_KEY`, `GEMINI_API_KEY` and `GROQ_API_KEY`
in the Render dashboard. The ingestion credentials are not needed on the
server — the running app never imports those modules.

## Layout

```
app/
  main.py          FastAPI routes, and serves the built frontend
  auth.py          password hashing + the account-creation CLI
  db.py            SQLite/Postgres persistence for chats and users
  ingestion/       GitHub, Jira, Slack → data/raw/*.json
  graph/           commits → person-to-file edges
  search/          keyword search per source, then the AI answer step
frontend/          React app (Vite)
data/              ingested demo data, and the local SQLite file
```
