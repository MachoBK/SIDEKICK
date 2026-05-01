import os
import json
import numpy as np
import faiss
from pathlib import Path
from openai import OpenAI

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "knowledge.json"
INDEX_PATH = BASE_DIR / "synk.index"
META_PATH = BASE_DIR / "synk_meta.json"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"


def embed_texts(texts: list[str]) -> list[list[float]]:
    res = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [d.embedding for d in res.data]


def normalize_items(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]

    if isinstance(data, dict) and isinstance(data.get("records"), list):
        game = data.get("game", "Unknown")
        converted = []

        for record in data["records"]:
            converted.append({
                "id": record.get("id"),
                "game": game,
                "section": record.get("category", "General"),
                "title": record.get("name", "Untitled"),
                "type": record.get("category", "note"),
                "content": {
                    "name": record.get("name"),
                    "category": record.get("category"),
                    "description": record.get("description"),
                    "aliases": record.get("aliases", []),
                    "tags": record.get("tags", []),
                    "notes": record.get("notes", ""),
                    "confidence": record.get("confidence"),
                    "source_type": record.get("source_type"),
                    "source_name": record.get("source_name"),
                    "last_verified": record.get("last_verified"),
                }
            })

        return converted

    return [data]


def item_to_text(item: dict) -> str:
    parts = [
        f"game: {item.get('game', '')}",
        f"section: {item.get('section', '')}",
        f"title: {item.get('title', '')}",
        f"type: {item.get('type', '')}",
    ]

    content = item.get("content", {})

    if isinstance(content, dict):
        for key, value in content.items():
            parts.append(f"{key}: {value}")
    elif isinstance(content, list):
        for value in content:
            parts.append(f"- {value}")
    else:
        parts.append(str(content))

    return "\n".join(parts)


def build_index():
    if not DATA_PATH.exists():
        raise FileNotFoundError("knowledge.json not found")

    with open(DATA_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    items = normalize_items(data)

    if not items:
        raise ValueError("No knowledge items found.")

    texts = [item_to_text(item) for item in items]

    embeddings = embed_texts(texts)
    vectors = np.array(embeddings).astype("float32")

    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, str(INDEX_PATH))

    with open(META_PATH, "w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)

    print(f"Built SYNK vector index with {len(items)} item(s).")


def load_index():
    if not INDEX_PATH.exists() or not META_PATH.exists():
        build_index()

    index = faiss.read_index(str(INDEX_PATH))

    with open(META_PATH, "r", encoding="utf-8") as file:
        items = json.load(file)

    return index, items


def query_index(query: str, k: int = 5):
    index, items = load_index()

    query_embedding = embed_texts([query])[0]
    query_vector = np.array([query_embedding]).astype("float32")

    faiss.normalize_L2(query_vector)

    scores, indexes = index.search(query_vector, k)

    results = []

    for score, item_index in zip(scores[0], indexes[0]):
        if item_index < 0:
            continue

        item = items[item_index]

        results.append({
            "game": item.get("game", "Unknown"),
            "section": item.get("section", "General"),
            "title": item.get("title", "Untitled"),
            "type": item.get("type", "note"),
            "score": float(score),
            "content": item.get("content", item),
        })

    return results