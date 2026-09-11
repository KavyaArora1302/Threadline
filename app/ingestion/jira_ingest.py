"""Pulls tickets from a Jira project and saves them as local JSON.

Usage:
    python -m app.ingestion.jira_ingest SCRUM
"""

import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_SITE = os.getenv("JIRA_SITE")
JIRA_API = f"https://{JIRA_SITE}/rest/api/3"

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def _session() -> requests.Session:
    session = requests.Session()
    session.auth = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))
    session.headers["Accept"] = "application/json"
    return session


def _extract_text(node) -> str:
    """Flattens Jira's rich-text description format (Atlassian Document Format) into plain text."""
    if not node:
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_extract_text(child) for child in node.get("content", [])]
    return " ".join(p for p in parts if p)


def _list_issues(session: requests.Session, project_key: str) -> list[dict]:
    issues = []
    next_page_token = None
    while True:
        params = {
            "jql": f"project={project_key}",
            "maxResults": 100,
            "fields": "summary,status,description,assignee,reporter,created,updated,issuetype,priority,comment",
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        resp = session.get(f"{JIRA_API}/search/jql", params=params)
        resp.raise_for_status()
        data = resp.json()
        issues.extend(data.get("issues", []))

        next_page_token = data.get("nextPageToken")
        if data.get("isLast", True) or not next_page_token:
            break
    return issues


def ingest_project(project_key: str) -> Path:
    session = _session()
    raw_issues = _list_issues(session, project_key)

    issues = []
    for issue in raw_issues:
        fields = issue["fields"]
        raw_comments = (fields.get("comment") or {}).get("comments", [])
        comments = [
            {
                "author": (c.get("author") or {}).get("displayName"),
                "created": c.get("created"),
                "text": _extract_text(c.get("body")),
            }
            for c in raw_comments
        ]
        issues.append({
            "key": issue["key"],
            "summary": fields.get("summary"),
            "status": (fields.get("status") or {}).get("name"),
            "issue_type": (fields.get("issuetype") or {}).get("name"),
            "priority": (fields.get("priority") or {}).get("name"),
            "assignee": (fields.get("assignee") or {}).get("displayName"),
            "reporter": (fields.get("reporter") or {}).get("displayName"),
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "description": _extract_text(fields.get("description")),
            "comments": comments,
        })
        print(f"  fetched {issue['key']}: {fields.get('summary')} ({len(comments)} comment(s))")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"jira_{project_key}.json"
    out_path.write_text(json.dumps({
        "site": JIRA_SITE,
        "project_key": project_key,
        "issues": issues,
    }, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a Jira project's tickets into local JSON.")
    parser.add_argument("project_key", help="Jira project key, e.g. SCRUM")
    args = parser.parse_args()

    print(f"Ingesting Jira project {args.project_key} ...")
    out_path = ingest_project(args.project_key)
    print(f"Done. Saved to {out_path}")


if __name__ == "__main__":
    main()
