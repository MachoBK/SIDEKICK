import os
from dotenv import load_dotenv
from openai import OpenAI

from profile_manager import load_profile, save_profile, update_profile
from knowledge_retriever import (
    search_official_knowledge,
    format_records_for_prompt,
    get_top_record_names,
    is_direct_fact_query,
    is_list_query,
    build_direct_fact_answer,
    build_list_answer,
)
from knowledge_graph import format_graph_context

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


VALID_MODES = {
    "general",
    "boss_prep",
    "build_advice",
    "exploration_help",
    "loot_priority",
}


def bullets(items):
    if not items:
        return "- None loaded."
    return "\n".join(f"- {item}" for item in items)


def extract_names(items, key="name"):
    return [item.get(key, "unknown") for item in items if isinstance(item, dict)]


def detect_intent(user_input: str) -> str:
    text = user_input.lower()

    if any(word in text for word in ["boss", "fight", "enemy", "combat", "attack", "defend", "dodge"]):
        return "combat"

    if any(word in text for word in ["gear", "weapon", "armor", "build", "mount", "equipment", "shield", "sword", "bow", "spear"]):
        return "gear"

    if any(word in text for word in ["item", "items", "token", "artifact", "lantern"]):
        return "item"

    if any(word in text for word in ["where", "region", "travel", "explore", "map", "world", "location", "camp", "castle"]):
        return "world"

    if any(word in text for word in ["quest", "mission", "objective", "progression", "stage"]):
        return "progression"

    if any(word in text for word in ["my name is", "i am ", "i'm ", "call me ", "i like", "i prefer"]):
        return "profile"

    if any(word in text for word in ["shorter", "summarize", "simplify", "make that shorter"]):
        return "followup"

    if any(word in text for word in ["list", "show me all", "what are the", "give me all"]):
        return "list"

    return "general"


def detect_topic(user_input: str, intent: str) -> str:
    text = user_input.lower()

    if intent == "combat":
        if "boss" in text:
            return "boss fight"
        if "enemy" in text:
            return "enemy tactics"
        return "combat"

    if intent == "gear":
        return "gear"

    if intent == "item":
        return "item"

    if intent == "world":
        return "exploration"

    if intent == "progression":
        return "progression"

    if intent == "profile":
        return "player profile"

    if intent == "followup":
        return "follow-up"

    if intent == "list":
        return "official records"

    return "general"


def detect_preferred_style(user_input: str, current_style: str = "normal") -> str:
    text = user_input.lower()

    if any(phrase in text for phrase in ["make that shorter", "shorter", "brief", "quick answer", "summarize", "simplify"]):
        return "brief"

    if any(phrase in text for phrase in ["go deeper", "more detail", "explain more", "detailed", "step by step", "walk me through"]):
        return "detailed"

    return current_style


def infer_preferred_style_from_session(session_memory: dict | None, fallback: str = "normal") -> str:
    if not isinstance(session_memory, dict):
        return fallback

    meta = session_memory.get("meta", {})
    if isinstance(meta, dict):
        return meta.get("preferred_style", fallback)

    return fallback


def build_mode_instruction(mode: str) -> str:
    if mode == "boss_prep":
        return """
MODE: Boss Prep
- Focus on survival, preparation, and combat strategy
- Give checklist-style advice when useful
- Highlight mistakes to avoid
- Prioritize reliability and consistency over reckless aggression
- If the boss is unknown, give a practical preparation framework
""".strip()

    if mode == "build_advice":
        return """
MODE: Build Advice
- Focus on gear synergy, stats, and playstyle fit
- Recommend upgrades and improvements
- Explain tradeoffs when multiple paths are viable
- If important build details are missing, say exactly what would help refine the answer
""".strip()

    if mode == "exploration_help":
        return """
MODE: Exploration Help
- Focus on efficient progression and route value
- Suggest what to prioritize next
- Warn about risks, wasted effort, and avoidable detours
- Emphasize safe progress, valuable pickups, and useful discoveries
""".strip()

    if mode == "loot_priority":
        return """
MODE: Loot Priority
- Rank items, upgrades, or categories by importance
- Explain what to keep, upgrade, sell, or ignore
- Focus on efficiency, value, and immediate usefulness
- Prefer practical prioritization over vague advice
""".strip()

    return """
MODE: General
- Provide clear, helpful, grounded guidance
- Be flexible and useful without forcing a special format
""".strip()


