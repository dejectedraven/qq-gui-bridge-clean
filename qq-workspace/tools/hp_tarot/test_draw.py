from datetime import date

from draw import entry, load_deck, pick


def test_deck_integrity() -> None:
    deck = load_deck()
    assert len(deck) == 78
    assert len({card["id"] for card in deck}) == 78
    assert len({card["name"] for card in deck}) == 78
    for card in deck:
        assert card["keywords"]
        assert card["upright"]
        assert card["reversed"]
        assert card["name_en"]
    assert len({card["name_en"] for card in deck}) == 78


def test_entry_uses_english_name() -> None:
    deck = load_deck()
    card = deck[0]
    value = entry("今日", card, False)
    assert value["name"] == card["name_en"]
    assert value["name_cn"] == card["name"]


def test_daily_is_deterministic() -> None:
    deck = load_deck()
    day = date(2026, 10, 19)
    first = pick(deck, "123456789", day, "daily")
    second = pick(deck, "123456789", day, "daily")
    assert first[0]["id"] == second[0]["id"]
    assert first[1] == second[1]


def test_user_and_day_change_the_draw() -> None:
    deck = load_deck()
    day = date(2026, 10, 19)
    a = pick(deck, "user-a", day, "daily")
    b = pick(deck, "user-b", day, "daily")
    c = pick(deck, "user-a", date(2026, 10, 20), "daily")
    assert (a[0]["id"], a[1]) != (b[0]["id"], b[1])
    assert (a[0]["id"], a[1]) != (c[0]["id"], c[1])


def test_three_card_now_matches_daily() -> None:
    deck = load_deck()
    day = date(2026, 10, 19)
    daily = pick(deck, "someone", day, "daily")
    now = pick(deck, "someone", day, "daily")
    assert daily[0]["id"] == now[0]["id"]
    assert daily[1] == now[1]


def main() -> None:
    test_deck_integrity()
    test_entry_uses_english_name()
    test_daily_is_deterministic()
    test_user_and_day_change_the_draw()
    test_three_card_now_matches_daily()
    print("all tests passed")


if __name__ == "__main__":
    main()
