from typing import Any


def safe_name(item: Any, fallback: str = "unknown") -> str:
    if isinstance(item, dict):
        return str(item.get("name", fallback))
    return str(item) if item is not None else fallback


def extract_official_names_by_category(records: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}

    for record in records:
        if not isinstance(record, dict):
            continue

        category = str(record.get("category", "unknown")).lower()
        name = str(record.get("name", "Unknown")).strip()

        if not name:
            continue

        grouped.setdefault(category, [])
        if name not in grouped[category]:
            grouped[category].append(name)

    return grouped


def build_static_world_graph(game_data: dict) -> dict[str, Any]:
    game_info = game_data.get("game_info", {})
    story = game_data.get("official_story_and_world", {})
    systems = game_data.get("official_systems", {})
    regions = game_data.get("regions", [])
    quests = game_data.get("quests", [])
    gear = game_data.get("gear", [])
    bosses = game_data.get("official_bosses", [])
    stages = game_data.get("progression_stages", [])
    enemy_archetypes = game_data.get("enemy_archetypes", [])
    community_ref = game_data.get("community_reference", {})

    protagonist = game_info.get("protagonist", "Kliff")
    primary_faction = game_info.get("primary_faction", "Greymanes")
    enemy_faction = game_info.get("enemy_faction", "Black Bears")
    world = game_info.get("world", "Pywel")

    region_names = [safe_name(r) for r in regions if safe_name(r) != "unknown"]
    quest_names = [safe_name(q) for q in quests if safe_name(q) != "unknown"]
    gear_names = [safe_name(g) for g in gear if safe_name(g) != "unknown"]
    boss_names = [safe_name(b) for b in bosses if safe_name(b) != "unknown"]
    archetype_names = [safe_name(e) for e in enemy_archetypes if safe_name(e) != "unknown"]
    stage_names = [
        str(item.get("stage", "unknown"))
        for item in stages
        if isinstance(item, dict) and item.get("stage")
    ]

    return {
        "game": {
            "name": game_info.get("name", "Crimson Desert"),
            "world": world,
            "protagonist": protagonist,
            "primary_faction": primary_faction,
            "enemy_faction": enemy_faction,
        },
        "relationships": {
            protagonist: {
                "type": "character",
                "related_to": [primary_faction, world],
                "notes": ["Main protagonist of Crimson Desert."],
            },
            primary_faction: {
                "type": "faction",
                "related_to": [protagonist, enemy_faction, world],
                "notes": ["Primary allied faction from game context."],
            },
            enemy_faction: {
                "type": "faction",
                "related_to": [primary_faction, world],
                "notes": ["Enemy faction from game context."],
            },
            world: {
                "type": "region",
                "related_to": region_names[:10],
                "notes": story.get("summary", [])[:4] if isinstance(story.get("summary", []), list) else [],
            },
            "combat": {
                "type": "system",
                "related_to": boss_names[:8] + archetype_names[:8],
                "notes": systems.get("combat", [])[:8] if isinstance(systems.get("combat", []), list) else [],
            },
            "travel_and_world": {
                "type": "system",
                "related_to": region_names[:10],
                "notes": systems.get("travel_and_world", [])[:8] if isinstance(systems.get("travel_and_world", []), list) else [],
            },
            "progression": {
                "type": "system",
                "related_to": quest_names[:8] + stage_names[:8],
                "notes": ["Progression stages and quest flow context."],
            },
            "gear": {
                "type": "system",
                "related_to": gear_names[:12],
                "notes": ["Structured gear and equipment context."],
            },
        },
        "community_reference": {
            "community_boss_names": community_ref.get("community_boss_names", [])[:10]
            if isinstance(community_ref, dict)
            else []
        }
    }


def enrich_graph_with_official_records(graph: dict, matched_records: list[dict]) -> dict:
    enriched = dict(graph)
    relationships = dict(enriched.get("relationships", {}))
    grouped = extract_official_names_by_category(matched_records)

    for category, names in grouped.items():
        key = f"official_{category}"
        relationships[key] = {
            "type": category,
            "related_to": names[:12],
            "notes": [f"Official matched {category} records from knowledge search."],
        }

        for name in names:
            if name not in relationships:
                relationships[name] = {
                    "type": category,
                    "related_to": [],
                    "notes": ["Official named record matched from official knowledge."],
                }

    enriched["relationships"] = relationships
    return enriched


def find_graph_hits(user_input: str, graph: dict) -> list[dict]:
    text = user_input.lower()
    relationships = graph.get("relationships", {})
    hits = []

    for node_name, node in relationships.items():
        node_name_lower = node_name.lower()
        if node_name_lower in text:
            hits.append({
                "node": node_name,
                "type": node.get("type", "unknown"),
                "related_to": node.get("related_to", []),
                "notes": node.get("notes", []),
                "score": 100,
            })
            continue

        score = 0
        for related in node.get("related_to", []):
            if str(related).lower() in text:
                score += 8

        if score > 0:
            hits.append({
                "node": node_name,
                "type": node.get("type", "unknown"),
                "related_to": node.get("related_to", []),
                "notes": node.get("notes", []),
                "score": score,
            })

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:6]


def format_graph_context(user_input: str, game_data: dict, matched_records: list[dict]) -> str:
    base_graph = build_static_world_graph(game_data)
    full_graph = enrich_graph_with_official_records(base_graph, matched_records)
    hits = find_graph_hits(user_input, full_graph)

    if not hits:
        return "No strong graph relationships matched."

    lines = ["KNOWLEDGE GRAPH RELATIONSHIPS"]

    for hit in hits:
        lines.append(f"- Node: {hit['node']} [{hit['type']}]")

        related_to = hit.get("related_to", [])
        if related_to:
            lines.append("  Related to: " + ", ".join(str(x) for x in related_to[:8]))

        notes = hit.get("notes", [])
        if notes:
            for note in notes[:4]:
                lines.append(f"  Note: {note}")

    return "\n".join(lines)