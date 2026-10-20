import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from embed import embed_text
from store import add_embedding, add_message, connect


def sync_spool(db_path, spool_path, embed_enabled: bool = False, model: str = "nomic-embed-text",
               base_url: str = "http://127.0.0.1:11434") -> dict:
    conn = connect(db_path)
    spool = Path(spool_path)
    stats = {"added": 0, "skipped": 0, "embedded": 0, "invalid": 0}
    if spool.exists():
        for line in spool.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                stats["invalid"] += 1
                continue
            text = str(data.get("text", "")).strip()
            if not text:
                stats["invalid"] += 1
                continue
            message_id, created = add_message(
                conn,
                str(data.get("ts", "")),
                str(data.get("source", "group")),
                str(data.get("chat", "")),
                str(data.get("sender", "")),
                str(data.get("sender_id", "")),
                text,
                str(data.get("kind", "message")),
            )
            if not created:
                stats["skipped"] += 1
                continue
            stats["added"] += 1
            if embed_enabled:
                vector = embed_text(text, model, base_url)
                if vector:
                    add_embedding(conn, message_id, model, vector)
                    stats["embedded"] += 1
    conn.close()
    return stats


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--spool", required=True)
    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    stats = sync_spool(args.db, args.spool, args.embed, args.model, args.base_url)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
