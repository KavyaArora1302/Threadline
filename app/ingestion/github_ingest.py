"""Pulls file contents from a GitHub repo and saves them as local JSON.

Usage:
    python -m app.ingestion.github_ingest owner/repo
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"
MAX_FILE_SIZE_BYTES = 200_000
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".swift", ".kt",
    ".md", ".mdx", ".txt", ".rst",
    ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".sh", ".sql",
}

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def _session() -> requests.Session:
    session = requests.Session()
    token = os.getenv("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.headers["Accept"] = "application/vnd.github+json"
    return session


def _default_branch(session: requests.Session, owner: str, repo: str) -> str:
    resp = session.get(f"{GITHUB_API}/repos/{owner}/{repo}")
    resp.raise_for_status()
    return resp.json()["default_branch"]


def _list_files(session: requests.Session, owner: str, repo: str, branch: str) -> list[dict]:
    resp = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"},
    )
    resp.raise_for_status()
    tree = resp.json()["tree"]
    return [
        entry for entry in tree
        if entry["type"] == "blob"
        and Path(entry["path"]).suffix in TEXT_EXTENSIONS
        and entry.get("size", 0) <= MAX_FILE_SIZE_BYTES
    ]


def _fetch_content(session: requests.Session, owner: str, repo: str, sha: str) -> str:
    resp = session.get(f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs/{sha}")
    resp.raise_for_status()
    blob = resp.json()
    if blob.get("encoding") != "base64":
        return blob.get("content", "")
    return base64.b64decode(blob["content"]).decode("utf-8", errors="replace")


def ingest_repo(owner: str, repo: str) -> Path:
    session = _session()
    branch = _default_branch(session, owner, repo)
    files = _list_files(session, owner, repo, branch)

    documents = []
    for entry in files:
        content = _fetch_content(session, owner, repo, entry["sha"])
        documents.append({
            "path": entry["path"],
            "sha": entry["sha"],
            "size": entry["size"],
            "content": content,
        })
        print(f"  fetched {entry['path']} ({entry['size']} bytes)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{owner}_{repo}.json"
    out_path.write_text(json.dumps({
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "documents": documents,
    }, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a GitHub repo's text files into local JSON.")
    parser.add_argument("repo", help="owner/repo, e.g. torvalds/linux")
    args = parser.parse_args()

    try:
        owner, repo = args.repo.split("/", 1)
    except ValueError:
        sys.exit("repo must be in the form owner/repo")

    print(f"Ingesting {owner}/{repo} ...")
    out_path = ingest_repo(owner, repo)
    print(f"Done. Saved to {out_path}")


if __name__ == "__main__":
    main()