def build_relevant_context(game_data, intent):
    game_info = game_data.get("game_info", {})
    story = game_data.get("official_story_and_world", {})
    systems = game_data.get("official_systems", {})
    patch_terms = game_data.get("official_patch_notice_terms", [])
    rules = game_data.get("assistant_rules", {}).get("response_policy", [])
    regions = game_data.get("regions", [])
    quests = game_data.get("quests", [])
    gear = game_data.get("gear", [])
    enemy_archetypes = game_data.get("enemy_archetypes", [])
    progression_stages = game_data.get("progression_stages", [])
    official_bosses = game_data.get("official_bosses", [])
    community_boss_names = game_data.get("community_reference", {}).get("community_boss_names", [])

    patch_lines = [term.get("term", "unknown") for term in patch_terms if isinstance(term, dict)]
    region_names = extract_names(regions)
    quest_names = extract_names(quests)
    gear_names = extract_names(gear)
    archetype_names = extract_names(enemy_archetypes)
    stage_names = [item.get("stage", "unknown") for item in progression_stages if isinstance(item, dict)]
    boss_names = extract_names(official_bosses)

    base = f"""
GAME INFO
- Name: {game_info.get("name", "Crimson Desert")}
- World: {game_info.get("world", "Pywel")}
- Protagonist: {game_info.get("protagonist", "Kliff")}
- Primary faction: {game_info.get("primary_faction", "Greymanes")}
- Enemy faction: {game_info.get("enemy_faction", "Black Bears")}

RESPONSE RULES
{bullets(rules)}
""".strip()

    if intent == "combat":
        return f"""
{base}

OFFICIAL BOSSES
{bullets(boss_names)}

OFFICIAL SYSTEMS - COMBAT
{bullets(systems.get("combat", []))}

ENEMY ARCHETYPES
{bullets(archetype_names)}

COMMUNITY BOSS REFERENCE
{bullets(community_boss_names)}
""".strip()

    if intent == "gear":
        return f"""
{base}

GEAR / MOUNTS
{bullets(gear_names)}

OFFICIAL PATCH / SYSTEM TERMS
{bullets(patch_lines)}

OFFICIAL SYSTEMS - COMBAT
{bullets(systems.get("combat", []))}
""".strip()

    if intent == "item":
        return f"""
{base}

OFFICIAL PATCH / SYSTEM TERMS
{bullets(patch_lines)}

GEAR / MOUNTS
{bullets(gear_names)}
""".strip()

    if intent == "world":
        return f"""
{base}

OFFICIAL STORY SUMMARY
{bullets(story.get("summary", []))}

OFFICIAL SYSTEMS - WORLD / TRAVEL
{bullets(systems.get("travel_and_world", []))}

REGIONS
{bullets(region_names)}
""".strip()

    if intent == "progression":
        return f"""
{base}

QUESTS
{bullets(quest_names)}

PROGRESSION STAGES
{bullets(stage_names)}

OFFICIAL STORY SUMMARY
{bullets(story.get("summary", []))}
""".strip()

    return f"""
{base}

OFFICIAL STORY SUMMARY
{bullets(story.get("summary", []))}

OFFICIAL BOSSES
{bullets(boss_names)}

OFFICIAL SYSTEMS - COMBAT
{bullets(systems.get("combat", []))}

OFFICIAL SYSTEMS - WORLD / TRAVEL
{bullets(systems.get("travel_and_world", []))}

REGIONS
{bullets(region_names)}

QUESTS
{bullets(quest_names)}

GEAR / MOUNTS
{bullets(gear_names)}

ENEMY ARCHETYPES
{bullets(archetype_names)}

PROGRESSION STAGES
{bullets(stage_names)}

COMMUNITY BOSS REFERENCE
{bullets(community_boss_names)}

OFFICIAL PATCH / SYSTEM TERMS
{bullets(patch_lines)}
""".strip()


