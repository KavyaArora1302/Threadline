"""Searches ingested file contents for one or more words, and shows who touched the matches.

Files/commits matching more of the words are ranked first.

Usage:
    python -m app.search.keyword_search owner/repo "some words"
"""

import argparse
import json
import sys
from pathlib import Path

from app.graph.query import load_graph, people_who_touched
from app.search.terms import search_terms as _words

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

LOCK_FILENAMES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")


def _is_lock_file(filename: str) -> bool:
    return filename.endswith(LOCK_FILENAMES)


def search_files(owner: str, repo: str, query: str) -> list[dict]:
    """Returns matching documents (path + content), best matches first."""
    files_path = RAW_DIR / f"{owner}_{repo}.json"
    data = json.loads(files_path.read_text())

    words = _words(query)
    scored = []
    for doc in data["documents"]:
        content_lower = doc["content"].lower()
        match_count = sum(1 for w in words if w in content_lower)
        if match_count > 0:
            scored.append((match_count, doc))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["path"]))
    return [doc for _, doc in scored]


def matching_lines(doc: dict, query: str, max_lines: int = 3) -> list[str]:
    """Which lines of this file contain the query words, as a preview snippet."""
    words = _words(query)
    lines = []
    for line in doc["content"].splitlines():
        stripped = line.strip()
        if stripped and any(w in stripped.lower() for w in words):
            lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return lines


def search_commits(owner: str, repo: str, query: str) -> list[dict]:
    commits_path = RAW_DIR / f"{owner}_{repo}_commits.json"
    data = json.loads(commits_path.read_text())

    words = _words(query)
    scored = []
    for commit in data["commits"]:
        haystack = commit["message"].lower()
        for f in commit["files"]:
            if f.get("patch") and not _is_lock_file(f["filename"]):
                haystack += "\n" + f["patch"].lower()
        match_count = sum(1 for w in words if w in haystack)
        if match_count > 0:
            scored.append((match_count, commit))

    scored.sort(key=lambda pair: -pair[0])
    return [commit for _, commit in scored]


def files_with_matching_diff(commit: dict, query: str) -> list[dict]:
    """Which of this commit's changed files have the query words in their diff."""
    words = _words(query)
    matches = []
    for f in commit["files"]:
        patch = f.get("patch")
        if patch and not _is_lock_file(f["filename"]) and any(w in patch.lower() for w in words):
            matches.append(f)
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(description="Search file contents for one or more words.")
    parser.add_argument("repo", help="owner/repo, e.g. KavyaArora1302/FlagHouse")
    parser.add_argument("query", help="one or more words to search for, e.g. \"reset password\"")
    args = parser.parse_args()

    try:
        owner, repo = args.repo.split("/", 1)
    except ValueError:
        sys.exit("repo must be in the form owner/repo")

    matches = search_files(owner, repo, args.query)
    print(f"Found '{args.query}' in {len(matches)} file(s):")

    graph = load_graph(owner, repo)
    for doc in matches:
        path = doc["path"]
        touched_by = people_who_touched(graph, path)
        who = ", ".join(touched_by) if touched_by else "(no commit history found)"
        print(f"  {path}  —  touched by: {who}")
        for line in matching_lines(doc, args.query):
            print(f"    | {line}")

    print()

    commit_matches = search_commits(owner, repo, args.query)
    print(f"Found '{args.query}' in {len(commit_matches)} commit(s):")
    for commit in commit_matches:
        first_line = commit["message"].splitlines()[0]
        date = commit["date"][:10]
        print(f"  [{date}] {commit['author_name']}: {first_line}")
        for f in files_with_matching_diff(commit, args.query):
            print(f"    diff — {f['filename']}:")
            for line in f["patch"].splitlines():
                print(f"      {line}")


if __name__ == "__main__":
    main()
