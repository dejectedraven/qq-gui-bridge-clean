import math
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  source TEXT NOT NULL,
  chat TEXT NOT NULL DEFAULT '',
  sender TEXT NOT NULL DEFAULT '',
  sender_id TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'message',
  UNIQUE(source, chat, sender, text)
);
CREATE TABLE IF NOT EXISTS embeddings (
  message_id INTEGER PRIMARY KEY,
  model TEXT NOT NULL,
  vector TEXT NOT NULL,
  FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_source_ts ON messages(source, ts);
"""


def connect(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_message(conn, ts: str, source: str, chat: str, sender: str, sender_id: str, text: str, kind: str = "message"):
    cursor = conn.execute(
        "INSERT OR IGNORE INTO messages (ts, source, chat, sender, sender_id, text, kind) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, source, chat, sender, sender_id, text, kind),
    )
    conn.commit()
    if cursor.rowcount:
        return cursor.lastrowid, True
    row = conn.execute(
        "SELECT id FROM messages WHERE source = ? AND chat = ? AND sender = ? AND text = ?",
        (source, chat, sender, text),
    ).fetchone()
    if row:
        return row["id"], False
    return None, False


def add_embedding(conn, message_id: int, model: str, vector) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO embeddings (message_id, model, vector) VALUES (?, ?, ?)",
        (message_id, model, to_json(vector)),
    )
    conn.commit()


def to_json(vector) -> str:
    import json

    return json.dumps([float(value) for value in vector])


def normalize(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").lower())


def bigrams(value: str):
    if len(value) < 2:
        return {value} if value else set()
    return {value[index:index + 2] for index in range(len(value) - 1)}


def lexical_score(query: str, text: str) -> float:
    query_value = normalize(query)
    text_value = normalize(text)
    if not query_value or not text_value:
        return 0.0
    if query_value in text_value:
        return 1.0
    query_grams = bigrams(query_value)
    text_grams = bigrams(text_value)
    if not query_grams or not text_grams:
        return 0.0
    overlap = len(query_grams & text_grams)
    return overlap / math.sqrt(len(query_grams) * len(text_grams))


def search_messages(conn, query: str, source=None, limit: int = 8):
    sql = "SELECT id, ts, source, sender, text FROM messages"
    params = []
    if source:
        sql += " WHERE source = ?"
        params.append(source)
    sql += " ORDER BY ts DESC LIMIT 20000"
    rows = conn.execute(sql, params).fetchall()
    total = len(rows)
    results = []
    for index, row in enumerate(rows):
        score = lexical_score(query, row["text"])
        if score <= 0:
            continue
        recency = 1.0 - (index / total) if total else 0.0
        results.append({
            "ts": row["ts"],
            "source": row["source"],
            "sender": row["sender"],
            "text": row["text"],
            "score": round(score * 0.85 + recency * 0.15, 6),
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def cosine(left, right) -> float:
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def semantic_search(conn, query_vector, source=None, limit: int = 8):
    import json

    sql = """
    SELECT messages.id, messages.ts, messages.source, messages.sender, messages.text, embeddings.vector
    FROM messages JOIN embeddings ON embeddings.message_id = messages.id
    """
    params = []
    if source:
        sql += " WHERE messages.source = ?"
        params.append(source)
    sql += " ORDER BY messages.ts DESC LIMIT 20000"
    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        vector = json.loads(row["vector"])
        score = cosine(query_vector, vector)
        if score <= 0:
            continue
        results.append({
            "ts": row["ts"],
            "source": row["source"],
            "sender": row["sender"],
            "text": row["text"],
            "score": round(score, 6),
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def count_messages(conn, source=None) -> int:
    if source:
        row = conn.execute("SELECT COUNT(*) AS value FROM messages WHERE source = ?", (source,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS value FROM messages").fetchone()
    return int(row["value"])
