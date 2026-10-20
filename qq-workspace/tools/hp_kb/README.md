# HPMA 知识库

群聊主题是《哈利波特：魔法觉醒》。这里把主人本地的题库与卡牌手册整理成一份只读知识库，供群聊回答时精确检索。

## 数据来源

- `HPMAMagicHistorySolver\data\bank_web.json`：网页整理的魔法史题库。
- `HPMAMagicQuiz\data\questions.csv`：主人长期积累的魔法史题库（约 1249 条），与上面按题目去重合并。
- `HPMAMagicQuiz\data\questions_muggle.csv`：麻瓜题题库（约 500 条）。
- `HPMAMagicQuiz\data\game_data.json`：卡牌 / 回响 / 伙伴 / 模式与机制手册。

来源文件只读，不改动；生成结果写在 `tools/hp_kb/data/kb.json`。当前约 2100 条：魔法史 1483、麻瓜 504、卡牌 72、伙伴 18、回响 15、规则 16。

## 重新生成

```powershell
python tools\hp_kb\build.py
```

## 检索

```powershell
python tools\hp_kb\search.py --query "厉火 费用"
python tools\hp_kb\search.py --query "1991年 草药学" --kind quiz
python tools\hp_kb\search.py --query "哈利回响" --limit 3 --json
```

`--kind` 可选 `card`、`quiz`、`muggle`、`echo`、`companion`、`rule`，默认 `all`。

## 每日一题 / 三连问

和塔罗同一套确定性逻辑：同一人同一天题面固定，第二问等于每日一题。

```powershell
python tools\hp_kb\quiz.py --user-id 123456789 --name "主人" --json
python tools\hp_kb\quiz.py --user-id 123456789 --name "主人" --spread three
python tools\hp_kb\quiz.py --user-id 123456789 --name "主人" --kind muggle --hide-answer
```

- `--hide-answer` 不返回答案，适合先让群友猜，猜完再公布。
- `--kind quiz|muggle` 可只抽魔法史或只抽麻瓜题。
- 每条带一句旁白，方便玩梗，不必当真。

## 规则

- 事实性问题（费用、数值、效果、考题答案）必须先检索，再作答；检索不到就说没查到，不编。
- 只读，不联网，不写文件。
- guest 可用，仅限 `tools/hp_kb/search.py`。

## 测试

```powershell
python tools\hp_kb\test_hp_kb.py
```
