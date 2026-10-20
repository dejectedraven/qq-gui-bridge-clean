import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from embed import embed_text
from ingest import sync_spool
from store import connect, search_messages, semantic_search

WORKSPACE = Path(__file__).resolve().parents[2]
MEMORY_DIR = WORKSPACE / "memory"
DBS = {
    "group": MEMORY_DIR / "group.db",
    "private": MEMORY_DIR / "private.db",
}
SPOOLS = {
    "group": MEMORY_DIR / "group_spool.jsonl",
    "private": MEMORY_DIR / "private_spool.jsonl",
}


def resolve_dbs(name: str):
    if name == "all":
        return list(DBS.items())
    if name in DBS:
        return [(name, DBS[name])]
    path = Path(name)
    return [(path.stem, path)]


def merge(results, limit: int):
    merged = {}
    for item in results:
        key = (item["ts"], item["sender"], item["text"])
        if key not in merged or item["score"] > merged[key]["score"]:
            merged[key] = item
    ordered = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
    return ordered[:limit]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="group", help="group | private | all | path")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--source", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--sync-embed", action="store_true")
    parser.add_argument("--lexical", action="store_true")
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    query_vector = None
    if not args.lexical:
        query_vector = embed_text(args.query, args.model, args.base_url)

    results = []
    for name, db_path in resolve_dbs(args.db):
        if not args.no_sync:
            spool = SPOOLS.get(name)
            if spool is not None:
                sync_spool(
                    db_path,
                    spool,
                    embed_enabled=args.sync_embed,
                    model=args.model,
                    base_url=args.base_url,
                )
        conn = connect(db_path)
        results.extend(search_messages(conn, args.query, args.source or None, args.limit))
        if query_vector:
            results.extend(semantic_search(conn, query_vector, args.source or None, args.limit))
        conn.close()

    results = merge(results, args.limit)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for item in results:
        print(f"[{item['ts']}] {item['sender']}: {item['text']}")
    if not results:
        print("no matching memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
