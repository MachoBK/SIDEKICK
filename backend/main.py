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

try:
    load_json_to_db()
except Exception as e:
    print(f"Knowledge database load skipped/error: {e}")


class ChatRequest(BaseModel):
    message: str
    personality: str = "calm_strategist"
    mode: str = "general"


def build_knowledge_context(user_message: str) -> str:
    try:
        results = search_knowledge(user_message)

        if not results:
            return ""

        context_parts = []

        for item in results[:3]:
            content = item.get("content", {})

            context_parts.append(
                f"""
Game: {item.get("game")}
Section: {item.get("section")}
Title: {item.get("title")}

Knowledge:
{json.dumps(content, indent=2, ensure_ascii=False)}
"""
            )

        return "\n\n".join(context_parts)

    except Exception as e:
        print(f"Knowledge search error: {e}")
        return ""


def generate_response(
    message: str,
    personality: str = "calm_strategist",
    mode: str = "general",
):
    knowledge_context = build_knowledge_context(message)

    system_prompt = f"""
You are SYNK, a helpful holographic AI sidekick.

Always respond in English.
Personality: {personality}.
Mode: {mode}.

Use the knowledge below when it is relevant.
If the knowledge does not answer the user's question, answer normally.

Keep responses clear, useful, and conversational.

KNOWLEDGE:
{knowledge_context}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )

    content = response.choices[0].message.content
    return content.strip() if content else "I heard you, but I could not generate a response."


def extension_from_filename(filename: str | None):
    if not filename:
        return ".webm"

    suffix = Path(filename).suffix.lower()
    return suffix if suffix else ".webm"


@app.get("/")
def root():
    return {"message": "SYNK backend online"}


@app.get("/knowledge/search")
async def knowledge_search(q: str):
    try:
        results = search_knowledge(q)
        return {
            "query": q,
            "results": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/realtime/session")
def realtime_session():
    try:
        secret = client.realtime.client_secrets.create(
            session={
                "type": "realtime",
                "model": "gpt-realtime",
                "instructions": (
                    "You are SYNK, a futuristic holographic AI sidekick. "
                    "Speak ONLY in English. "
                    "Use a clear, natural American accent. "
                    "Keep replies conversational and concise."
                ),
                "audio": {
                    "output": {
                        "voice": "marin"
                    }
                },
            }
        )

        return secret

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        text = generate_response(req.message, req.personality, req.mode)

        return {
            "title": "SYNK Response",
            "message": text,
            "mode": req.mode,
            "personality": req.personality,
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
        audio_bytes = await audio.read()

        if not audio_bytes:
            raise HTTPException(status_code=400, detail="No audio received.")

        suffix = extension_from_filename(audio.filename)

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_path = temp_audio.name

        with open(temp_path, "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        transcript = getattr(transcript_response, "text", "").strip()

        if not transcript:
            raise HTTPException(
                status_code=400,
                detail="No speech detected. Try speaking louder or recording longer.",
            )

        reply = generate_response(transcript, personality, mode)

        return {
            "title": "SYNK Voice Response",
            "transcript": transcript,
            "message": reply,
            "mode": mode,
            "personality": personality,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/tts")
async def tts(text: str = Form(...)):
    try:
        output_path = "synk_speech.mp3"

        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
        ) as response:
            response.stream_to_file(output_path)

        return FileResponse(output_path, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))