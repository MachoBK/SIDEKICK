from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
import tempfile
from pathlib import Path
from fastapi.responses import FileResponse

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


# =========================
# MODELS
# =========================
class ChatRequest(BaseModel):
    message: str
    personality: str = "calm_strategist"
    mode: str = "general"


# =========================
# AI RESPONSE
# =========================
def generate_response(
    message: str,
    personality: str = "calm_strategist",
    mode: str = "general",
):
    system_prompt = (
        "You are SYNK, a helpful holographic AI sidekick. "
        "Always respond in English. "
        f"Personality: {personality}. Mode: {mode}. "
        "Keep responses clear, useful, and conversational."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )

    content = response.choices[0].message.content
    return content.strip() if content else "I heard you, but I could not generate a response."


# =========================
# UTILITY
# =========================
def extension_from_filename(filename: str | None):
    if not filename:
        return ".webm"

    suffix = Path(filename).suffix.lower()
    return suffix if suffix else ".webm"


# =========================
# ROUTES
# =========================

@app.get("/")
def root():
    return {"message": "SYNK backend online"}


# 🔥 REALTIME SESSION (FIXED + ENGLISH)
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


# 🔊 TEXT TO SPEECH
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