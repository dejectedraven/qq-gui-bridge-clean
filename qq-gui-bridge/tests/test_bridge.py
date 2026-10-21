import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from bridge.main import (
    bottom_signature,
    build_followup_prompt,
    build_owner_prompt,
    build_prompt,
    chat_key,
    chat_state,
    classify_chat,
    clean_reply,
    count_messages,
    count_triggers,
    find_ambient_message,
    find_followup_message,
    find_private_message,
    find_sidebar_row,
    find_trigger,
    is_owner_private,
    is_pass_reply,
    is_trigger_row,
    parse_outbox_line,
    read_new_outbox_lines,
    update_handled_counts,
)
from bridge.memory import MemoryRecorder
from bridge.ocr import clean_sender_name, is_timestamp, parse_messages
from bridge.opencode_client import OpenCodeClient
from bridge.sidebar import (
    clean_title,
    conversation_entries,
    find_unread_badges,
    sidebar_entries,
    unread_entries,
)

NICKNAME = "测试昵称"


def client_config():
    return {
        "opencode": {
            "base_url": "http://127.0.0.1:41873",
            "agent": "qq-guest",
            "model": "opencode/deepseek-v4.1-flash-free",
        }
    }


def row(text, x0=0, y=0):
    return {"text": text, "x0": x0, "x1": x0 + 200, "y": y}


class TriggerTests(unittest.TestCase):
    def test_trigger_row(self):
        self.assertTrue(is_trigger_row(row("@测试昵称 今日天气"), NICKNAME, 650))
        self.assertFalse(is_trigger_row(row("LV100殿堂测试昵称"), NICKNAME, 650))
        self.assertFalse(is_trigger_row(row("12:34"), NICKNAME, 650))
        self.assertFalse(is_trigger_row(row("@测试昵称 今日天气", x0=500), NICKNAME, 650))

    def test_find_last_trigger(self):
        rows = [
            row("hello"),
            row("@测试昵称 A"),
            row("other"),
            row("@测试昵称 B"),
        ]
        self.assertEqual(find_trigger(rows, NICKNAME, 650), 3)

    def test_count_triggers(self):
        rows = [
            row("LV100殿堂禄时节"),
            row("@测试昵称 今日天气"),
            row("LV100殿堂禄时节"),
            row("@测试昵称 今日天气"),
            row("LV100殿堂禄时节"),
            row("@测试昵称 今日天气"),
        ]
        present = count_triggers(rows, NICKNAME, 650)
        self.assertEqual(present["@测试昵称今日天气"], 3)

    def test_trigger_key_survives_sender_flap(self):
        without_label = [row("@测试昵称 我喜欢你", x0=70)]
        with_label = [row("LV100殿堂禄时节", x0=60), row("@测试昵称 我喜欢你", x0=70)]
        key = "@测试昵称我喜欢你"
        self.assertEqual(count_triggers(without_label, NICKNAME, 650), {key: 1})
        self.assertEqual(count_triggers(with_label, NICKNAME, 650), {key: 1})

    def test_prime_suppresses_existing_triggers(self):
        rows = [row("LV2初研", x0=60), row("@测试昵称 早安", x0=70)]
        primed = count_triggers(rows, NICKNAME, 650)
        self.assertEqual(len(primed), 1)
        handled = dict(primed)
        update_handled_counts(handled, primed)
        self.assertEqual(handled, primed)

    def test_update_handled_counts(self):
        handled = {"@测试昵称今日天气": 2}
        update_handled_counts(handled, {"@测试昵称今日天气": 1})
        self.assertEqual(handled["@测试昵称今日天气"], 1)
        update_handled_counts(handled, {})
        self.assertNotIn("@测试昵称今日天气", handled)

    def test_clean_sender_name(self):
        self.assertEqual(clean_sender_name("LV100殿堂禄时节"), "禄时节")
        self.assertEqual(clean_sender_name("LV94殿堂厄普克拉（十张月卡真君）"), "厄普克拉（十张月卡真君）")
        self.assertEqual(clean_sender_name("禄时节"), "禄时节")
        self.assertEqual(clean_sender_name(""), "unknown")
        self.assertEqual(clean_sender_name("LV100殿堂"), "unknown")

    def test_bottom_signature(self):
        rows = [row("a"), row("b"), row(" c ")]
        self.assertEqual(bottom_signature(rows, 2), ("b", "c"))

    def test_build_prompt(self):
        config = {"trigger": {"group_name": "嘛咪哄养老院", "max_context_messages": 2}}
        rows = [row("OLDCONTEXT"), row("LV100殿堂禄时节"), row("@测试昵称 今日天气")]
        prompt = build_prompt(rows, 2, config, "LV100殿堂禄时节")
        self.assertIn("[QQ] tier=guest", prompt)
        self.assertIn("sender_qq=group:禄时节", prompt)
        self.assertIn("嘛咪哄养老院", prompt)
        self.assertIn("@测试昵称 今日天气", prompt)
        self.assertNotIn("OLDCONTEXT", prompt)


