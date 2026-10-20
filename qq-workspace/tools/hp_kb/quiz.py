"""Deterministic daily quiz draw from the local HPMA knowledge base.

Same user + same day -> same question (and same three-card spread),
mirroring tools/hp_tarot/draw.py.

Examples:
  python tools/hp_kb/quiz.py --user-id 123456789 --name "主人" --json
  python tools/hp_kb/quiz.py --user-id 123456789 --name "主人" --spread three --json
  python tools/hp_kb/quiz.py --user-id 123456789 --name "主人" --kind muggle --json
  python tools/hp_kb/quiz.py --user-id 123456789 --name "主人" --hide-answer
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB_PATH = HERE / "data" / "kb.json"
VERSION = "hp_quiz_v1"

FLAVORS = [
    "今日份冷知识，答不上来也不丢人。",
    "这道题当年坑过不少人。",
    "送分题，真的。",
    "别急着翻书，先想想。",
    "魔法史课的经典送命题。",
    "答对了也没什么奖励。",
    "教授当年就考过这一道。",
    "看着眼熟，对吧？",
]


def load_pool(kind: str = "all") -> list:
    if not KB_PATH.exists():
        raise SystemExit(f"knowledge base missing: {KB_PATH}; run tools/hp_kb/build.py first")
    payload = json.loads(KB_PATH.read_text(encoding="utf-8"))
    docs = payload.get("docs", [])
    if kind == "muggle":
        pool = [doc for doc in docs if doc.get("kind") == "muggle"]
    elif kind == "quiz":
        pool = [doc for doc in docs if doc.get("kind") == "quiz"]
    else:
        pool = [doc for doc in docs if doc.get("kind") in ("quiz", "muggle")]
    if not pool:
        raise SystemExit("no questions in knowledge base; rebuild it first")
    return pool


def stable_seed(user_id: str, day, salt: str) -> str:
    raw = f"{VERSION}|{user_id}|{day.isoformat()}|{salt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def pick(pool: list, user_id: str, day, salt: str = "daily"):
    seed = stable_seed(user_id, day, salt)
    return pool[int(seed[:12], 16) % len(pool)], seed


def parse_question(doc: dict) -> dict:
    text = doc.get("text", "")
    question = doc.get("title", "")
    answer = ""
    options = []
    for part in text.split("｜"):
        if part.startswith("答："):
            answer = part[2:]
        elif part.startswith("选项："):
            options = [item for item in part[3:].split("/") if item]
    return {
        "kind": doc.get("kind"),
        "question": question,
        "answer": answer,
        "options": options,
    }


def entry(label: str, doc: dict) -> dict:
    item = parse_question(doc)
    item["position"] = label
    item["flavor"] = FLAVORS[int(hashlib.sha256(doc.get("id", "").encode()).hexdigest()[:4], 16) % len(FLAVORS)]
    return item


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--spread", choices=["daily", "three"], default="daily")
    parser.add_argument("--kind", choices=["all", "quiz", "muggle"], default="all")
    parser.add_argument("--hide-answer", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    user_id = args.user_id.strip()[:128]
    name = args.name.strip()[:64] or "匿名访客"
    if not user_id:
        parser.error("--user-id must not be empty")

    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            parser.error("--date must be YYYY-MM-DD")
    else:
        day = datetime.now().astimezone().date()

    pool = load_pool(args.kind)
    daily_doc, daily_seed = pick(pool, user_id, day, "daily")

    if args.spread == "daily":
        cards = [entry("今日", daily_doc)]
    else:
        first_doc, _ = pick(pool, user_id, day, "first")
        third_doc, _ = pick(pool, user_id, day, "third")
        cards = [entry("第一问", first_doc), entry("第二问", daily_doc), entry("第三问", third_doc)]

    if args.hide_answer:
        for card in cards:
            card["answer"] = ""

    payload = {
        "version": VERSION,
        "name": name,
        "date": day.isoformat(),
        "spread": args.spread,
        "kind": args.kind,
        "draw_id": daily_seed[:12],
        "items": cards,
        "rule": "同一人同一天题面固定；第二问等于每日一题；先让对方作答，再公布答案。",
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    title = "魔法史 · 每日一题" if args.spread == "daily" else "魔法史 · 三连问"
    print(title)
    print(f"对象：{name}")
    print(f"日期：{payload['date']}")
    print(f"抽取编号：{payload['draw_id']}")
    print()
    for card in cards:
        print(f"[{card['position']}] {card['question']}")
        if card["options"]:
            print(f"选项：{' / '.join(card['options'])}")
        if card["answer"]:
            print(f"答案：{card['answer']}")
        print(f"旁白：{card['flavor']}")
        print()
    print("同一人同一天，题面固定；先答再揭晓。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
