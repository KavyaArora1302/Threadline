"""Loads our person-file edges into an in-memory graph and answers questions about them.

Usage:
    python -m app.graph.query owner/repo
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

GRAPH_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "graph"


def load_graph(owner: str, repo: str) -> nx.MultiDiGraph:
    edges_path = GRAPH_DIR / f"{owner}_{repo}_edges.json"
    data = json.loads(edges_path.read_text())

    graph = nx.MultiDiGraph()
    for edge in data["edges"]:
        person_id = f"person:{edge['person_username']}"
        file_id = f"file:{edge['file']}"
        graph.add_node(person_id, type="person", name=edge["person_name"])
        graph.add_node(file_id, type="file", path=edge["file"])
        graph.add_edge(
            person_id, file_id,
            commit_sha=edge["commit_sha"],
            date=edge["date"],
            status=edge["status"],
            additions=edge["additions"],
            deletions=edge["deletions"],
        )
    return graph


def files_touched_by(graph: nx.MultiDiGraph, username: str) -> list[str]:
    person_id = f"person:{username}"
    if person_id not in graph:
        return []
    return sorted({graph.nodes[n]["path"] for n in graph.successors(person_id)})


def people_who_touched(graph: nx.MultiDiGraph, filepath: str) -> list[str]:
    file_id = f"file:{filepath}"
    if file_id not in graph:
        return []
    return sorted({graph.nodes[n]["name"] for n in graph.predecessors(file_id)})


def files_co_changed_with(graph: nx.MultiDiGraph, filepath: str, top_n: int = 5) -> list[tuple[str, int]]:
    """Files that tend to change in the same commits as the given file."""
    file_id = f"file:{filepath}"
    if file_id not in graph:
        return []

    commit_shas = {data["commit_sha"] for _, _, data in graph.in_edges(file_id, data=True)}

    counts = Counter()
    for _, other_file_id, data in graph.edges(data=True):
        if other_file_id != file_id and data["commit_sha"] in commit_shas:
            counts[graph.nodes[other_file_id]["path"]] += 1
    return counts.most_common(top_n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the graph and run a few example questions.")
    parser.add_argument("repo", help="owner/repo, e.g. KavyaArora1302/FlagHouse")
    args = parser.parse_args()

    try:
        owner, repo = args.repo.split("/", 1)
    except ValueError:
        sys.exit("repo must be in the form owner/repo")

    graph = load_graph(owner, repo)
    print(f"Graph loaded: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    print()

    people = sorted({d["name"] for n, d in graph.nodes(data=True) if d["type"] == "person"})
    print(f"People in the graph: {people}")
    print()

    if people:
        first_person = people[0]
        username = next(
            n.split(":", 1)[1] for n, d in graph.nodes(data=True)
            if d["type"] == "person" and d["name"] == first_person
        )
        touched = files_touched_by(graph, username)
        print(f"Q: What files has {first_person} touched?")
        print(f"A: {len(touched)} files, e.g. {touched[:5]}")
        print()

    example_file = "backend/README.md"
    who = people_who_touched(graph, example_file)
    print(f"Q: Who touched {example_file}?")
    print(f"A: {who}")
    print()

    co_changed = files_co_changed_with(graph, example_file)
    print(f"Q: What files tend to change alongside {example_file}?")
    print(f"A: {co_changed}")


if __name__ == "__main__":
    main()
