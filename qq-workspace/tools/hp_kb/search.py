"""Read-only lexical search over the local HPMA knowledge base.

Examples:
  python tools/hp_kb/search.py --query "厉火 费用"
  python tools/hp_kb/search.py --query "1991 草药学" --kind quiz
  python tools/hp_kb/search.py --query "哈利回响" --limit 3 --json
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB_PATH = HERE / "data" / "kb.json"


def normalize(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").lower())


def bigrams(value: str) -> set:
    if len(value) < 2:
        return {value} if value else set()
    return {value[i:i + 2] for i in range(len(value) - 1)}


def score(query: str, doc: dict) -> float:
    q = normalize(query)
    if not q:
        return 0.0
    title = normalize(doc.get("title", ""))
    body = normalize(doc.get("text", ""))
    tags = normalize(" ".join(doc.get("tags") or []))
    if q == title:
        return 1.0
    best = 0.0
    if q in title:
        best = max(best, 0.95)
    if q in tags:
        best = max(best, 0.85)
    if q in body:
        best = max(best, 0.8)
    q_grams = bigrams(q)
    for value, weight in ((title, 1.0), (tags, 0.8), (body, 0.6)):
        grams = bigrams(value)
        if not grams:
            continue
        overlap = len(q_grams & grams)
        best = max(best, weight * overlap / math.sqrt(len(q_grams) * len(grams)))
    return round(best, 6)


def load_kb(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"knowledge base missing: {path}; run tools/hp_kb/build.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def search(kb: dict, query: str, kind: str = "all", limit: int = 5) -> list:
    results = []
    for doc in kb.get("docs", []):
        if kind != "all" and doc.get("kind") != kind:
            continue
        value = score(query, doc)
        if value <= 0:
            continue
        results.append({
            "kind": doc.get("kind"),
            "title": doc.get("title"),
            "text": doc.get("text"),
            "source": doc.get("source", ""),
            "score": value,
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--kind", default="all", choices=["all", "card", "quiz", "muggle", "echo", "companion", "rule"])
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--path", default=str(KB_PATH))
    args = parser.parse_args()

    kb = load_kb(Path(args.path))
    items = search(kb, args.query, args.kind, max(1, min(args.limit, 20)))
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    if not items:
        print("没有匹配到条目。")
        return 0
    for item in items:
        print(f"[{item['kind']}] {item['title']}")
        print(item["text"])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
