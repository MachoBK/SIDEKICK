import json
import os
from datetime import datetime

DB_FILE = "game_database.json"

_CACHE = {
    "data": None,
    "loaded_at": None,
}


def default_game_data():
    return {
        "game_info": {
            "name": "Crimson Desert",
            "world": "Pywel",
            "protagonist": "Kliff",
            "primary_faction": "Greymanes",
            "enemy_faction": "Black Bears",
        },
        "official_story_and_world": {
            "summary": [],
        },
        "official_systems": {
            "combat": [],
            "travel_and_world": [],
        },
        "official_patch_notice_terms": [],
        "assistant_rules": {
            "response_policy": [],
        },
        "regions": [],
        "quests": [],
        "gear": [],
        "enemy_archetypes": [],
        "progression_stages": [],
        "official_bosses": [],
        "community_reference": {
            "community_boss_names": [],
        },
        "meta": {
            "loaded_from": "default_fallback",
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def normalize_game_data(data: dict) -> dict:
    base = default_game_data()

    if not isinstance(data, dict):
        return base

    normalized = dict(data)

    for key, value in base.items():
        normalized.setdefault(key, value)

    normalized.setdefault("game_info", {})
    normalized["game_info"].setdefault("name", "Crimson Desert")
    normalized["game_info"].setdefault("world", "Pywel")
    normalized["game_info"].setdefault("protagonist", "Kliff")
    normalized["game_info"].setdefault("primary_faction", "Greymanes")
    normalized["game_info"].setdefault("enemy_faction", "Black Bears")

    normalized.setdefault("official_story_and_world", {})
    normalized["official_story_and_world"].setdefault("summary", [])

    normalized.setdefault("official_systems", {})
    normalized["official_systems"].setdefault("combat", [])
    normalized["official_systems"].setdefault("travel_and_world", [])

    normalized.setdefault("official_patch_notice_terms", [])
    normalized.setdefault("regions", [])
    normalized.setdefault("quests", [])
    normalized.setdefault("gear", [])
    normalized.setdefault("enemy_archetypes", [])
    normalized.setdefault("progression_stages", [])
    normalized.setdefault("official_bosses", [])

    normalized.setdefault("assistant_rules", {})
    normalized["assistant_rules"].setdefault("response_policy", [])

    normalized.setdefault("community_reference", {})
    normalized["community_reference"].setdefault("community_boss_names", [])

    normalized.setdefault("meta", {})
    normalized["meta"].setdefault("loaded_from", DB_FILE)
    normalized["meta"].setdefault("timestamp", datetime.utcnow().isoformat())

    return normalized


def load_game_facts(force_reload: bool = False) -> dict:
    global _CACHE

    if _CACHE["data"] is not None and not force_reload:
        return _CACHE["data"]

    if not os.path.exists(DB_FILE):
        print(f"[DATA LOADER] {DB_FILE} not found. Using fallback.")
        data = default_game_data()
        _CACHE["data"] = data
        _CACHE["loaded_at"] = datetime.utcnow()
        return data

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        data = normalize_game_data(raw)

        _CACHE["data"] = data
        _CACHE["loaded_at"] = datetime.utcnow()

        print(f"[DATA LOADER] Loaded {DB_FILE} successfully.")
        return data

    except Exception as e:
        print(f"[DATA LOADER] Failed to load {DB_FILE}: {e}")
        data = default_game_data()

        _CACHE["data"] = data
        _CACHE["loaded_at"] = datetime.utcnow()

        return data


def reload_game_facts() -> dict:
    return load_game_facts(force_reload=True)


def get_data_summary() -> dict:
    data = load_game_facts()

    return {
        "regions": len(data.get("regions", [])),
        "quests": len(data.get("quests", [])),
        "gear": len(data.get("gear", [])),
        "bosses": len(data.get("official_bosses", [])),
        "systems": {
            "combat": len(data.get("official_systems", {}).get("combat", [])),
            "world": len(data.get("official_systems", {}).get("travel_and_world", [])),
        },
        "loaded_at": str(_CACHE.get("loaded_at")),
        "source": data.get("meta", {}).get("loaded_from"),
    }