def build_personality_instruction(personality: str, preferred_style: str) -> str:
    style_rules = {
        "brief": "Keep the answer short, direct, and natural. Use 2 to 4 sentences when possible.",
        "normal": "Keep the answer concise, clear, and helpful.",
        "detailed": "Give a more detailed answer with practical guidance, but keep it organized and easy to follow."
    }

    response_style = style_rules.get(preferred_style, style_rules["normal"])

    personalities = {
        "cartoon": f"""
PERSONALITY RULES
- You are playful, energetic, and sharp.
- Sound like a fun game sidekick.
- You may occasionally use short lines like:
  - "Alright, let’s go."
  - "Nice."
  - "That’s the move."
  - "Good pick."
  - "Here’s the play."
- Keep it fun but not childish.
- {response_style}
""".strip(),

        "calm_strategist": f"""
PERSONALITY RULES
- You are calm, polished, and clear.
- Sound like a modern AI assistant: natural, steady, helpful, and confident.
- Keep the tone warm but controlled.
- Avoid slang, hype, or exaggerated personality.
- Prefer smooth, clean wording.
- Be concise first, but still useful.
- {response_style}
""".strip(),

        "hype_mode": f"""
PERSONALITY RULES
- You are high-energy, confident, and motivating.
- Sound like a teammate hyping the player up.
- You may occasionally use short lines like:
  - "Let’s cook."
  - "That’s huge."
  - "We’re good."
  - "That’s your opening."
- Do not be annoying or overdo slang.
- {response_style}
""".strip(),

        "serious_tactical": f"""
PERSONALITY RULES
- You are direct, efficient, and serious.
- Sound like a mission operator or tactical support AI.
- Keep replies clean, controlled, and practical.
- Avoid jokes and extra fluff.
- {response_style}
""".strip(),
    }

    return personalities.get(personality, personalities["calm_strategist"])


def build_memory_summary(session_memory: dict | None) -> str:
    if not isinstance(session_memory, dict):
        return "No session memory available."

    meta = session_memory.get("meta", {})
    context = session_memory.get("context", {})
    profile = session_memory.get("profile", {})
    history = session_memory.get("history", [])

    recent_history = history[-3:] if isinstance(history, list) else []

    history_lines = []
    for item in recent_history:
        if not isinstance(item, dict):
            continue
        user_msg = item.get("user", "")
        assistant_msg = item.get("assistant", "")
        item_mode = item.get("mode", "general")
        history_lines.append(
            f"Mode: {item_mode}\nUser: {user_msg}\nAssistant: {assistant_msg}"
        )

    return f"""
SESSION META
- personality: {meta.get("personality", "unknown")}
- preferred_style: {meta.get("preferred_style", "unknown")}
- active_mode: {meta.get("active_mode", "general")}

SESSION CONTEXT
- last_intent: {context.get("last_intent", "unknown")}
- last_topic: {context.get("last_topic", "unknown")}

SESSION PROFILE
- name: {profile.get("name", "unknown")}
- playstyle: {profile.get("playstyle", "unknown")}
- experience_level: {profile.get("experience_level", "unknown")}
- favorite_focus: {profile.get("favorite_focus", "unknown")}

RECENT HISTORY
{chr(10).join(history_lines) if history_lines else "None"}
""".strip()


