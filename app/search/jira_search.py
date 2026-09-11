"""Searches ingested Jira tickets for one or more words.

Tickets matching more of the words are ranked first.

Usage:
    python -m app.search.jira_search SCRUM "some words"
"""

import argparse
import json
from pathlib import Path

from app.search.terms import search_terms as _words

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def search_issues(project_key: str, query: str) -> list[dict]:
    issues_path = RAW_DIR / f"jira_{project_key}.json"
    data = json.loads(issues_path.read_text())

    words = _words(query)
    scored = []
    for issue in data["issues"]:
        comment_text = " ".join(c["text"] for c in issue.get("comments", []) if c["text"])
        haystack = " ".join(filter(None, [issue.get("summary"), issue.get("description"), comment_text])).lower()
        match_count = sum(1 for w in words if w in haystack)
        if match_count > 0:
            scored.append((match_count, issue))

    scored.sort(key=lambda pair: -pair[0])
    return [issue for _, issue in scored]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Jira tickets for one or more words.")
    parser.add_argument("project_key", help="Jira project key, e.g. SCRUM")
    parser.add_argument("query", help="one or more words to search for, e.g. \"payment webhook\"")
    args = parser.parse_args()

    matches = search_issues(args.project_key, args.query)
    print(f"Found '{args.query}' in {len(matches)} ticket(s):")
    for issue in matches:
        assignee = issue["assignee"] or "(unassigned)"
        print(f"  {issue['key']}: {issue['summary']}")
        print(f"    status: {issue['status']}  |  priority: {issue['priority']}  |  assignee: {assignee}")
        if issue["description"]:
            print(f"    | {issue['description']}")
        for c in issue.get("comments", []):
            print(f"    comment ({c['author']}): {c['text']}")


if __name__ == "__main__":
    main()
