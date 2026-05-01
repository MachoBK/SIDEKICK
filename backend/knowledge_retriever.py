import json
import os
import re
from collections import defaultdict


KNOWLEDGE_FILE = "official_knowledge.json"

CATEGORY_HINTS = {
    "gear": ["gear", "armor", "set", "shield", "tack", "equipment"],
    "weapon": ["weapon", "weapons", "sword", "bow", "spear", "blade"],
    "item": ["item", "items", "token", "artifact", "lantern", "object"],
    "quest": ["quest", "quests", "mission", "missions", "objective"],
    "location": ["location", "locations", "camp", "castle", "hill", "town", "fort"],
    "region": ["region", "regions", "world", "area", "zone", "land"],
    "character": ["character", "characters", "person", "hero", "npc"],
    "faction": ["faction", "factions", "group", "army", "clan"],
    "mount": ["mount", "mounts", "horse", "animal", "ride"],
    "skill": ["skill", "skills", "ability", "move", "technique"],
    "system": ["system", "systems", "feature", "mechanic", "travel", "nexus"],
    "enemy": ["enemy", "enemies", "foe", "monster", "target", "boss", "bosses"],
    "minigame": ["minigame", "game", "activity"],
    "ability": ["ability", "abilities", "boost", "perk"],
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "to", "for", "of", "on", "in",
    "at", "by", "with", "from", "up", "about", "into", "over", "after", "before", "under",
    "what", "which", "who", "when", "where", "why", "how", "is", "are", "was", "were", "be",
    "can", "could", "should", "would", "do", "does", "did", "tell", "me", "my", "i", "you",
    "we", "they", "them", "this", "that", "these", "those", "it", "its", "as", "all", "any",
    "just", "please", "give", "show", "list", "name", "known"
}


def load_official_knowledge():
    if not os.path.exists(KNOWLEDGE_FILE):
        return {"records": []}

    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("records"), list):
                return data
    except Exception as e:
        print(f"Failed to load {KNOWLEDGE_FILE}: {e}")

    return {"records": []}


def tokenize(text: str):
    if not text:
        return []
    return re.findall(r"[a-zA-Z0-9']+", text.lower())


def meaningful_tokens(text: str):
    return [token for token in tokenize(text) if token not in STOP_WORDS and len(token) > 1]


def normalize_text(text: str) -> str:
    return " ".join(tokenize(text))


def normalize_record(record: dict) -> dict:
    """
    Ensures each record has consistent searchable fields.
    """
    if not isinstance(record, dict):
        return {
            "name": "Unknown",
            "category": "unknown",
            "description": "",
            "aliases": [],
            "tags": [],
            "_raw": record,
        }

    normalized = dict(record)

    normalized["name"] = str(record.get("name", "Unknown")).strip()
    normalized["category"] = str(record.get("category", "unknown")).strip().lower()
    normalized["description"] = str(record.get("description", "")).strip()

    aliases = record.get("aliases", [])
    if not isinstance(aliases, list):
        aliases = [str(aliases)]
    normalized["aliases"] = [str(a).strip() for a in aliases if str(a).strip()]

    tags = record.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)]
    normalized["tags"] = [str(t).strip().lower() for t in tags if str(t).strip()]

    normalized["_raw"] = record
    return normalized


def detect_category_filters(user_input: str):
    text = user_input.lower()
    matched_categories = set()

    for category, hints in CATEGORY_HINTS.items():
        if any(hint in text for hint in hints):
            matched_categories.add(category)

    return matched_categories


def exact_name_match_score(user_input: str, record_name: str) -> int:
    query = normalize_text(user_input)
    name = normalize_text(record_name)

    if not query or not name:
        return 0

    if query == name:
        return 120

    if name in query:
        return 55

    if query in name:
        return 35

    return 0


def alias_match_score(user_input: str, aliases: list[str]) -> int:
    query = normalize_text(user_input)
    best = 0

    for alias in aliases:
        normalized_alias = normalize_text(alias)
        if not normalized_alias:
            continue

        if query == normalized_alias:
            best = max(best, 110)
        elif normalized_alias in query:
            best = max(best, 45)
        elif query in normalized_alias:
            best = max(best, 28)

    return best


