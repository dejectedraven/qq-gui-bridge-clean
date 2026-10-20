import json
import re
from datetime import datetime
from pathlib import Path

from bridge.ocr import clean_sender_name, is_level_label, is_timestamp, normalize


class MemoryRecorder:
    def __init__(self, group_spool: str, private_spool: str, max_seen: int = 50000):
        self.spools = {
            "group": Path(group_spool),
            "private": Path(private_spool),
        }
        for path in self.spools.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        self.seen = set()
        self.max_seen = max_seen
        self.current_sender = {"group": "unknown", "private": "unknown"}

    def remember(self, key) -> None:
        self.seen.add(key)
        if len(self.seen) > self.max_seen:
            self.seen = set(list(self.seen)[self.max_seen // 2:])

    def record(self, source: str, chat: str, rows) -> int:
        path = self.spools.get(source)
        if path is None:
            return 0
        sender = self.current_sender.get(source, "unknown")
        entries = []
        for row in rows:
            text = row["text"].strip()
            if not text or is_timestamp(text):
                continue
            if is_level_label(text):
                sender = clean_sender_name(text)
                self.current_sender[source] = sender
                continue
            if re.fullmatch(r"\+\d+", normalize(text)):
                continue
            key = (source, chat, sender, normalize(text))
            if key in self.seen:
                continue
            self.remember(key)
            entries.append({
                "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
                "source": source,
                "chat": chat,
                "sender": sender,
                "sender_id": "" if sender == "unknown" else f"{source}:{normalize(sender)}",
                "text": text,
            })
        if entries:
            with path.open("a", encoding="utf-8") as handle:
                for entry in entries:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return len(entries)
