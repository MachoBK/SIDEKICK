import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "synk_knowledge.db"
JSON_PATH = Path(__file__).parent / "knowledge.json"


def get_connection():
    return sqlite3.connect(DB_PATH)


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id TEXT PRIMARY KEY,
            game TEXT,
            section TEXT,
            title TEXT,
            type TEXT,
            content TEXT
        )
    """)

    conn.commit()
    conn.close()


def load_json_to_db():
    create_tables()

    if not JSON_PATH.exists():
        print("knowledge.json not found.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO knowledge
        (id, game, section, title, type, content)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get("id"),
        data.get("game"),
        data.get("section"),
        data.get("title"),
        data.get("type"),
        json.dumps(data, ensure_ascii=False)
    ))

    conn.commit()
    conn.close()


def search_knowledge(query):
    conn = get_connection()
    cursor = conn.cursor()

    search = f"%{query}%"

    cursor.execute("""
        SELECT game, section, title, content
        FROM knowledge
        WHERE content LIKE ?
           OR game LIKE ?
           OR section LIKE ?
           OR title LIKE ?
    """, (search, search, search, search))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "game": row[0],
            "section": row[1],
            "title": row[2],
            "content": json.loads(row[3])
        }
        for row in rows
    ]