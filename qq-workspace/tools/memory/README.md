# Memory / RAG

给 QQ 助手提供本地长期记忆与检索。

## 数据流

```text
QQ GUI bridge
  → memory/group_spool.jsonl      群聊观察
  → memory/private_spool.jsonl    私聊观察（需打开私聊窗口并命中 private_match）
        ↓ ingest
  memory/group.db                 群聊记忆（guest 可用）
  memory/private.db               私聊记忆（仅 owner 可用）
        ↓ search
  tools/memory/search_group.py    群聊内检索（guest 唯一可用入口）
```

## 隐私边界

- `private.db` 只在主人私聊时使用；群聊回复绝不能检索或泄露私聊内容。
- guest 的权限只放行 `search_group.py`，它固定 `--db group`。
- 桥接层对群聊只检索 `group.db`。

## 命令

群聊内检索（guest 可用）：

```bash
python tools/memory/search_group.py --query "上次说的塔罗" --limit 5 --json
```

通用检索（owner / 调试）：

```bash
python tools/memory/search.py --db group --query "火锅" --limit 5
python tools/memory/search.py --db private --query "主人" --limit 5
python tools/memory/search.py --db all --query "记忆" --limit 8
```

手动写入私聊记忆（导入用）：

```bash
python tools/memory/add.py --db private --source private --sender "主人" --sender-id 123456789 --text "我习惯晚上十一点前睡觉"
python tools/memory/add.py --db private --jsonl private_chat.jsonl
```

`jsonl` 每行字段：`ts`、`source`、`chat`、`sender`、`sender_id`、`text`。

生成语义 embedding（可选，依赖本机 Ollama + `nomic-embed-text`）：

```bash
python tools/memory/ingest.py --db memory/group.db --spool memory/group_spool.jsonl --embed
python tools/memory/ingest.py --db memory/private.db --spool memory/private_spool.jsonl --embed
```

不生成 embedding 时使用词面 + 时间衰减检索，仍然可用。生成 embedding 后，`search.py` 会同时做词面检索与语义检索并合并结果；Ollama 不可用时自动退回纯词面检索。

## 测试

```bash
python tools/memory/test_memory.py
```
