"""Builds person-to-file connections (edges) from ingested commit data.

Usage:
    python -m app.graph.build_edges owner/repo
"""

import argparse
import json
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
GRAPH_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "graph"


def build_edges(owner: str, repo: str) -> Path:
    commits_path = RAW_DIR / f"{owner}_{repo}_commits.json"
    commits_data = json.loads(commits_path.read_text())

    edges = []
    for commit in commits_data["commits"]:
        for file in commit["files"]:
            edges.append({
                "person_name": commit["author_name"],
                "person_username": commit["author_username"],
                "file": file["filename"],
                "commit_sha": commit["sha"],
                "date": commit["date"],
                "status": file["status"],
                "additions": file["additions"],
                "deletions": file["deletions"],
            })

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GRAPH_DIR / f"{owner}_{repo}_edges.json"
    out_path.write_text(json.dumps({
        "owner": owner,
        "repo": repo,
        "edges": edges,
    }, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build person-to-file edges from ingested commit data.")
    parser.add_argument("repo", help="owner/repo, e.g. KavyaArora1302/FlagHouse")
    args = parser.parse_args()

    try:
        owner, repo = args.repo.split("/", 1)
    except ValueError:
        sys.exit("repo must be in the form owner/repo")

    out_path = build_edges(owner, repo)
    edges_count = len(json.loads(out_path.read_text())["edges"])
    print(f"Built {edges_count} edges. Saved to {out_path}")


if __name__ == "__main__":
    main()
