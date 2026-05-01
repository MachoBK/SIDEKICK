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

from knowledge_db import load_json_to_db, search_knowledge

# =========================
# SETUP
# =========================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

# =========================
# GAME FILTER
# =========================
def is_game_related(message: str) -> bool:
    msg = message.lower()

    game_keywords = [
        "game", "games", "gaming", "quest", "mission", "boss", "character",
        "npc", "weapon", "armor", "skill", "level", "map", "location",
        "faction", "story", "lore", "chapter", "prologue", "enemy",
        "combat", "ability", "reward", "item", "guide", "walkthrough",
        "crimson", "desert", "kliff", "myurdin", "greymanes",
        "black bears", "pywel", "hernand", "abyss", "freesword"
    ]

    return any(keyword in msg for keyword in game_keywords)

# =========================
# KNOWLEDGE
# =========================
def build_knowledge_context(query: str) -> str:
    results = search_knowledge(query, limit=5)

    if not results:
        return ""

    context = []

    for item in results[:3]:
        content = json.dumps(item.get("content", {}), indent=2)

        if len(content) > 1500:
            content = content[:1500] + "\n...[truncated]"

        context.append(f"""
Game: {item.get('game', 'Unknown')}
Section: {item.get('section', 'Unknown')}
Title: {item.get('title', 'Unknown')}
Type: {item.get('type', 'Unknown')}

Data:
{content}
""")

    return "\n\n".join(context)

# =========================
# AI RESPONSE
# =========================
def generate_response(message: str, personality: str, mode: str, language: str):
    if not is_game_related(message):
        return "I’m focused only on video game-related topics."

    knowledge = build_knowledge_context(message)

    if not knowledge:
        return "I don't have that information yet."

    system_prompt = f"""
You are SYNK, a futuristic AI sidekick designed ONLY for video games.

LANGUAGE RULE:
- Respond ONLY in {language}.
- Do not switch languages unless the selected language changes.

STRICT RULES:
- Only answer video game-related questions.
- Only use the provided game knowledge.
- Never guess or invent information.
- Do not invent factions, characters, locations, quests, weapons, lore, or mechanics.
- If the answer is not in the provided knowledge, say:
  "I don't have that information yet."

GAME KNOWLEDGE:
{knowledge}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=300,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )

    return response.choices[0].message.content.strip()

# =========================
# ROUTES
# =========================
@app.get("/")
def root():
    return {"status": "SYNK running"}

@app.get("/knowledge/search")
def knowledge_search(q: str):
    try:
        results = search_knowledge(q)
        return {
            "query": q,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        reply = generate_response(
            req.message,
            req.personality,
            req.mode,
            req.language
        )

        return {
            "message": reply,
            "mode": req.mode,
            "personality": req.personality,
            "language": req.language
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/realtime/session")
def realtime_session(language: str = "English"):
    try:
        return client.realtime.client_secrets.create(
            session={
                "type": "realtime",
                "model": "gpt-realtime",
                "instructions": (
                    "You are SYNK, a futuristic AI sidekick designed only for video games. "
                    f"Always respond only in {language}. "
                    "Do not answer general questions. "
                    "If the user asks anything unrelated to video games, say: "
                    "'I’m focused only on video game-related topics.' "
                    "Do not guess game facts. "
                    "If you do not have the answer, say: "
                    "'I don't have that information yet.'"
                ),
                "audio": {
                    "output": {"voice": "marin"}
                },
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    personality: str = Form("calm_strategist"),
    mode: str = Form("game"),
    language: str = Form("English"),
):
    temp_path = None

    try:
        data = await audio.read()

        if not data:
            raise HTTPException(status_code=400, detail="No audio received")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp:
            temp.write(data)
            temp_path = temp.name

        with open(temp_path, "rb") as f:
            transcript_res = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        transcript = transcript_res.text.strip()

        reply = generate_response(
            transcript,
            personality,
            mode,
            language
        )

        return {
            "transcript": transcript,
            "message": reply,
            "language": language
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/tts")
async def tts(text: str = Form(...)):
    try:
        output_file = "synk.mp3"

        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
        ) as res:
            res.stream_to_file(output_file)

        return FileResponse(output_file, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))