class MessageTests(unittest.TestCase):
    def test_parse_messages_marks_self(self):
        rows = [
            row("LV100劳模测试昵称", x0=60),
            row("@测试昵称 今日天气", x0=70),
            row("LV2初研", x0=600),
            row("Grindelwald，逆位。", x0=70),
            row("+1", x0=70),
        ]
        messages = parse_messages(rows, 650)
        self.assertEqual(len(messages), 2)
        self.assertFalse(messages[0]["self"])
        self.assertEqual(messages[0]["sender"], "劳模测试昵称")
        self.assertTrue(messages[1]["self"])
        self.assertEqual(messages[1]["sender"], "初研")

    def test_count_messages_excludes_self(self):
        messages = [
            {"sender": "A", "self": False, "text": "hello"},
            {"sender": "初研", "self": True, "text": "reply"},
            {"sender": "A", "self": False, "text": "hello"},
        ]
        counts = count_messages(messages)
        self.assertEqual(counts[("A", "hello")], 2)

    def test_find_ambient_message(self):
        messages = [
            {"sender": "A", "self": False, "text": "今天天气不错"},
            {"sender": "B", "self": False, "text": "@测试昵称 今日天气"},
            {"sender": "初研", "self": True, "text": "..."},
        ]
        self.assertEqual(find_ambient_message(messages, NICKNAME)["text"], "今天天气不错")

    def test_is_pass_reply(self):
        self.assertTrue(is_pass_reply("[PASS]"))
        self.assertTrue(is_pass_reply("pass"))
        self.assertFalse(is_pass_reply("好呀"))

    def test_find_followup_message(self):
        messages = [
            {"sender": "A", "self": False, "text": "@测试昵称 今日天气"},
            {"sender": "A", "self": False, "text": "什么意思"},
            {"sender": "初研", "self": True, "text": "[你]: 天气不错……"},
        ]
        self.assertEqual(find_followup_message(messages, NICKNAME, "A")["text"], "什么意思")
        self.assertIsNone(find_followup_message(messages, NICKNAME, "B"))
        self.assertIsNone(find_followup_message(messages, NICKNAME, ""))

    def test_build_followup_prompt(self):
        config = {"trigger": {"group_name": "嘛咪哄养老院"}, "ambient": {"context_messages": 12}}
        messages = [
            {"sender": "A", "self": False, "text": "什么意思"},
            {"sender": "初研", "self": True, "text": "天气不错……"},
        ]
        prompt = build_followup_prompt(messages, config, "A")
        self.assertIn("[QQ] tier=guest", prompt)
        self.assertIn("sender_qq=group:A", prompt)
        self.assertIn("msg_id=followup-", prompt)
        self.assertIn("[你]: 天气不错……", prompt)
        self.assertIn("什么意思", prompt)

    def test_classify_chat(self):
        config = {
            "trigger": {"group_name": "嘛咪哄养老院", "group_match": "养老院"},
            "memory": {"private_match": "Raven"},
        }
        self.assertEqual(classify_chat("嘛咪哄养老院(64)", config), "group")
        self.assertEqual(classify_chat("Raven", config), "private")
        self.assertEqual(classify_chat("别的东西", config), "other")

    def test_is_timestamp(self):
        self.assertTrue(is_timestamp("12:34"))
        self.assertTrue(is_timestamp("昨天23:58"))
        self.assertTrue(is_timestamp("星期天 9:05".replace(" ", "")))
        self.assertFalse(is_timestamp("明天8:00见"))
        self.assertFalse(is_timestamp("hello"))

    def test_parse_messages_private_self_by_position(self):
        rows = [
            row("帮我看看服务器", x0=70, y=1),
            row("好的主人", x0=420, y=2),
            row("顺便看看磁盘", x0=75, y=3),
        ]
        messages = parse_messages(rows, 650)
        self.assertEqual(len(messages), 3)
        self.assertFalse(messages[0]["self"])
        self.assertTrue(messages[1]["self"])
        self.assertFalse(messages[2]["self"])

    def test_parse_messages_self_by_right_edge(self):
        wide = row("我的长回复，一直写到右边", x0=70, y=1)
        wide["x1"] = 868
        incoming = row("主人的短消息", x0=69, y=2)
        incoming["x1"] = 474
        messages = parse_messages([wide, incoming], 650)
        self.assertTrue(messages[0]["self"])
        self.assertFalse(messages[1]["self"])

    def test_parse_messages_self_by_bubble_color(self):
        image = np.full((140, 650, 3), 245, dtype=np.uint8)
        image[30:60, 60:400] = (255, 235, 204)
        rows = [row("蓝气泡是我的", x0=70, y=45), row("灰气泡是主人的", x0=70, y=110)]
        messages = parse_messages(rows, 650, image=image)
        self.assertTrue(messages[0]["self"])
        self.assertFalse(messages[1]["self"])

    def test_is_owner_private(self):
        config = {"memory": {"private_match": "Raven"}}
        self.assertTrue(is_owner_private("Raven", config))
        self.assertTrue(is_owner_private(" Raven ", config))
        self.assertFalse(is_owner_private("嘛咪哄养老院(64)", config))
        self.assertFalse(is_owner_private("", config))

    def test_find_private_message(self):
        messages = [
            {"sender": "unknown", "self": False, "text": "帮我看下服务器状态"},
            {"sender": "unknown", "self": True, "text": "好的主人"},
            {"sender": "unknown", "self": False, "text": "顺便看看磁盘"},
        ]
        self.assertEqual(find_private_message(messages)["text"], "顺便看看磁盘")
        self.assertIsNone(find_private_message([{"sender": "unknown", "self": True, "text": "x"}]))
        self.assertIsNone(find_private_message([]))

    def test_build_owner_prompt(self):
        config = {
            "qq": {"owner_qq": "123456789"},
            "trigger": {"group_name": "嘛咪哄养老院"},
            "ambient": {"context_messages": 12},
        }
        messages = [
            {"sender": "unknown", "self": False, "text": "帮我看下磁盘"},
            {"sender": "unknown", "self": True, "text": "好的主人"},
        ]
        prompt = build_owner_prompt(messages, config)
        self.assertIn("[QQ] tier=owner", prompt)
        self.assertIn("sender_qq=123456789", prompt)
        self.assertIn("msg_id=private-", prompt)
        self.assertIn("[你]: 好的主人", prompt)
        self.assertIn("帮我看下磁盘", prompt)
        self.assertIn("notify.py --to owner", prompt)


