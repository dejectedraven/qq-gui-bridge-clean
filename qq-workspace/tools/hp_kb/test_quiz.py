from datetime import date

from quiz import entry, load_pool, pick


def test_daily_is_deterministic() -> None:
    pool = load_pool("all")
    day = date(2026, 10, 20)
    first, _ = pick(pool, "123456789", day, "daily")
    second, _ = pick(pool, "123456789", day, "daily")
    assert first["id"] == second["id"]


def test_user_and_day_change_question() -> None:
    pool = load_pool("all")
    day = date(2026, 10, 20)
    a, _ = pick(pool, "user-a", day, "daily")
    b, _ = pick(pool, "user-b", day, "daily")
    c, _ = pick(pool, "user-a", date(2026, 10, 21), "daily")
    assert (a["id"], b["id"], c["id"]).count(a["id"]) >= 1
    assert len({a["id"], b["id"], c["id"]}) >= 2


def test_kind_filter() -> None:
    quiz_pool = load_pool("quiz")
    muggle_pool = load_pool("muggle")
    assert quiz_pool and muggle_pool
    assert all(doc["kind"] == "quiz" for doc in quiz_pool)
    assert all(doc["kind"] == "muggle" for doc in muggle_pool)
    assert len(quiz_pool) >= 1400


def test_entry_has_question_and_answer() -> None:
    pool = load_pool("all")
    doc, _ = pick(pool, "123456789", date(2026, 10, 20), "daily")
    item = entry("今日", doc)
    assert item["question"]
    assert item["answer"]
    assert item["flavor"]


def main() -> None:
    test_daily_is_deterministic()
    test_user_and_day_change_question()
    test_kind_filter()
    test_entry_has_question_and_answer()
    print("all tests passed")


if __name__ == "__main__":
    main()