def token_overlap_score(query_tokens, text: str, weight: int) -> int:
    if not text:
        return 0

    text_tokens = set(tokenize(text))
    score = 0

    for token in query_tokens:
        if token in text_tokens:
            score += weight

    return score


def fuzzy_token_bonus(query_tokens, text: str, weight: int = 2) -> int:
    """
    Gives light credit for partial token prefix matches.
    Example: 'progres' vs 'progression'
    """
    if not text:
        return 0

    text_tokens = set(tokenize(text))
    score = 0

    for q in query_tokens:
        for t in text_tokens:
            if q == t:
                continue
            if len(q) >= 4 and (t.startswith(q) or q.startswith(t)):
                score += weight
                break

    return score


def category_bonus(record_category: str, requested_categories: set) -> int:
    if not requested_categories:
        return 0
    return 20 if record_category in requested_categories else -6


def tags_score(query_tokens, tags: list[str]) -> int:
    if not tags:
        return 0

    tag_text = " ".join(tags)
    return token_overlap_score(query_tokens, tag_text, 5)


def multi_field_text(record: dict) -> str:
    parts = [
        record.get("name", ""),
        record.get("category", ""),
        record.get("description", ""),
        " ".join(record.get("aliases", [])),
        " ".join(record.get("tags", [])),
    ]

    for extra_key in ["summary", "details", "notes", "region", "type", "source"]:
        extra_value = record.get(extra_key)
        if isinstance(extra_value, str):
            parts.append(extra_value)
        elif isinstance(extra_value, list):
            parts.extend(str(x) for x in extra_value)
        elif isinstance(extra_value, dict):
            parts.extend(f"{k} {v}" for k, v in extra_value.items())

    return " ".join(part for part in parts if part)


def score_record(user_input: str, query_tokens, record, requested_categories: set):
    record = normalize_record(record)

    name = record.get("name", "")
    description = record.get("description", "")
    category = record.get("category", "").lower()
    aliases = record.get("aliases", [])
    tags = record.get("tags", [])

    full_text = multi_field_text(record)

    score = 0
    score += exact_name_match_score(user_input, name)
    score += alias_match_score(user_input, aliases)
    score += token_overlap_score(query_tokens, name, 10)
    score += token_overlap_score(query_tokens, category, 6)
    score += token_overlap_score(query_tokens, description, 4)
    score += tags_score(query_tokens, tags)
    score += token_overlap_score(query_tokens, full_text, 2)
    score += fuzzy_token_bonus(query_tokens, full_text, 2)
    score += category_bonus(category, requested_categories)

    if len(name.split()) >= 2:
        score += 2

    if description:
        score += 1

    return score


def compute_confidence_from_score(score: int) -> float:
    if score >= 120:
        return 0.98
    if score >= 90:
        return 0.94
    if score >= 65:
        return 0.88
    if score >= 45:
        return 0.79
    if score >= 28:
        return 0.68
    return 0.52


def enrich_record(record: dict, score: int) -> dict:
    enriched = normalize_record(record)
    enriched["_score"] = score
    enriched["_confidence"] = compute_confidence_from_score(score)
    return enriched


def search_official_knowledge(user_input: str, max_results: int = 8):
    knowledge = load_official_knowledge()
    records = knowledge.get("records", [])

    if not user_input.strip():
        return []

    query_tokens = meaningful_tokens(user_input)
    requested_categories = detect_category_filters(user_input)

    scored = []
    for record in records:
        score = score_record(user_input, query_tokens, record, requested_categories)
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda x: (x[0], normalize_text(x[1].get("name", ""))), reverse=True)

    results = []
    seen = set()

    for score, record in scored:
        normalized = normalize_record(record)
        key = (normalized.get("name", "").lower(), normalized.get("category", "").lower())

        if key in seen:
            continue

        seen.add(key)
        results.append(enrich_record(record, score))

        if len(results) >= max_results:
            break

    return results


def get_best_official_match(user_input: str):
    results = search_official_knowledge(user_input, max_results=1)
    if not results:
        return None
    return results[0]


def group_records_by_category(records):
    grouped = defaultdict(list)

    for record in records:
        category = record.get("category", "unknown")
        grouped[category].append(record)

    return dict(grouped)


