from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
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
# MODELS
# =========================
class ChatRequest(BaseModel):
    message: str
    personality: str = "calm_strategist"
    mode: str = "general"

# =========================
# KNOWLEDGE ENGINE
# =========================
def build_knowledge_context(query: str) -> str:
    results = search_knowledge(query)

    if not results:
        return ""

    context = []

    # Only use top 3 chunks to save tokens
    for item in results[:3]:
        content = json.dumps(item.get("content", {}), indent=2)

        # Limit each chunk so we do not waste tokens
        if len(content) > 1800:
            content = content[:1800] + "\n...[truncated]"

        context.append(
            f"""
Game: {item.get('game', 'Unknown')}
Section: {item.get('section', 'Unknown')}
Title: {item.get('title', 'Unknown')}

Data:
{content}
"""
        )

    return "\n\n".join(context)

# =========================
# AI RESPONSE
# =========================
def generate_response(message: str, personality: str, mode: str):
    knowledge = build_knowledge_context(message)

    if not knowledge:
        knowledge = "NO_RELEVANT_KNOWLEDGE_FOUND"

    system_prompt = f"""
You are SYNK, a futuristic AI sidekick for video games.

Always respond in English.

Personality: {personality}
Mode: {mode}

STRICT RULES:
- Use ONLY the provided knowledge when answering game-specific questions.
- Do NOT guess.
- Do NOT invent factions, characters, locations, quests, weapons, lore, or mechanics.
- If the knowledge does not contain the answer, say: "I don't have that information yet."
- If the user asks a general non-game question, you may answer normally.
- Keep responses clear, natural, and conversational.
- Be concise unless the user asks for detail.

GAME KNOWLEDGE:
{knowledge}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=350,
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
    return {"status": "SYNK backend running"}

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

@app.get("/realtime/session")
def realtime_session():
    try:
        return client.realtime.client_secrets.create(
            session={
                "type": "realtime",
                "model": "gpt-realtime",
                "instructions": (
                    "You are SYNK, a futuristic AI sidekick. "
                    "Speak clearly in English with a natural tone. "
                    "Do not guess game facts. If you do not know, say you do not have that information yet."
                ),
                "audio": {
                    "output": {"voice": "marin"}
                },
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        reply = generate_response(req.message, req.personality, req.mode)

        return {
            "message": reply,
            "mode": req.mode,
            "personality": req.personality
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    personality: str = Form("calm_strategist"),
    mode: str = Form("general"),
):
    temp_path = None

    try:
        data = await audio.read()

        if not data:
            raise HTTPException(status_code=400, detail="No audio received")

        suffix = Path(audio.filename).suffix or ".webm"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(data)
            temp_path = temp.name

        with open(temp_path, "rb") as f:
            transcript_res = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )

        transcript = transcript_res.text.strip()

        reply = generate_response(transcript, personality, mode)

        return {
            "transcript": transcript,
            "message": reply
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