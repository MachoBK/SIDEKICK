import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


SOURCES = [
    {
        "name": "main_story",
        "url": "https://crimsondesert.pearlabyss.com/en-us/Main",
        "kind": "story"
    },
    {
        "name": "game_editions",
        "url": "https://crimsondesert.pearlabyss.com/en-us/News/Notice/Detail?_boardNo=49",
        "kind": "items"
    },
    {
        "name": "patch_1_00_03",
        "url": "https://crimsondesert.pearlabyss.com/en-us/News/Notice/Detail?_boardNo=73",
        "kind": "patch"
    },
    {
        "name": "patch_1_01_00",
        "url": "https://crimsondesert.pearlabyss.com/en-us/News/Notice/Detail?_boardNo=76",
        "kind": "patch"
    },
    {
        "name": "patch_1_02_00",
        "url": "https://crimsondesert.pearlabyss.com/en-US/News/Notice/Detail?_boardNo=80",
        "kind": "patch"
    }
]


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n")
    return text


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def normalize_name(text: str) -> str:
    text = text or ""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def text_contains_name(text: str, name: str) -> bool:
    if not text or not name:
        return False

    escaped = re.escape(name)
    pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def safe_slug(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def build_aliases(name: str) -> list[str]:
    aliases = set()
    aliases.add(name)

    if "'" in name:
        aliases.add(name.replace("'", "’"))
        aliases.add(name.replace("'", ""))

    if "’" in name:
        aliases.add(name.replace("’", "'"))
        aliases.add(name.replace("’", ""))

    return sorted(alias for alias in aliases if alias.strip())


def make_record(
    name,
    category,
    description,
    source_url,
    source_name,
    tags=None,
    aliases=None,
    confidence="high",
    notes=None,
):
    tags = tags or []
    aliases = aliases or build_aliases(name)
    notes = notes or ""

    return {
        "id": f"{category}_{safe_slug(name)}",
        "name": name,
        "category": category,
        "description": description,
        "aliases": aliases,
        "tags": sorted({str(tag).strip().lower() for tag in tags if str(tag).strip()}),
        "notes": notes,
        "source_type": "official",
        "source_name": source_name,
        "source_url": source_url,
        "confidence": confidence,
        "last_verified": datetime.now(timezone.utc).date().isoformat(),
    }


def merge_record(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)

    merged_aliases = set(existing.get("aliases", [])) | set(incoming.get("aliases", []))
    merged_tags = set(existing.get("tags", [])) | set(incoming.get("tags", []))

    merged["aliases"] = sorted(a for a in merged_aliases if a)
    merged["tags"] = sorted(t for t in merged_tags if t)

    if incoming.get("description") and (
        not existing.get("description") or len(incoming["description"]) > len(existing["description"])
    ):
        merged["description"] = incoming["description"]

    if incoming.get("notes"):
        existing_notes = existing.get("notes", "").strip()
        incoming_notes = incoming.get("notes", "").strip()

        if existing_notes and incoming_notes and incoming_notes not in existing_notes:
            merged["notes"] = f"{existing_notes} | {incoming_notes}"
        elif incoming_notes:
            merged["notes"] = incoming_notes

    # Keep last verified fresh
    merged["last_verified"] = incoming.get("last_verified", existing.get("last_verified"))

    return merged


def add_unique(records, record):
    key = (normalize_name(record["name"]), record["category"])

    for i, existing in enumerate(records):
        existing_key = (normalize_name(existing["name"]), existing["category"])
        if key == existing_key:
            records[i] = merge_record(existing, record)
            return

    records.append(record)


def parse_main_story(text: str, source_url: str, source_name: str):
    records = []

    known_characters = [
        ("Kliff", ["protagonist", "lead"]),
        ("Oongka", ["character"]),
        ("Yann", ["character"]),
        ("Naira", ["character"]),
        ("Myurdin", ["character"]),
    ]

    known_factions = [
        ("Greymanes", ["faction", "allies"]),
        ("Black Bears", ["faction", "enemy"]),
    ]

    known_regions = [
        ("Pywel", ["world", "region"]),
        ("Pailune", ["region"]),
    ]

    for name, tags in known_characters:
        if text_contains_name(text, name):
            add_unique(
                records,
                make_record(
                    name=name,
                    category="character",
                    description=f"Officially named character found on the main Crimson Desert story page: {name}.",
                    source_url=source_url,
                    source_name=source_name,
                    tags=tags,
                )
            )

    for name, tags in known_factions:
        if text_contains_name(text, name):
            add_unique(
                records,
                make_record(
                    name=name,
                    category="faction",
                    description=f"Officially named faction found on the main Crimson Desert story page: {name}.",
                    source_url=source_url,
                    source_name=source_name,
                    tags=tags,
                )
            )

    for name, tags in known_regions:
        if text_contains_name(text, name):
            add_unique(
                records,
                make_record(
                    name=name,
                    category="region",
                    description=f"Officially named world/location found on the main Crimson Desert story page: {name}.",
                    source_url=source_url,
                    source_name=source_name,
                    tags=tags,
                )
            )

    return records


def parse_game_editions(text: str, source_url: str, source_name: str):
    records = []

    items = [
        ("Khaled Shield", "gear", ["edition", "shield"]),
        ("Grotevant Plate Set", "gear", ["edition", "armor"]),
        ("Balgran Shield", "gear", ["edition", "shield"]),
        ("Kairos Plate Set", "gear", ["edition", "armor"]),
        ("Exclaire Horse Tack Set", "gear", ["edition", "mount", "horse"]),
        ("Tormented Soul Bow", "weapon", ["edition", "weapon", "bow"]),
        ("Derictus Spear", "weapon", ["edition", "weapon", "spear"]),
        ("Sielos Longsword", "weapon", ["edition", "weapon", "sword"]),
        ("Shroud Lantern", "item", ["edition", "item"]),
        ("Hyperion Horse Tack Set", "gear", ["edition", "mount", "horse"]),
    ]

    for name, category, tags in items:
        if text_contains_name(text, name):
            add_unique(
                records,
                make_record(
                    name=name,
                    category=category,
                    description=f"Officially named edition or pre-order item: {name}.",
                    source_url=source_url,
                    source_name=source_name,
                    tags=tags,
                )
            )

    return records


def parse_patch_notes(text: str, source_url: str, source_name: str):
    records = []

    patch_entities = [
        ("Reunion", "quest", "Officially named quest mentioned in patch notes.", ["quest"]),
        ("Mysterious Pot", "quest", "Officially named quest mentioned in patch notes.", ["quest"]),
        ("Turnali's Request", "quest", "Officially named quest mentioned in patch notes.", ["quest"]),
        ("Bekker Shield", "gear", "Officially named shield/item mentioned in patch notes.", ["gear", "shield"]),
        ("Howling Hill Camp", "location", "Officially named location or camp mentioned in patch notes.", ["location", "camp"]),
        ("Hernand", "location", "Officially named location mentioned in patch notes.", ["location"]),
        ("Abyss Nexus", "system", "Officially named travel or system feature mentioned in patch notes.", ["system", "travel"]),
        ("Pailune", "region", "Officially named region mentioned in patch notes.", ["region"]),
        ("Healing Force Palm", "skill", "Officially named skill mentioned in patch notes.", ["skill"]),
        ("Aerial Force Palm", "skill", "Officially named skill mentioned in patch notes.", ["skill"]),
        ("Light Reflection", "skill", "Officially named skill mentioned in patch notes.", ["skill"]),
        ("Abyss Artifact", "item", "Officially named item or system object mentioned in patch notes.", ["item"]),
        ("Abyss Skybridge Gates", "system", "Officially named system or location feature mentioned in patch notes.", ["system"]),
        ("Double Boost", "ability", "Officially named horse ability mentioned in patch notes.", ["ability", "mount"]),
        ("Demeniss Castle", "location", "Officially named location mentioned in patch notes.", ["location", "castle"]),
    ]

    mounts = [
        "White Bear",
        "Silver Fang",
        "Snowwhite Deer",
        "Rock Tusk Warthog",
        "Icicle Edge Alpine Ibex",
        "Blackstar",
    ]

    other_items = [
        ("Refinement Token", "item", "Officially named item mentioned in patch notes or known issues.", ["item"]),
        ("Constellation Helm", "gear", "Officially named gear mentioned in known issues.", ["gear", "helm"]),
        ("A.T.A.G.", "enemy", "Officially named enemy or object mentioned in known issues.", ["enemy"]),
        ("Damiane", "character", "Officially named character mentioned in official notices.", ["character"]),
        ("Duo", "minigame", "Officially named minigame mentioned in patch notes.", ["minigame"]),
    ]

    for name, category, description, tags in patch_entities:
        if text_contains_name(text, name):
            add_unique(
                records,
                make_record(
                    name=name,
                    category=category,
                    description=description,
                    source_url=source_url,
                    source_name=source_name,
                    tags=tags,
                )
            )

    for name in mounts:
        if text_contains_name(text, name):
            add_unique(
                records,
                make_record(
                    name=name,
                    category="mount",
                    description=f"Officially named mount mentioned in official patch notes or known issues: {name}.",
                    source_url=source_url,
                    source_name=source_name,
                    tags=["mount"],
                )
            )

    for name, category, description, tags in other_items:
        if text_contains_name(text, name):
            add_unique(
                records,
                make_record(
                    name=name,
                    category=category,
                    description=description,
                    source_url=source_url,
                    source_name=source_name,
                    tags=tags,
                )
            )

    return records


def parse_source(source: dict, text: str):
    kind = source["kind"]
    source_url = source["url"]
    source_name = source["name"]

    if kind == "story":
        return parse_main_story(text, source_url, source_name)

    if kind == "items":
        return parse_game_editions(text, source_url, source_name)

    return parse_patch_notes(text, source_url, source_name)


def build_knowledge_base():
    records = []
    source_stats = []

    for source in SOURCES:
        print(f"Fetching: {source['name']} -> {source['url']}")

        try:
            raw_text = fetch_text(source["url"])
            text = normalize_whitespace(raw_text)
            parsed = parse_source(source, text)

            for record in parsed:
                add_unique(records, record)

            source_stats.append({
                "source_name": source["name"],
                "kind": source["kind"],
                "url": source["url"],
                "records_found": len(parsed),
                "status": "ok",
            })

            print(f"  -> parsed {len(parsed)} records")

        except Exception as e:
            source_stats.append({
                "source_name": source["name"],
                "kind": source["kind"],
                "url": source["url"],
                "records_found": 0,
                "status": f"error: {str(e)}",
            })
            print(f"  -> failed: {e}")

    output = {
        "game": "Crimson Desert",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "sources_checked": len(SOURCES),
        "source_stats": source_stats,
        "records": sorted(records, key=lambda r: (r["category"], r["name"].lower())),
    }

    return output


def main():
    knowledge = build_knowledge_base()

    with open("official_knowledge.json", "w", encoding="utf-8") as f:
        json.dump(knowledge, f, indent=2, ensure_ascii=False)

    print(f"Saved official_knowledge.json with {knowledge['record_count']} records.")


if __name__ == "__main__":
    main()