class MemoryRecorderTests(unittest.TestCase):
    def test_records_message_with_sender(self):
        with tempfile.TemporaryDirectory() as tmp:
            group_spool = Path(tmp) / "group.jsonl"
            private_spool = Path(tmp) / "private.jsonl"
            recorder = MemoryRecorder(str(group_spool), str(private_spool))
            rows = [
                {"text": "LV100劳模测试昵称", "x0": 60, "y": 1},
                {"text": "@测试昵称 今日天气", "x0": 70, "y": 2},
                {"text": "12:34", "x0": 300, "y": 3},
                {"text": "+1", "x0": 70, "y": 4},
            ]
            self.assertEqual(recorder.record("group", "嘛咪哄养老院", rows), 1)
            lines = group_spool.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data["sender"], "劳模测试昵称")
            self.assertIn("今日天气", data["text"])

    def test_private_and_group_spools_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            group_spool = Path(tmp) / "group.jsonl"
            private_spool = Path(tmp) / "private.jsonl"
            recorder = MemoryRecorder(str(group_spool), str(private_spool))
            rows = [{"text": "LV100主人", "x0": 60, "y": 1}, {"text": "今晚早点睡", "x0": 70, "y": 2}]
            self.assertEqual(recorder.record("private", "主人", rows), 1)
            self.assertFalse(group_spool.exists() and group_spool.read_text(encoding="utf-8"))
            self.assertTrue(private_spool.read_text(encoding="utf-8"))


