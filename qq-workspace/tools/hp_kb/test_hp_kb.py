import json
from pathlib import Path

from build import (
    build,
    DEFAULT_BANK,
    DEFAULT_GAME,
    DEFAULT_MUGGLE_CSV,
    DEFAULT_QUIZ_CSV,
)
from search import load_kb, search

KB = Path(__file__).resolve().parent / "data" / "kb.json"


def test_kb_is_complete() -> None:
    kb = load_kb(KB)
    assert len(kb["docs"]) >= 2000
    counts = kb["counts"]
    assert counts["quiz"] >= 1400
    assert counts["muggle"] >= 480
    assert counts["card"] >= 70
    assert counts["echo"] >= 15
    assert counts["companion"] >= 15
    ids = [doc["id"] for doc in kb["docs"]]
    assert len(ids) == len(set(ids))


def test_card_lookup() -> None:
    kb = load_kb(KB)
    items = search(kb, "厉火", "card", 3)
    assert items and items[0]["title"] == "厉火"
    assert "7费" in items[0]["text"]


def test_quiz_lookup() -> None:
    kb = load_kb(KB)
    items = search(kb, "1991年谁在霍格沃茨教草药学", "quiz", 3)
    assert items
    assert "斯普劳特教授" in items[0]["text"]


def test_echo_lookup() -> None:
    kb = load_kb(KB)
    items = search(kb, "哈利 回响", "all", 5)
    assert any(item["kind"] == "echo" and item["title"].startswith("哈利") for item in items)


def test_rebuild_is_stable() -> None:
    if not (DEFAULT_BANK.exists() and DEFAULT_GAME.exists()):
        return
    payload = build(DEFAULT_BANK, DEFAULT_GAME, DEFAULT_QUIZ_CSV, DEFAULT_MUGGLE_CSV)
    assert payload["counts"] == json.loads(KB.read_text(encoding="utf-8"))["counts"]


def main() -> None:
    test_kb_is_complete()
    test_card_lookup()
    test_quiz_lookup()
    test_echo_lookup()
    test_rebuild_is_stable()
    print("all tests passed")


if __name__ == "__main__":
    main()
