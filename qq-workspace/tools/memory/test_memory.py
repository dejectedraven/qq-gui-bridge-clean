import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest import sync_spool
from store import add_message, connect, count_messages, search_messages


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.db"
        self.spool = Path(self.temp.name) / "spool.jsonl"
        entries = [
            {
                "ts": "2026-10-19T23:24:00+08:00",
                "source": "group",
                "chat": "测试群",
                "sender": "TestUser",
                "sender_id": "group:TestUser",
                "text": "@你的机器人昵称 今日天气",
            },
            {
                "ts": "2026-10-19T23:25:00+08:00",
                "source": "group",
                "chat": "测试群",
                "sender": "初研",
                "sender_id": "group:初研",
                "text": "Grindelwald, Reversed. 今日关键词：愿景、魅力、操控。",
            },
            {
                "ts": "2026-10-19T23:26:00+08:00",
                "source": "group",
                "chat": "测试群",
                "sender": "群友",
                "sender_id": "group:群友",
                "text": "这家店的火锅不错",
            },
        ]
        self.spool.write_text(
            "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_sync_and_search(self):
        stats = sync_spool(self.db, self.spool, embed_enabled=False)
        self.assertEqual(stats["added"], 3)
        conn = connect(self.db)
        results = search_messages(conn, "天气", None, 5)
        self.assertTrue(results)
        self.assertIn("天气", results[0]["text"])
        conn.close()

    def test_sync_is_idempotent(self):
        sync_spool(self.db, self.spool, embed_enabled=False)
        stats = sync_spool(self.db, self.spool, embed_enabled=False)
        self.assertEqual(stats["added"], 0)
        conn = connect(self.db)
        self.assertEqual(count_messages(conn), 3)
        conn.close()

    def test_source_is_part_of_identity(self):
        conn = connect(self.db)
        add_message(conn, "2026-10-19T23:30:00+08:00", "group", "测试群", "群友", "group:群友", "同一句话")
        add_message(conn, "2026-10-19T23:31:00+08:00", "private", "主人", "主人", "123456789", "同一句话")
        self.assertEqual(count_messages(conn, "group"), 1)
        self.assertEqual(count_messages(conn, "private"), 1)
        conn.close()


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MemoryTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