class ReplyTests(unittest.TestCase):
    def test_clean_markdown(self):
        value = clean_reply("**今日牌**：`分院仪式`\n\n- 选择\n- 归属", 500)
        self.assertIn("今日牌", value)
        self.assertNotIn("**", value)
        self.assertNotIn("`", value)
        self.assertNotIn("- 选择", value)

    def test_truncate(self):
        self.assertEqual(clean_reply("x" * 10, 5), "xxxxx…")


class SessionStateTests(unittest.TestCase):
    def test_session_title(self):
        client = OpenCodeClient(client_config())
        self.assertEqual(client.session_title("qq-owner"), "qq-bridge-owner")
        self.assertEqual(client.session_title("qq-guest"), "qq-bridge-guest")

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "sessions.json")
            client = OpenCodeClient(client_config(), state_path=path)
            client.session_cache["qq-owner"] = "ses_test"
            client._save_state()
            again = OpenCodeClient(client_config(), state_path=path)
            self.assertEqual(again.session_cache.get("qq-owner"), "ses_test")

    def test_corrupt_state_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sessions.json"
            path.write_text("{not json", encoding="utf-8")
            client = OpenCodeClient(client_config(), state_path=str(path))
            self.assertEqual(client.session_cache, {})


class OutboxTests(unittest.TestCase):
    def test_parse_outbox_line(self):
        line = '{"target": "group", "text": "晚安", "ts": "2026-10-20T00:30:00+08:00"}'
        self.assertEqual(parse_outbox_line(line), {"target": "group", "text": "晚安"})
        self.assertIsNone(parse_outbox_line(""))
        self.assertIsNone(parse_outbox_line("not json"))
        self.assertIsNone(parse_outbox_line('{"target": "other", "text": "x"}'))
        self.assertIsNone(parse_outbox_line('{"target": "group", "text": "   "}'))

    def test_parse_outbox_line_image(self):
        line = '{"target": "owner", "text": "", "image": "D:\\\\tmp\\\\a.png"}'
        self.assertEqual(
            parse_outbox_line(line),
            {"target": "owner", "text": "", "image": "D:\\tmp\\a.png"},
        )
        caption = '{"target": "owner", "text": "看这个", "image": "D:\\\\tmp\\\\a.png"}'
        self.assertEqual(
            parse_outbox_line(caption),
            {"target": "owner", "text": "看这个", "image": "D:\\tmp\\a.png"},
        )
        self.assertIsNone(parse_outbox_line('{"target": "group", "text": ""}'))

    def test_read_new_outbox_lines_incremental(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outbox.jsonl"
            state = {"offset": 0, "path": str(path)}
            path.write_text('{"target": "owner", "text": "一"}\n', encoding="utf-8")
            first = read_new_outbox_lines(state, path)
            self.assertEqual([entry["text"] for entry in first], ["一"])
            self.assertEqual(read_new_outbox_lines(state, path), [])
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"target": "group", "text": "二"}\n')
                handle.write('{"target": "group", "text": "半')
            second = read_new_outbox_lines(state, path)
            self.assertEqual([entry["text"] for entry in second], ["二"])
            with path.open("a", encoding="utf-8") as handle:
                handle.write('行"}\n')
            third = read_new_outbox_lines(state, path)
            self.assertEqual([entry["text"] for entry in third], ["半行"])

    def test_find_sidebar_row(self):
        rows = [
            row("Raven", x0=90, y=143),
            row("喂，主人，就甩我一个…", x0=100, y=165),
            row("嘛咪哄养老院", x0=90, y=215),
            row("12:34", x0=250, y=215),
        ]
        hit = find_sidebar_row(rows, "养老院")
        self.assertAlmostEqual(hit["y"], 215)
        self.assertAlmostEqual(hit["x"], 190)
        self.assertEqual(find_sidebar_row(rows, "Raven")["y"], 143)
        self.assertIsNone(find_sidebar_row(rows, "不存在"))
        self.assertIsNone(find_sidebar_row(rows, ""))
        self.assertIsNone(find_sidebar_row(rows, "12:34"))