def merge_structured_and_records(user_input: str, game_data: dict, matched_records: list[dict]) -> str:
    text = user_input.lower()
    context_parts = []

    game_info = game_data.get("game_info", {})
    story = game_data.get("official_story_and_world", {})
    systems = game_data.get("official_systems", {})
    regions = game_data.get("regions", [])
    quests = game_data.get("quests", [])
    gear = game_data.get("gear", [])
    bosses = game_data.get("official_bosses", [])
    stages = game_data.get("progression_stages", [])

    context_parts.append(
        "\n".join([
            "STRUCTURED GAME INFO",
            f"- Name: {game_info.get('name', 'Crimson Desert')}",
            f"- World: {game_info.get('world', 'Pywel')}",
            f"- Protagonist: {game_info.get('protagonist', 'Kliff')}",
            f"- Primary faction: {game_info.get('primary_faction', 'Greymanes')}",
            f"- Enemy faction: {game_info.get('enemy_faction', 'Black Bears')}",
        ])
    )

    if "combat" in text or "boss" in text or "fight" in text:
        combat_lines = systems.get("combat", [])
        if combat_lines:
            context_parts.append("COMBAT SYSTEM INFO\n" + bullets(combat_lines))

    if any(word in text for word in ["world", "explore", "region", "location", "travel", "where"]):
        summary_lines = story.get("summary", [])
        if summary_lines:
            context_parts.append("WORLD SUMMARY\n" + bullets(summary_lines))

        if regions:
            region_names = extract_names(regions)
            context_parts.append("KNOWN REGIONS\n" + bullets(region_names))

    if any(word in text for word in ["quest", "mission", "objective", "progression"]):
        if quests:
            quest_names = extract_names(quests)
            context_parts.append("KNOWN QUESTS\n" + bullets(quest_names[:10]))

        if stages:
            stage_names = [item.get("stage", "unknown") for item in stages if isinstance(item, dict)]
            context_parts.append("PROGRESSION STAGES\n" + bullets(stage_names[:10]))

    if any(word in text for word in ["gear", "weapon", "armor", "mount", "build", "equipment"]):
        if gear:
            gear_names = extract_names(gear)
            context_parts.append("STRUCTURED GEAR DATA\n" + bullets(gear_names[:12]))

    if bosses:
        boss_names = extract_names(bosses)
        context_parts.append("KNOWN BOSSES\n" + bullets(boss_names[:10]))

    if matched_records:
        record_lines = []
        for r in matched_records[:5]:
            record_lines.append(
                f"- {r.get('name', 'Unknown')} [{r.get('category', 'unknown')}]: "
                f"{r.get('description', 'No description.')}"
            )
        context_parts.append("OFFICIAL MATCHED RECORDS\n" + "\n".join(record_lines))

    graph_context = format_graph_context(user_input, game_data, matched_records)
    if graph_context:
        context_parts.append(graph_context)

    return "\n\n".join(part for part in context_parts if part.strip())


def build_system_prompt(
    game_data,
    profile,
    intent,
    preferred_style,
    retrieved_records_text,
    retrieved_names,
    personality,
    mode="general",
    session_memory=None
):
    player_name = profile.get("name", "unknown")
    relevant_context = build_relevant_context(game_data, intent)
    personality_instruction = build_personality_instruction(personality, preferred_style)
    session_summary = build_memory_summary(session_memory)
    mode_instruction = build_mode_instruction(mode)

    return f"""
You are SYNK, an AI sidekick for Crimson Desert.

Your job:
- Give tactical, concise, useful answers.
- Prefer official named records when available.
- Use structured game data when it helps explain systems, world, combat, progression, and gear.
- Use graph relationships when they help connect people, places, factions, systems, and records.
- If a matching official record exists, use its exact name.
- If the query asks what is known by name, list the best matching official names.
- If using community data, explicitly say it is community-sourced.
- Do not invent exact bosses, quests, gear, items, locations, mounts, or characters that are not in the official records.
- If exact official facts are missing, say that clearly and then give best-practice action-game advice.
- If the player's name is known, occasionally use it naturally, but do not overuse it.
- If a follow-up asks for a shorter version, shorten the previous style naturally.
- If official records directly answer the question, prioritize them over general reasoning.

{personality_instruction}

{mode_instruction}

CURRENT INTENT
- {intent}

CURRENT MODE
- {mode}

CURRENT PERSONALITY
- {personality}

PLAYER PROFILE
- Name: {player_name}
- Playstyle: {profile.get("playstyle", "unknown")}
- Focus: {profile.get("focus", "unknown")}
- Preferred weapon style: {profile.get("preferred_weapon_style", "unknown")}
- Experience level: {profile.get("experience_level", "unknown")}
- Favorite focus: {profile.get("favorite_focus", "unknown")}

TOP MATCHED OFFICIAL NAMES
- {", ".join(retrieved_names) if retrieved_names else "None"}

RETRIEVED KNOWLEDGE CONTEXT
{retrieved_records_text}

SESSION MEMORY
{session_summary}

ADDITIONAL GAME CONTEXT
{relevant_context}
""".strip()


