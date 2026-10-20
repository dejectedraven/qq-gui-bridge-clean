import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from store import add_message, connect

WORKSPACE = Path(__file__).resolve().parents[2]
DBS = {
    "group": WORKSPACE / "memory" / "group.db",
    "private": WORKSPACE / "memory" / "private.db",
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", choices=["group", "private"], default="private")
    parser.add_argument("--source", default="")
    parser.add_argument("--chat", default="")
    parser.add_argument("--sender", default="")
    parser.add_argument("--sender-id", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--ts", default="")
    parser.add_argument("--jsonl", default="")
    args = parser.parse_args()

    source = args.source or args.db
    chat = args.chat or source
    ts = args.ts or datetime.now().astimezone().isoformat(timespec="seconds")
    conn = connect(DBS[args.db])
    added = 0

    if args.jsonl:
        for line in Path(args.jsonl).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            _, created = add_message(
                conn,
                str(data.get("ts", ts)),
                str(data.get("source", source)),
                str(data.get("chat", chat)),
                str(data.get("sender", args.sender)),
                str(data.get("sender_id", args.sender_id)),
                str(data.get("text", "")),
            )
            if created:
                added += 1
    elif args.text:
        _, created = add_message(conn, ts, source, chat, args.sender, args.sender_id, args.text)
        if created:
            added += 1

    conn.close()
    print(json.dumps({"added": added}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
