from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
import tempfile
import json
import re
import httpx

from knowledge_db import load_json_to_db, search_knowledge
from vector_index import query_index

# =========================
# SETUP
# =========================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/audio", StaticFiles(directory="."), name="audio")

load_json_to_db()

# =========================
# MODEL
# =========================
class ChatRequest(BaseModel):
    message: str
    personality: str = "calm_strategist"
    mode: str = "game"
    language: str = "English"
    session_id: str = "default"


# =========================
# GAME FILTER
# =========================
def is_game_related(message: str) -> bool:
    msg = message.lower()

    keywords = [
        "game", "quest", "mission", "boss", "character", "npc", "weapon",
        "armor", "skill", "level", "map", "location", "faction", "story",
        "lore", "enemy", "combat", "reward", "item", "guide", "walkthrough",
        "crimson", "desert", "kliff", "macduff", "hernand", "battalion",
        "army", "clan", "group"
    ]

    return any(k in msg for k in keywords)


# =========================
# KNOWLEDGE
# =========================
def build_knowledge_context(query: str) -> str:
    results = query_index(query, k=5)

    results = [r for r in results if r.get("score", 0) >= 0.35]

    if not results:
        return ""

    parts = []

    for item in results[:3]:
        content = item.get("content", {})
        lines = []

        if isinstance(content, dict):
            for k, v in content.items():
                lines.append(f"{k}: {v}")
        elif isinstance(content, list):
            lines.extend([f"- {v}" for v in content])
        else:
            lines.append(str(content))

        text = "\n".join(lines)

        parts.append(f"""
GAME: {item.get('game')}
TITLE: {item.get('title')}
TYPE: {item.get('type')}
SCORE: {item.get('score'):.3f}

{text}
""")

    return "\n\n---\n\n".join(parts)


def extract_allowed_names(knowledge: str):
    names = []

    for line in knowledge.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)

            if key.lower() in ["name", "title"]:
                names.append(value.strip().lower())

    return names


def contains_entity_claim(reply: str):
    keywords = [
        "battalion", "faction", "group", "army", "clan", "guild",
        "organization", "order", "tribe", "crew", "unit", "force",
        "company", "squad", "legion", "leader", "boss", "character"
    ]

    r = reply.lower()
    return any(k in r for k in keywords)


# =========================
# AI RESPONSE
# =========================
def generate_response(message: str, personality: str, mode: str, language: str):
    if not is_game_related(message):
        return "I’m focused only on video game-related topics."

    knowledge = build_knowledge_context(message)

    if not knowledge:
        return "I don't have that information yet."

    allowed_names = extract_allowed_names(knowledge)

    system_prompt = f"""
You are SYNK, a video game AI.

RULES:
- ONLY use GAME KNOWLEDGE
- NEVER invent names
- If unsure → say: "I don't have that information yet."

GAME KNOWLEDGE:
{knowledge}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=300,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )

    reply = res.choices[0].message.content.strip()
    reply_lower = reply.lower()

    unsafe = ["i don't know", "not sure", "maybe", "probably"]

    if any(u in reply_lower for u in unsafe):
        return "I don't have that information yet."

    if contains_entity_claim(reply):
        valid = False

        for name in allowed_names:
            if name in reply_lower:
                valid = True
                break

        if not valid:
            return "I don't have that information yet."

    return reply


# =========================
# ROUTES
# =========================
@app.get("/")
def root():
    return {"status": "SYNK running"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "SYNK backend",
        "realtime_route": "enabled",
    }


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        if not OPENAI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY is missing from backend environment variables.",
            )

        memory = conversation_memory.get(req.session_id, [])
        context_message = req.message

        if memory:
            history = "\n".join([
                f"User: {m['user']}\nSYNK: {m['assistant']}"
                for m in memory[-3:]
            ])

            context_message = f"{history}\nUser: {req.message}"

        reply = generate_response(
            context_message,
            req.personality,
            req.mode,
            req.language,
        )

        memory.append({"user": req.message, "assistant": reply})
        conversation_memory[req.session_id] = memory[-5:]

        return {"message": reply}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# REALTIME ROUTE - GA CLIENT SECRET
# =========================
@app.get("/realtime/session")
async def create_realtime_session(language: str = "English"):
    try:
        if not OPENAI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY is missing from backend environment variables.",
            )

        instructions = f"""
You are SYNK, a calm video game AI assistant.

RULES:
- Speak in {language}.
- Stay focused on video game-related topics.
- Do not guess.
- Do not invent names, factions, characters, bosses, items, or locations.
- If you do not know something, say: "I don't have that information yet."
- Keep answers clear, calm, and useful.
"""

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                "https://api.openai.com/v1/realtime/client_secrets",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "session": {
                        "type": "realtime",
                        "model": "gpt-realtime-mini",
                        "instructions": instructions,
                        "audio": {
                            "input": {
                                "turn_detection": {
                                    "type": "server_vad",
                                    "create_response": True,
                                    "interrupt_response": True,
                                }
                            },
                            "output": {
                                "voice": "alloy",
                            },
                        },
                    }
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text,
            )

        return response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))