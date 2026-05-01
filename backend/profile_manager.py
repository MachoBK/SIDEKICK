import json
import os
import re
from datetime import datetime, timezone

PROFILE_FILE = "user_profile.json"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def default_profile():
    return {
        "name": None,
        "playstyle": None,
        "preferred_weapon_style": None,
        "focus": None,
        "experience_level": None,
        "favorite_focus": None,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }


def normalize_profile(profile):
    if not isinstance(profile, dict):
        return default_profile()

    normalized = default_profile()
    normalized.update(profile)

    normalized.setdefault("name", None)
    normalized.setdefault("playstyle", None)
    normalized.setdefault("preferred_weapon_style", None)
    normalized.setdefault("focus", None)
    normalized.setdefault("experience_level", None)
    normalized.setdefault("favorite_focus", None)
    normalized.setdefault("created_at", utc_now_iso())
    normalized.setdefault("updated_at", utc_now_iso())

    return normalized


def load_profile():
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return normalize_profile(data)
        except Exception:
            return default_profile()
    return default_profile()


def save_profile(profile):
    profile = normalize_profile(profile)
    profile["updated_at"] = utc_now_iso()

    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    parts = name.split(" ")
    cleaned_parts = []

    for part in parts:
        if not part:
            continue

        if "'" in part:
            subparts = part.split("'")
            subparts = [sp.capitalize() if sp else sp for sp in subparts]
            cleaned_parts.append("'".join(subparts))
        elif "-" in part:
            subparts = part.split("-")
            subparts = [sp.capitalize() if sp else sp for sp in subparts]
            cleaned_parts.append("-".join(subparts))
        else:
            cleaned_parts.append(part.capitalize())

    return " ".join(cleaned_parts)


def extract_name(user_input):
    text = user_input.strip()

    patterns = [
        r"\bmy name is\s+([A-Za-z][A-Za-z' -]{0,40})",
        r"\bi am\s+([A-Za-z][A-Za-z' -]{0,40})",
        r"\bi'm\s+([A-Za-z][A-Za-z' -]{0,40})",
        r"\bcall me\s+([A-Za-z][A-Za-z' -]{0,40})",
    ]

    blocked_values = {
        "new", "ready", "here", "using", "trying", "playing",
        "aggressive", "defensive", "stealth", "beginner", "advanced"
    }

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = clean_name(match.group(1))
            lowered = candidate.lower().strip()

            if lowered in blocked_values:
                continue

            if len(candidate) > 40:
                continue

            return candidate

    return None


def detect_playstyle(user_input: str):
    text = user_input.lower()

    playstyle_rules = {
        "stealth": ["stealth", "sneaky", "quiet approach", "silent"],
        "aggressive": ["aggressive", "rushdown", "pressure", "all-in"],
        "defensive": ["defensive", "careful", "safe", "patient"],
        "ranged": ["ranged", "distance", "far away", "keep range"],
        "melee": ["melee", "close range", "up close"],
        "balanced": ["balanced", "versatile", "all-round"],
        "mobile": ["mobile", "mobility", "fast movement", "hit and run"],
    }

    for style, phrases in playstyle_rules.items():
        if any(phrase in text for phrase in phrases):
            return style

    return None


def detect_weapon_style(user_input: str):
    text = user_input.lower()

    weapon_rules = {
        "fast": ["fast weapon", "fast weapons", "quick weapon", "quick weapons", "light weapon", "light weapons"],
        "heavy": ["heavy weapon", "heavy weapons", "slow weapon", "slow weapons"],
        "sword": ["sword", "longsword", "blade"],
        "bow": ["bow", "archery"],
        "spear": ["spear"],
        "shield": ["shield"],
        "balanced": ["balanced weapon", "versatile weapon"],
    }

    for style, phrases in weapon_rules.items():
        if any(phrase in text for phrase in phrases):
            return style

    return None


def detect_focus(user_input: str):
    text = user_input.lower()

    focus_rules = {
        "boss fights": ["boss", "boss fight", "boss fights"],
        "exploration": ["explore", "exploration", "travel", "world"],
        "gear and builds": ["gear", "build", "builds", "equipment", "loadout"],
        "combat": ["combat", "fighting", "duel", "enemy tactics"],
        "quests": ["quest", "quests", "mission", "missions", "objective"],
        "mounts": ["mount", "mounts", "horse", "ride"],
        "progression": ["progression", "leveling", "advancing"],
    }

    for focus, phrases in focus_rules.items():
        if any(phrase in text for phrase in phrases):
            return focus

    return None


def detect_experience_level(user_input: str):
    text = user_input.lower()

    if any(phrase in text for phrase in ["i'm new", "i am new", "beginner", "just starting", "new player"]):
        return "beginner"

    if any(phrase in text for phrase in ["intermediate", "some experience"]):
        return "intermediate"

    if any(phrase in text for phrase in ["advanced", "experienced", "veteran"]):
        return "advanced"

    return None


def detect_favorite_focus(user_input: str):
    text = user_input.lower()

    patterns = [
        r"\bi want to focus on\s+([a-zA-Z0-9' -]{2,40})",
        r"\bi want help with\s+([a-zA-Z0-9' -]{2,40})",
        r"\bfocus on\s+([a-zA-Z0-9' -]{2,40})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip().lower()

    return None


def update_profile(profile, user_input):
    profile = normalize_profile(profile)
    text = user_input.strip()

    found_name = extract_name(text)
    if found_name:
        profile["name"] = found_name

    detected_playstyle = detect_playstyle(text)
    if detected_playstyle:
        profile["playstyle"] = detected_playstyle

    detected_weapon_style = detect_weapon_style(text)
    if detected_weapon_style:
        profile["preferred_weapon_style"] = detected_weapon_style

    detected_focus = detect_focus(text)
    if detected_focus:
        profile["focus"] = detected_focus

    detected_experience = detect_experience_level(text)
    if detected_experience:
        profile["experience_level"] = detected_experience

    detected_favorite_focus = detect_favorite_focus(text)
    if detected_favorite_focus:
        profile["favorite_focus"] = detected_favorite_focus

    profile["updated_at"] = utc_now_iso()
    return profile