def format_record_line(record: dict) -> str:
    name = record.get("name", "Unknown")
    category = record.get("category", "unknown")
    description = record.get("description", "No description.")
    confidence = record.get("_confidence")

    if isinstance(confidence, float):
        confidence_text = f"{round(confidence * 100)}%"
    else:
        confidence_text = "n/a"

    return f"- {name} [{category}] - {description} (official source, confidence: {confidence_text})"


def format_records_for_prompt(records):
    if not records:
        return "No directly matching official records found."

    return "\n".join(format_record_line(record) for record in records)


def get_top_record_names(records, max_names: int = 5):
    names = []
    seen = set()

    for record in records:
        name = record.get("name", "Unknown")
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        names.append(name)

        if len(names) >= max_names:
            break

    return names


def is_list_query(user_input: str) -> bool:
    text = user_input.lower().strip()

    triggers = [
        "what quests",
        "what quest",
        "what items",
        "what item",
        "what gear",
        "what weapons",
        "what weapon",
        "what mounts",
        "what mount",
        "what locations",
        "what location",
        "what regions",
        "what region",
        "what characters",
        "what character",
        "what factions",
        "what bosses",
        "what boss",
        "what do you know by name",
        "list",
        "show me",
        "name the",
        "which",
        "give me all",
        "all the",
    ]

    if any(trigger in text for trigger in triggers):
        return True

    plural_hints = [
        "quests", "items", "weapons", "mounts", "locations", "regions",
        "characters", "factions", "bosses", "systems", "skills"
    ]
    return any(hint in text for hint in plural_hints) and ("what" in text or "which" in text)


def is_direct_fact_query(user_input: str, matched_records) -> bool:
    text = user_input.lower().strip()

    if not matched_records:
        return False

    direct_prefixes = [
        "what is",
        "who is",
        "tell me about",
        "do you know anything about",
        "what do you know about",
        "explain",
        "where is",
        "what are",
    ]

    if any(text.startswith(prefix) for prefix in direct_prefixes):
        return True

    top = matched_records[0]
    top_name = top.get("name", "").lower()
    normalized_query = normalize_text(user_input)

    if top_name and normalize_text(top_name) in normalized_query:
        return True

    aliases = top.get("aliases", [])
    for alias in aliases:
        if normalize_text(alias) in normalized_query:
            return True

    top_confidence = top.get("_confidence", 0)
    return top_confidence >= 0.90 and len(matched_records) == 1


def build_direct_fact_answer(user_input: str, matched_records):
    if not matched_records:
        return None

    top = matched_records[0]
    name = top.get("name", "Unknown")
    category = top.get("category", "unknown")
    description = top.get("description", "No description available.")

    extra_parts = []

    tags = top.get("tags", [])
    if tags:
        extra_parts.append(f"Tags: {', '.join(tags[:5])}.")

    aliases = top.get("aliases", [])
    if aliases:
        extra_parts.append(f"Also known as: {', '.join(aliases[:3])}.")

    extra_text = " ".join(extra_parts).strip()

    if extra_text:
        return f"{name} is an officially named {category} in Crimson Desert. {description} {extra_text}".strip()

    return f"{name} is an officially named {category} in Crimson Desert. {description}"


def build_list_answer(user_input: str, matched_records, max_items: int = 8):
    if not matched_records:
        return None

    top_records = matched_records[:max_items]
    names = [record.get("name", "Unknown") for record in top_records if record.get("name")]

    if not names:
        return None

    category_labels = {record.get("category", "unknown") for record in top_records}
    requested_categories = detect_category_filters(user_input)

    if len(requested_categories) == 1:
        requested_label = next(iter(requested_categories))
        intro = f"Here are the official {requested_label} names I found:"
    elif len(category_labels) == 1:
        label = next(iter(category_labels))
        intro = f"Here are the official {label} names I found:"
    else:
        intro = "Here are the official named records I found:"

    body = "\n".join(f"- {name}" for name in names)
    return f"{intro}\n{body}"


def get_retrieval_summary(records: list[dict]) -> dict:
    if not records:
        return {
            "count": 0,
            "top_name": None,
            "top_category": None,
            "top_confidence": 0.0,
        }

    top = records[0]
    return {
        "count": len(records),
        "top_name": top.get("name"),
        "top_category": top.get("category"),
        "top_confidence": top.get("_confidence", 0.0),
    }