class SidebarTests(unittest.TestCase):
    def sidebar_rows(self):
        return [
            row("Raven01:54", x0=64, y=13),
            row("让你修复这个漏洞，能兼顾私..", x0=65, y=35),
            row("嘛咪哄养老院01:51", x0=64, y=77),
            row("[有人@我]测试昵称：@子1", x0=65, y=99),
            row("QQ游戏中心05/22", x0=65, y=141),
            row("预约解锁异人夏禾带走礼包", x0=64, y=163),
        ]

    def test_clean_title(self):
        self.assertEqual(clean_title("嘛咪哄养老院01:51"), "嘛咪哄养老院")
        self.assertEqual(clean_title("Raven昨天"), "Raven")
        self.assertEqual(clean_title("QQ游戏中心05/22"), "QQ游戏中心")
        self.assertEqual(clean_title("Raven"), "Raven")

    def test_conversation_entries(self):
        entries = conversation_entries(self.sidebar_rows())
        self.assertEqual([entry["title"] for entry in entries], ["Raven", "嘛咪哄养老院", "QQ游戏中心"])
        self.assertFalse(entries[0]["unread"])
        self.assertTrue(entries[1]["unread"])

    def test_sidebar_entries_marks_badge(self):
        badges = [{"x": 218.0, "y": 92.0, "w": 16, "h": 16}]
        entries = sidebar_entries(self.sidebar_rows(), badges)
        self.assertTrue(entries[1]["badge"])
        self.assertTrue(entries[1]["unread"])
        self.assertFalse(entries[1]["preview"].endswith("1"))
        self.assertFalse(entries[0]["badge"])

    def test_find_unread_badges_filters_left_pixels(self):
        image = np.zeros((200, 250, 3), dtype=np.uint8)
        cv2.circle(image, (220, 92), 8, (60, 60, 240), -1)
        cv2.circle(image, (30, 92), 8, (60, 60, 240), -1)
        badges = find_unread_badges(image)
        self.assertEqual(len(badges), 1)
        self.assertAlmostEqual(badges[0]["y"], 92, delta=2)

    def test_unread_entries_ignore(self):
        entries = [
            {"title": "嘛咪哄养老院", "unread": True},
            {"title": "QQ游戏中心", "unread": True},
            {"title": "Raven", "unread": False},
        ]
        result = unread_entries(entries, ["QQ游戏中心"])
        self.assertEqual([entry["title"] for entry in result], ["嘛咪哄养老院"])


class ChatStateTests(unittest.TestCase):
    def test_chat_key(self):
        self.assertEqual(chat_key("嘛咪哄养老院(64)", "group"), "group")
        self.assertEqual(chat_key("Raven", "private"), "private:Raven")

    def test_chat_state_isolated_per_chat(self):
        states = {}
        group = chat_state(states, "group")
        private = chat_state(states, "private:Raven")
        group["triggers"]["@我"] = 1
        self.assertEqual(private["triggers"], {})
        self.assertIsNone(private["signature"])
        self.assertIs(chat_state(states, "group"), group)


if __name__ == "__main__":
    unittest.main()
