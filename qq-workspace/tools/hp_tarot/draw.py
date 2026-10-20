import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

DECK_PATH = Path(__file__).resolve().parent / "deck.json"
VERSION = "hp_tarot_v2"


def load_deck():
    deck = json.loads(DECK_PATH.read_text(encoding="utf-8"))
    if len(deck) != 78:
        raise ValueError(f"deck must contain 78 cards, got {len(deck)}")
    for card in deck:
        if "name_en" not in card:
            raise ValueError(f"card missing name_en: {card.get('id')}")
    return deck


def stable_seed(user_id: str, day, salt: str) -> str:
    raw = f"{VERSION}|{user_id}|{day.isoformat()}|{salt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def pick(deck, user_id: str, day, salt: str = "daily"):
    seed = stable_seed(user_id, day, salt)
    card = deck[int(seed[:12], 16) % len(deck)]
    is_reversed = int(seed[12:16], 16) % 2 == 1
    return card, is_reversed, seed


def entry(label: str, card: dict, is_reversed: bool) -> dict:
    return {
        "position": label,
        "name": card["name_en"],
        "name_cn": card["name"],
        "category": card["category"],
        "orientation": "逆位" if is_reversed else "正位",
        "keywords": card["keywords"],
        "meaning": card["reversed"] if is_reversed else card["upright"],
    }


def clean(value: str, limit: int) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())[:limit]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--spread", choices=["daily", "three"], default="daily")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    user_id = clean(args.user_id, 128)
    name = clean(args.name, 64) or "匿名访客"
    if not user_id:
        parser.error("--user-id must not be empty")

    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            parser.error("--date must be YYYY-MM-DD")
    else:
        day = datetime.now().astimezone().date()

    deck = load_deck()
    daily_card, daily_reversed, daily_seed = pick(deck, user_id, day, "daily")

    if args.spread == "daily":
        cards = [entry("今日", daily_card, daily_reversed)]
    else:
        past_card, past_reversed, _ = pick(deck, user_id, day, "past")
        future_card, future_reversed, _ = pick(deck, user_id, day, "future")
        cards = [
            entry("过去", past_card, past_reversed),
            entry("现在", daily_card, daily_reversed),
            entry("未来", future_card, future_reversed),
        ]

    payload = {
        "version": VERSION,
        "name": name,
        "date": day.isoformat(),
        "spread": args.spread,
        "draw_id": daily_seed[:12],
        "cards": cards,
        "rule": "牌面用英文名，正逆位与解读用中文；同一人同一天的今日牌固定；三牌阵的现在牌等于今日牌。",
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    title = "霍格沃茨塔罗 · 今日牌" if args.spread == "daily" else "霍格沃茨塔罗 · 三牌阵"
    print(title)
    print(f"对象：{name}")
    print(f"日期：{payload['date']}")
    print(f"抽取编号：{payload['draw_id']}")
    print()
    for card in cards:
        print(f"[{card['position']}] {card['name']}（{card['orientation']}） / {card['category']}")
        print(f"关键词：{' / '.join(card['keywords'])}")
        print(f"解读：{card['meaning']}")
        print()
    print("同一人同一天，今日牌固定；不要重复抽牌。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