def maybe_personality_flair(text: str, personality: str, preferred_style: str = "normal") -> str:
    text = (text or "").strip()
    if not text:
        return text

    if personality == "cartoon" and preferred_style != "brief":
        return f"SYNK says: {text}"

    if personality == "hype_mode" and preferred_style == "brief":
        return f"Lock in — {text}"

    return text


def compute_record_confidence(matched_records) -> float:
    if not matched_records:
        return 0.0

    top = matched_records[0]
    top_confidence = top.get("_confidence")
    if isinstance(top_confidence, (int, float)):
        return float(top_confidence)

    count = len(matched_records)

    if count >= 6:
        return 0.93
    if count >= 4:
        return 0.87
    if count >= 2:
        return 0.79
    return 0.68


def safe_profile_updates(profile: dict, previous_profile: dict) -> dict:
    updates = {}

    for key, value in profile.items():
        old_value = previous_profile.get(key)
        if value and value != old_value:
            updates[key] = value

    return updates


def build_response(
    response_text: str,
    previous_response_id,
    intent: str,
    topic: str,
    preferred_style: str,
    personality: str,
    source: str,
    confidence: float,
    mode: str = "general",
    profile_updates: dict | None = None,
):
    return {
        "response": response_text,
        "response_id": previous_response_id,
        "intent": intent,
        "topic": topic,
        "preferred_style": preferred_style,
        "personality": personality,
        "mode": mode,
        "source": source,
        "confidence": confidence,
        "profile_updates": profile_updates or {},
    }


