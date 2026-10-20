import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_OUTBOX = r"C:\path\to\qq-workspace\memory\outbox.jsonl"
DEFAULT_ROOT = r"C:\path\to\qq-workspace"


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue a QQ message for the bridge to deliver.")
    parser.add_argument("--to", choices=["owner", "group"], required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--image", default=None, help="Path to an image file to send.")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Allowed image root directory.")
    parser.add_argument("--allow-outside", action="store_true", help="Allow images outside --root.")
    parser.add_argument("--outbox", default=DEFAULT_OUTBOX)
    args = parser.parse_args()

    text = args.text.strip()
    image = ""
    if args.image:
        image = os.path.abspath(os.path.expanduser(args.image))
        if not os.path.isfile(image):
            print(f"image not found: {image}", file=sys.stderr)
            return 1
        if not args.allow_outside:
            root = os.path.abspath(os.path.expanduser(args.root))
            try:
                inside = os.path.commonpath([image, root]) == root
            except ValueError:
                inside = False
            if not inside:
                print(f"image outside workspace: {image} (use --allow-outside to override)", file=sys.stderr)
                return 1

    if not text and not image:
        print("nothing to send (need --text or --image)", file=sys.stderr)
        return 1

    path = Path(args.outbox)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "target": args.to,
        "text": text,
    }
    if image:
        entry["image"] = image
    entry["ts"] = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    detail = f"{len(text)} chars" + (f" + image {image}" if image else "")
    print(f"queued to {args.to}: {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
