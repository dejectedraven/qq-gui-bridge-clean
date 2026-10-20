"""Build the local HPMA knowledge base from the owner's data files.

Sources (read-only, outside the workspace):
  - Magic-history question bank: HPMAMagicHistorySolver/data/bank_web.json
  - Card / echo / companion manual: HPMAMagicQuiz/data/game_data.json

Output: tools/hp_kb/data/kb.json
"""

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BANK = Path(r"C:\path\to\hpma\history\bank_web.json")
DEFAULT_GAME = Path(r"C:\path\to\hpma\quiz\game_data.json")
DEFAULT_QUIZ_CSV = Path(r"C:\path\to\hpma\quiz\questions.csv")
DEFAULT_MUGGLE_CSV = Path(r"C:\path\to\hpma\quiz\questions_muggle.csv")
DEFAULT_OUT = HERE / "data" / "kb.json"


def norm_key(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").lower())


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def join(values) -> str:
    return "/".join(clean(v) for v in values if clean(v))


def quiz_docs(bank: dict) -> list:
    docs = []
    for item in bank.get("questions", []):
        question = clean(item.get("question_zh"))
        answers = item.get("answers_zh") or []
        options = item.get("options_zh") or []
        if not question or not answers:
            continue
        parts = [f"问：{question}", f"答：{join(answers)}"]
        if options:
            parts.append(f"选项：{join(options)}")
        docs.append({
            "id": f"quiz:{item.get('id') or len(docs)}",
            "kind": "quiz",
            "title": question,
            "text": "｜".join(parts),
            "tags": ["魔法史", "答题"],
            "source": clean(item.get("source")),
        })
    return docs


def card_docs(data: dict) -> list:
    docs = []
    for card in data.get("spell_cards", []):
        docs.append({
            "id": f"card:{card.get('id')}",
            "kind": "card",
            "title": clean(card.get("name")),
            "text": "｜".join(filter(None, [
                f"{clean(card.get('name'))}（{clean(card.get('name_en'))}）",
                f"咒语·{clean(card.get('category'))}",
                f"{card.get('cost')}费",
                clean(card.get("rarity")),
                f"标签：{join(card.get('tags') or [])}",
                f"目标：{clean(card.get('target'))}",
                f"效果：{clean(card.get('effect'))}",
                clean(card.get("description")),
            ])),
            "tags": card.get("tags") or [],
            "source": "game_data.json",
        })
    for card in data.get("summon_cards", []):
        docs.append({
            "id": f"card:{card.get('id')}",
            "kind": "card",
            "title": clean(card.get("name")),
            "text": "｜".join(filter(None, [
                f"{clean(card.get('name'))}（{clean(card.get('name_en'))}）",
                f"召唤·{clean(card.get('category'))}",
                f"{card.get('cost')}费",
                clean(card.get("rarity")),
                f"数量：{card.get('summon_count')}" if card.get("summon_count") else "",
                f"标签：{join(card.get('tags') or [])}",
                f"目标：{clean(card.get('target'))}",
                f"效果：{clean(card.get('effect'))}",
            ])),
            "tags": card.get("tags") or [],
            "source": "game_data.json",
        })
    for card in data.get("companion_cards", []):
        docs.append({
            "id": f"companion:{card.get('id')}",
            "kind": "companion",
            "title": clean(card.get("name")),
            "text": "｜".join(filter(None, [
                f"{clean(card.get('name'))}（{clean(card.get('name_en'))}）",
                "伙伴卡",
                clean(card.get("rarity")),
                f"定位：{clean(card.get('role'))}",
                f"标签：{join(card.get('tags') or [])}",
                f"效果：{clean(card.get('effect'))}",
                f"适用：{join(card.get('use_case') or [])}",
            ])),
            "tags": card.get("tags") or [],
            "source": "game_data.json",
        })
    return docs


def echo_docs(data: dict) -> list:
    docs = []
    for key, echo in (data.get("echoes") or {}).items():
        if not isinstance(echo, dict) or not echo.get("name"):
            continue
        docs.append({
            "id": f"echo:{key}",
            "kind": "echo",
            "title": clean(echo.get("name")),
            "text": "｜".join(filter(None, [
                f"{clean(echo.get('name'))}（{clean(echo.get('name_en'))}）",
                "回响",
                clean(echo.get("rarity")),
                f"效果：{clean(echo.get('effect'))}",
                f"打法：{clean(echo.get('playstyle'))}",
                f"适配：{join(echo.get('best_for') or [])}",
                f"PVP：{clean(echo.get('tier_pvp'))}",
                f"PVE：{clean(echo.get('tier_pve'))}",
            ])),
            "tags": echo.get("tags") or [],
            "source": "game_data.json",
        })
    return docs


def rule_docs(data: dict) -> list:
    docs = []
    for key, mode in (data.get("game_modes") or {}).items():
        if not isinstance(mode, dict) or not mode.get("name"):
            continue
        docs.append({
            "id": f"mode:{key}",
            "kind": "rule",
            "title": clean(mode.get("name")),
            "text": "｜".join(filter(None, [
                f"{clean(mode.get('name'))}（{clean(mode.get('type'))}）",
                clean(mode.get("rules")),
                f"牌组：{clean(mode.get('deck_size'))}" if mode.get("deck_size") else "",
                f"回响：{clean(mode.get('echo'))}" if mode.get("echo") else "",
                f"段位：{clean(mode.get('ranking'))}" if mode.get("ranking") else "",
                f"特性：{join(mode.get('features') or [])}",
            ])),
            "tags": ["模式", "规则"],
            "source": "game_data.json",
        })
    for key, mech in (data.get("combat_mechanics") or {}).items():
        if not isinstance(mech, dict):
            continue
        pieces = [clean(v) for k, v in mech.items() if isinstance(v, str)]
        docs.append({
            "id": f"mech:{key}",
            "kind": "rule",
            "title": key,
            "text": "｜".join(filter(None, pieces)),
            "tags": ["机制", "规则"],
            "source": "game_data.json",
        })
    return docs


def csv_docs(path: Path, kind: str, tag: str) -> list:
    docs = []
    if not path.exists():
        return docs
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 2:
                continue
            question = clean(row[0])
            answer = clean(row[1])
            if not question or not answer:
                continue
            docs.append({
                "id": f"{kind}:{len(docs)}",
                "kind": kind,
                "title": question,
                "text": f"问：{question}｜答：{answer}",
                "tags": [tag],
                "source": path.name,
            })
    return docs


def dedupe(docs: list) -> list:
    best = {}
    order = []
    for doc in docs:
        title_key = norm_key(doc.get("title"))
        if not title_key:
            continue
        kind = doc.get("kind")
        key = (kind, title_key) if kind in ("quiz", "muggle") else (kind, doc.get("id"))
        current = best.get(key)
        if current is None:
            best[key] = doc
            order.append(key)
            continue
        if "选项：" in doc.get("text", "") and "选项：" not in current.get("text", ""):
            best[key] = doc
    return [best[key] for key in order]


def build(bank_path: Path, game_path: Path, quiz_csv: Path, muggle_csv: Path) -> dict:
    docs = []
    sources = []
    if bank_path.exists():
        bank = load_json(bank_path)
        docs.extend(quiz_docs(bank))
        sources.append(str(bank_path))
    if quiz_csv.exists():
        docs.extend(csv_docs(quiz_csv, "quiz", "魔法史"))
        sources.append(str(quiz_csv))
    if muggle_csv.exists():
        docs.extend(csv_docs(muggle_csv, "muggle", "麻瓜题"))
        sources.append(str(muggle_csv))
    if game_path.exists():
        game = load_json(game_path)
        docs.extend(card_docs(game))
        docs.extend(echo_docs(game))
        docs.extend(rule_docs(game))
        sources.append(str(game_path))
    docs = dedupe(docs)
    counts = {}
    for doc in docs:
        counts[doc["kind"]] = counts.get(doc["kind"], 0) + 1
    return {
        "version": 2,
        "built": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": sources,
        "counts": counts,
        "docs": docs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", default=str(DEFAULT_BANK))
    parser.add_argument("--game", default=str(DEFAULT_GAME))
    parser.add_argument("--quiz-csv", default=str(DEFAULT_QUIZ_CSV))
    parser.add_argument("--muggle-csv", default=str(DEFAULT_MUGGLE_CSV))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    payload = build(Path(args.bank), Path(args.game), Path(args.quiz_csv), Path(args.muggle_csv))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"docs": len(payload["docs"]), "counts": payload["counts"], "out": str(out)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