def sidekick_reply(
    user_input,
    game_data,
    previous_response_id=None,
    personality="calm_strategist",
    mode="general",
    session_memory=None
):
    user_input = (user_input or "").strip()

    if mode not in VALID_MODES:
        mode = "general"

    if not user_input:
        return build_response(
            response_text="Ask me something about Crimson Desert.",
            previous_response_id=previous_response_id,
            intent="general",
            topic="general",
            preferred_style="normal",
            personality=personality,
            source="fallback",
            confidence=0.20,
            mode=mode,
        )

    previous_profile = load_profile()
    profile = update_profile(previous_profile, user_input)
    save_profile(profile)

    profile_updates = safe_profile_updates(profile, previous_profile)

    remembered_name = profile.get("name")
    lower_input = user_input.lower()

    if remembered_name and any(
        phrase in lower_input for phrase in ["my name is", "i am ", "i'm ", "call me "]
    ):
        acknowledgements = {
            "cartoon": f"Got it, {remembered_name}. I’ll remember your name. Alright, let’s go.",
            "calm_strategist": f"Got it, {remembered_name}. I’ll remember your name going forward.",
            "hype_mode": f"Locked in, {remembered_name}. I’ve got your name. Let’s do this.",
            "serious_tactical": f"Confirmed, {remembered_name}. Your name has been stored."
        }

        return build_response(
            response_text=acknowledgements.get(personality, acknowledgements["calm_strategist"]),
            previous_response_id=previous_response_id,
            intent="profile",
            topic="player profile",
            preferred_style="normal",
            personality=personality,
            source="memory",
            confidence=0.99,
            mode=mode,
            profile_updates=profile_updates,
        )

    stored_style = infer_preferred_style_from_session(session_memory, "normal")
    intent = detect_intent(user_input)
    topic = detect_topic(user_input, intent)
    preferred_style = detect_preferred_style(user_input, stored_style)

    matched_records = search_official_knowledge(user_input, max_results=8)
    record_confidence = compute_record_confidence(matched_records)

    if is_list_query(user_input):
        direct_list_answer = build_list_answer(user_input, matched_records)
        if direct_list_answer:
            return build_response(
                response_text=maybe_personality_flair(direct_list_answer, personality, preferred_style),
                previous_response_id=previous_response_id,
                intent="list",
                topic=topic,
                preferred_style=preferred_style,
                personality=personality,
                source="official",
                confidence=max(record_confidence, 0.88),
                mode=mode,
                profile_updates=profile_updates,
            )

    if is_direct_fact_query(user_input, matched_records):
        direct_fact_answer = build_direct_fact_answer(user_input, matched_records)
        if direct_fact_answer:
            return build_response(
                response_text=maybe_personality_flair(direct_fact_answer, personality, preferred_style),
                previous_response_id=previous_response_id,
                intent=intent,
                topic=topic,
                preferred_style=preferred_style,
                personality=personality,
                source="official",
                confidence=max(record_confidence, 0.90),
                mode=mode,
                profile_updates=profile_updates,
            )

    retrieved_records_text = merge_structured_and_records(
        user_input=user_input,
        game_data=game_data,
        matched_records=matched_records,
    )

    retrieved_names = get_top_record_names(matched_records, max_names=5)

    system_prompt = build_system_prompt(
        game_data=game_data,
        profile=profile,
        intent=intent,
        preferred_style=preferred_style,
        retrieved_records_text=retrieved_records_text,
        retrieved_names=retrieved_names,
        personality=personality,
        mode=mode,
        session_memory=session_memory,
    )

    if client is None:
        if matched_records:
            fallback_text = (
                "I found relevant official records, but AI generation is currently unavailable. "
                "Check your OPENAI_API_KEY and try again."
            )
            return build_response(
                response_text=fallback_text,
                previous_response_id=previous_response_id,
                intent=intent,
                topic=topic,
                preferred_style=preferred_style,
                personality=personality,
                source="official",
                confidence=0.55,
                mode=mode,
                profile_updates=profile_updates,
            )

        return build_response(
            response_text="AI generation is unavailable right now. Check your OPENAI_API_KEY.",
            previous_response_id=previous_response_id,
            intent=intent,
            topic=topic,
            preferred_style=preferred_style,
            personality=personality,
            source="fallback",
            confidence=0.20,
            mode=mode,
            profile_updates=profile_updates,
        )

    try:
        kwargs = {
            "model": OPENAI_MODEL,
            "instructions": system_prompt,
            "input": user_input,
            "store": True,
        }

        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id

        response = client.responses.create(**kwargs)
        output_text = (response.output_text or "").strip()

        if not output_text:
            output_text = "I couldn't generate a useful answer from that. Try asking in a more specific way."

        return {
            "response": output_text,
            "response_id": response.id,
            "intent": intent,
            "topic": topic,
            "preferred_style": preferred_style,
            "personality": personality,
            "mode": mode,
            "source": "hybrid" if matched_records else "openai",
            "confidence": 0.82 if matched_records else 0.64,
            "profile_updates": profile_updates,
        }

    except Exception as e:
        if matched_records:
            names_text = ", ".join(retrieved_names) if retrieved_names else "some official records"
            fallback_text = (
                f"I hit an AI error, but I did find related official material: {names_text}. "
                f"Error: {str(e)}"
            )
            return build_response(
                response_text=fallback_text,
                previous_response_id=previous_response_id,
                intent=intent,
                topic=topic,
                preferred_style=preferred_style,
                personality=personality,
                source="official",
                confidence=0.45,
                mode=mode,
                profile_updates=profile_updates,
            )

        return build_response(
            response_text=f"AI error: {str(e)}",
            previous_response_id=previous_response_id,
            intent=intent,
            topic=topic,
            preferred_style=preferred_style,
            personality=personality,
            source="fallback",
            confidence=0.15,
            mode=mode,
            profile_updates=profile_updates,
        )