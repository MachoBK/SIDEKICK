import sqlite3
import json
import re
from pathlib import Path

DB_PATH = Path(__file__).parent / "synk_knowledge.db"
JSON_PATH = Path(__file__).parent / "knowledge.json"


def get_connection():
    return sqlite3.connect(DB_PATH)


def normalize_text(text):
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def content_to_search_text(content):
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False).lower()
    if isinstance(content, list):
        return json.dumps(content, ensure_ascii=False).lower()
    return str(content).lower()


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
            content TEXT,
            search_text TEXT
        )
    """)

    conn.commit()
    conn.close()


def insert_knowledge_item(cursor, item, fallback_index=0):
    item_id = item.get("id") or f"{item.get('game', 'unknown')}_{fallback_index}"
    game = item.get("game", "Unknown")
    section = item.get("section", "General")
    title = item.get("title", "Untitled")
    item_type = item.get("type", "note")
    content = item.get("content", item)

    search_text = normalize_text(
        f"{game} {section} {title} {item_type} {content_to_search_text(content)}"
    )

    cursor.execute("""
        INSERT OR REPLACE INTO knowledge
        (id, game, section, title, type, content, search_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        item_id,
        game,
        section,
        title,
        item_type,
        json.dumps(content, ensure_ascii=False),
        search_text
    ))


def load_json_to_db():
    create_tables()

    if not JSON_PATH.exists():
        print("knowledge.json not found.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    conn = get_connection()
    cursor = conn.cursor()

    # Supports:
    # 1. A single object
    # 2. A list of objects
    # 3. A file shaped like {"items": [...]}
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("items"), list):
        items = data["items"]
    else:
        items = [data]

    for index, item in enumerate(items):
        insert_knowledge_item(cursor, item, index)

    conn.commit()
    conn.close()

    print(f"Loaded {len(items)} knowledge item(s).")


def score_result(query_words, row):
    game, section, title, item_type, content, search_text = row

    score = 0
    title_text = normalize_text(title)
    section_text = normalize_text(section)
    game_text = normalize_text(game)

    for word in query_words:
        if word in title_text:
            score += 6
        if word in section_text:
            score += 4
        if word in game_text:
            score += 3
        if word in search_text:
            score += 1

    return score


def search_knowledge(query, limit=5):
    conn = get_connection()
    cursor = conn.cursor()

    query_clean = normalize_text(query)
    query_words = [word for word in query_clean.split() if len(word) > 2]

    if not query_words:
        conn.close()
        return []

    like_filters = " OR ".join(["search_text LIKE ?" for _ in query_words])
    params = [f"%{word}%" for word in query_words]

    cursor.execute(f"""
        SELECT game, section, title, type, content, search_text
        FROM knowledge
        WHERE {like_filters}
    """, params)

    rows = cursor.fetchall()
    conn.close()

    scored_rows = []

    for row in rows:
        score = score_result(query_words, row)

        if score > 0:
            scored_rows.append((score, row))

    scored_rows.sort(key=lambda item: item[0], reverse=True)

    results = []

    for score, row in scored_rows[:limit]:
        game, section, title, item_type, content, search_text = row

        results.append({
            "game": game,
            "section": section,
            "title": title,
            "type": item_type,
            "score": score,
            "content": json.loads(content)
        })

    return results