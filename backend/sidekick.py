import json
import os
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from data_loader import load_game_facts
from logic import sidekick_reply

app = FastAPI()

MEMORY_FILE = "memory_store.json"


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None
    personality: str | None = "cartoon"


class ResetRequest(BaseModel):
    session_id: str


def log_event(title: str, payload: dict | None = None):
    print(f"\n===== {title} =====")
    if payload:
        for key, value in payload.items():
            print(f"{key}: {value}")
    print("====================\n")


def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

                if not isinstance(data, dict):
                    return {}

                upgraded_memory = {}

                for session_id, session_data in data.items():
                    upgraded_memory[session_id] = normalize_session_memory(session_data)

                return upgraded_memory

        except json.JSONDecodeError:
            print("Warning: memory_store.json is corrupted. Starting with empty memory.")
            return {}
        except Exception as e:
            print(f"Warning: failed to load memory: {e}")
            return {}
    return {}


def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(conversation_memory, f, indent=2)
    except Exception as e:
        print(f"Warning: failed to save memory: {e}")


def normalize_session_memory(existing):
    """
    Upgrades older session formats into the new structured memory shape.
    """

    default_session = {
        "meta": {
            "personality": "cartoon",
            "preferred_style": "normal",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        },
        "context": {
            "last_response_id": None,
            "last_intent": None,
            "last_topic": None
        },
        "profile": {
            "name": None,
            "playstyle": None,
            "experience_level": None,
            "favorite_focus": None
        },
        "history": []
    }

    if isinstance(existing, str):
        default_session["context"]["last_response_id"] = existing
        return default_session

    if not isinstance(existing, dict):
        return default_session

    # If it already looks like the new structure
    if "meta" in existing or "context" in existing or "profile" in existing:
        existing.setdefault("meta", {})
        existing.setdefault("context", {})
        existing.setdefault("profile", {})
        existing.setdefault("history", [])

        existing["meta"].setdefault("personality", "cartoon")
        existing["meta"].setdefault("preferred_style", "normal")
        existing["meta"].setdefault("created_at", datetime.utcnow().isoformat())
        existing["meta"]["updated_at"] = datetime.utcnow().isoformat()

        existing["context"].setdefault("last_response_id", None)
        existing["context"].setdefault("last_intent", None)
        existing["context"].setdefault("last_topic", None)

        existing["profile"].setdefault("name", None)
        existing["profile"].setdefault("playstyle", None)
        existing["profile"].setdefault("experience_level", None)
        existing["profile"].setdefault("favorite_focus", None)

        if not isinstance(existing["history"], list):
            existing["history"] = []

        return existing

    # Upgrade old flat structure to new structure
    upgraded = {
        "meta": {
            "personality": existing.get("personality", "cartoon"),
            "preferred_style": existing.get("preferred_style", "normal"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        },
        "context": {
            "last_response_id": existing.get("last_response_id"),
            "last_intent": existing.get("last_intent"),
            "last_topic": existing.get("last_topic")
        },
        "profile": {
            "name": None,
            "playstyle": None,
            "experience_level": None,
            "favorite_focus": None
        },
        "history": []
    }

    return upgraded


def get_session_memory(session_id: str):
    existing = conversation_memory.get(session_id)
    normalized = normalize_session_memory(existing)
    conversation_memory[session_id] = normalized
    save_memory()
    return normalized


def append_history(session_memory: dict, user_input: str, response_text: str):
    history = session_memory.setdefault("history", [])
    history.append({
        "user": user_input,
        "assistant": response_text,
        "timestamp": datetime.utcnow().isoformat()
    })

    # keep memory light
    if len(history) > 12:
        del history[:-12]


conversation_memory = load_memory()
game_facts_cache = load_game_facts()


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>SYNK</title>
        <style>
            * { box-sizing: border-box; }

            :root {
                --bg-1: #07111f;
                --bg-2: #0b1730;
                --panel: rgba(12, 20, 38, 0.72);
                --border: rgba(148, 163, 184, 0.14);
                --text: #e5eefc;
                --muted: #94a3b8;
                --shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
            }

            body {
                margin: 0;
                font-family: Inter, Arial, sans-serif;
                color: var(--text);
                min-height: 100vh;
                overflow: hidden;
                background:
                    radial-gradient(circle at 20% 20%, rgba(37, 99, 235, 0.22), transparent 28%),
                    radial-gradient(circle at 80% 15%, rgba(96, 165, 250, 0.18), transparent 25%),
                    radial-gradient(circle at 50% 100%, rgba(29, 78, 216, 0.15), transparent 35%),
                    linear-gradient(135deg, var(--bg-1), var(--bg-2));
            }

            .bg-grid {
                position: fixed;
                inset: 0;
                background-image:
                    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
                background-size: 36px 36px;
                mask-image: radial-gradient(circle at center, black 40%, transparent 95%);
                pointer-events: none;
            }

            .layout {
                display: flex;
                height: 100vh;
                width: 100%;
                position: relative;
                z-index: 1;
            }

            .sidebar {
                width: 340px;
                background: var(--panel);
                backdrop-filter: blur(18px);
                border-right: 1px solid var(--border);
                padding: 24px;
                display: flex;
                flex-direction: column;
                gap: 22px;
                box-shadow: var(--shadow);
            }

            .brand h1 {
                margin: 0;
                font-size: 34px;
                letter-spacing: 4px;
                font-weight: 800;
                background: linear-gradient(90deg, #ffffff, #93c5fd, #60a5fa);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .brand p {
                margin: 8px 0 0 0;
                color: var(--muted);
                line-height: 1.6;
                font-size: 14px;
            }

            .buddy-card,
            .status-card,
            .quick-card {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid var(--border);
                border-radius: 24px;
                padding: 18px;
                backdrop-filter: blur(16px);
            }

            .buddy-zone {
                min-height: 260px;
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
                overflow: hidden;
            }

            .buddy-ring {
                position: absolute;
                width: 260px;
                height: 260px;
                border-radius: 50%;
                border: 1px solid rgba(147, 197, 253, 0.16);
                animation: spin 16s linear infinite;
            }

            .buddy-ring::before,
            .buddy-ring::after {
                content: "";
                position: absolute;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #93c5fd;
                box-shadow: 0 0 20px rgba(147, 197, 253, 0.9);
            }

            .buddy-ring::before {
                top: -6px;
                left: 50%;
                transform: translateX(-50%);
            }

            .buddy-ring::after {
                bottom: 20px;
                left: 12px;
            }

            .buddy {
                width: 170px;
                height: 170px;
                border-radius: 50%;
                position: relative;
                background:
                    radial-gradient(circle at 30% 30%, #dbeafe 0%, #60a5fa 22%, #2563eb 58%, #1e40af 100%);
                box-shadow:
                    0 0 40px rgba(37, 99, 235, 0.45),
                    inset 0 0 25px rgba(255,255,255,0.15);
                animation: floatBuddy 4s ease-in-out infinite;
            }

            .buddy.speaking {
                animation: speakingPulse 0.9s ease-in-out infinite;
            }

            .buddy::before,
            .buddy::after {
                content: "";
                position: absolute;
                top: 58px;
                width: 18px;
                height: 18px;
                background: white;
                border-radius: 50%;
                animation: blink 4s infinite;
            }

            .buddy::before { left: 42px; }
            .buddy::after { right: 42px; }

            .mouth {
                position: absolute;
                left: 50%;
                bottom: 40px;
                transform: translateX(-50%);
                width: 42px;
                height: 20px;
                border-bottom: 4px solid white;
                border-radius: 0 0 40px 40px;
            }

            .status-card h3,
            .quick-card h3 {
                margin: 0 0 10px 0;
                font-size: 14px;
                color: #dbeafe;
            }

            .status-card p {
                margin: 0;
                color: var(--muted);
                line-height: 1.6;
                font-size: 14px;
            }

            .quick-buttons {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }

            .quick-btn,
            .reset-btn {
                border: 1px solid rgba(96, 165, 250, 0.18);
                background: rgba(30, 41, 59, 0.8);
                color: #dbeafe;
                border-radius: 14px;
                padding: 12px;
                cursor: pointer;
                font-size: 13px;
                transition: 0.2s ease;
            }

            .quick-btn:hover,
            .reset-btn:hover {
                transform: translateY(-2px);
                background: rgba(37, 99, 235, 0.22);
            }

            .reset-btn {
                margin-top: 12px;
                width: 100%;
                border-color: rgba(248, 113, 113, 0.2);
                background: rgba(127, 29, 29, 0.35);
                color: #fecaca;
            }

            .main {
                flex: 1;
                display: flex;
                flex-direction: column;
                min-width: 0;
            }

            .topbar {
                min-height: 78px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 12px 24px;
                border-bottom: 1px solid var(--border);
                background: rgba(7, 17, 31, 0.45);
                backdrop-filter: blur(16px);
                gap: 16px;
            }

            .topbar-title {
                font-size: 24px;
                font-weight: 800;
                letter-spacing: 2px;
                background: linear-gradient(90deg, #ffffff, #93c5fd, #60a5fa);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .topbar-sub {
                font-size: 13px;
                color: var(--muted);
            }

            .chip {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                border-radius: 999px;
                background: rgba(96, 165, 250, 0.12);
                border: 1px solid rgba(96, 165, 250, 0.16);
                color: #dbeafe;
                font-size: 12px;
                font-weight: 700;
            }

            .controls {
                display: flex;
                align-items: center;
                gap: 10px;
                flex-wrap: wrap;
                justify-content: flex-end;
            }

            .toggle,
            .select-shell {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                border-radius: 999px;
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid var(--border);
                color: #dbeafe;
                font-size: 12px;
                font-weight: 700;
            }

            .toggle input {
                width: auto;
                margin: 0;
                accent-color: #60a5fa;
            }

            .voice-style-select,
            .personality-select {
                background: transparent;
                color: #dbeafe;
                border: none;
                outline: none;
                font-size: 12px;
                font-weight: 700;
                cursor: pointer;
            }

            .voice-style-select option,
            .personality-select option {
                background: #0f172a;
                color: #dbeafe;
            }

            .chat-wrap {
                flex: 1;
                overflow-y: auto;
                padding: 28px;
                display: flex;
                flex-direction: column;
                gap: 18px;
                scroll-behavior: smooth;
            }

            .message-row {
                display: flex;
                width: 100%;
                animation: fadeInUp 0.28s ease;
            }

            .message-row.user {
                justify-content: flex-end;
            }

            .message-row.bot {
                justify-content: flex-start;
            }

            .message {
                max-width: 760px;
                padding: 16px 18px;
                border-radius: 22px;
                line-height: 1.7;
                white-space: pre-wrap;
                word-wrap: break-word;
                box-shadow: 0 14px 34px rgba(0, 0, 0, 0.18);
            }

            .message.user {
                background: linear-gradient(135deg, #2563eb, #1d4ed8);
                color: white;
                border-bottom-right-radius: 8px;
            }

            .message.bot {
                background: rgba(17, 24, 39, 0.9);
                border: 1px solid var(--border);
                color: var(--text);
                border-bottom-left-radius: 8px;
            }

            .message-meta {
                font-size: 12px;
                color: #94a3b8;
                margin-top: 8px;
            }

            .input-bar {
                padding: 18px 24px 24px;
                border-top: 1px solid var(--border);
                background: rgba(7, 17, 31, 0.45);
                backdrop-filter: blur(16px);
            }

            .input-shell {
                max-width: 980px;
                margin: 0 auto;
                background: rgba(15, 23, 42, 0.82);
                border: 1px solid var(--border);
                border-radius: 24px;
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 10px 10px 16px;
                box-shadow: var(--shadow);
            }

            input[type="text"] {
                flex: 1;
                background: transparent;
                border: none;
                outline: none;
                color: white;
                font-size: 16px;
                padding: 12px 8px;
            }

            input[type="text"]::placeholder {
                color: #64748b;
            }

            .send-btn,
            .voice-btn,
            .stop-btn {
                border: none;
                color: white;
                padding: 14px 18px;
                border-radius: 18px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 800;
                transition: 0.2s ease;
            }

            .send-btn,
            .voice-btn {
                background: linear-gradient(135deg, #60a5fa, #2563eb);
            }

            .stop-btn {
                background: linear-gradient(135deg, #ef4444, #dc2626);
            }

            .voice-btn.listening {
                background: linear-gradient(135deg, #ef4444, #dc2626);
            }

            .typing {
                display: flex;
                align-items: center;
                gap: 6px;
            }

            .typing span {
                width: 8px;
                height: 8px;
                background: #93c5fd;
                border-radius: 50%;
                display: inline-block;
                animation: bounce 1s infinite ease-in-out;
            }

            .typing span:nth-child(2) { animation-delay: 0.15s; }
            .typing span:nth-child(3) { animation-delay: 0.3s; }

            @keyframes floatBuddy {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
            }

            @keyframes speakingPulse {
                0%, 100% { transform: scale(1) translateY(0); }
                50% { transform: scale(1.04) translateY(-4px); }
            }

            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            @keyframes blink {
                0%, 45%, 100% { transform: scaleY(1); }
                48%, 52% { transform: scaleY(0.12); }
            }

            @keyframes bounce {
                0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
                40% { transform: translateY(-6px); opacity: 1; }
            }

            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            @media (max-width: 980px) {
                .sidebar { display: none; }
                .chat-wrap { padding: 18px; }
                .input-bar { padding: 14px 16px 18px; }
                .message { max-width: 100%; }
                .input-shell { flex-wrap: wrap; }
                .topbar { flex-direction: column; align-items: flex-start; }
                .controls { justify-content: flex-start; }
            }
        </style>
    </head>
    <body>
        <div class="bg-grid"></div>

        <div class="layout">
            <aside class="sidebar">
                <div class="brand">
                    <h1>SYNK</h1>
                    <p>Your Crimson Desert AI sidekick with memory, voice input, spoken responses, and switchable personalities.</p>
                </div>

                <div class="buddy-card">
                    <div class="buddy-zone">
                        <div class="buddy-ring"></div>
                        <div id="buddy" class="buddy">
                            <div class="mouth"></div>
                        </div>
                    </div>
                </div>

                <div class="status-card">
                    <h3>Buddy Status</h3>
                    <p id="buddy-status">Idle. I can listen, think, speak, and remember.</p>
                </div>

                <div class="quick-card">
                    <h3>Quick Prompts</h3>
                    <div class="quick-buttons">
                        <button class="quick-btn" onclick="fillPrompt('My name is Roy')">Set name</button>
                        <button class="quick-btn" onclick="fillPrompt('How do I prepare for a boss fight?')">Boss prep</button>
                        <button class="quick-btn" onclick="fillPrompt('What gear should I focus on early?')">Best gear</button>
                        <button class="quick-btn" onclick="fillPrompt('Now make that shorter')">Follow-up</button>
                    </div>
                    <button class="reset-btn" onclick="resetMemory()">Reset memory</button>
                </div>
            </aside>

            <main class="main">
                <div class="topbar">
                    <div>
                        <div class="topbar-title">SYNK</div>
                        <div class="topbar-sub">Gemini-style voice mode enabled</div>
                    </div>
                    <div class="controls">
                        <label class="toggle">
                            <input id="autoSpeakToggle" type="checkbox" checked />
                            Auto voice
                        </label>

                        <label class="select-shell">
                            Voice mood
                            <select id="voiceStyleSelect" class="voice-style-select">
                                <option value="gemini" selected>Gemini Style</option>
                                <option value="cartoon">Cartoon</option>
                                <option value="playful">Playful</option>
                                <option value="normal">Normal</option>
                                <option value="deep">Deep</option>
                            </select>
                        </label>

                        <label class="select-shell">
                            Personality
                            <select id="personalitySelect" class="personality-select">
                                <option value="cartoon">Cartoon</option>
                                <option value="calm_strategist" selected>Calm Strategist</option>
                                <option value="hype_mode">Hype Mode</option>
                                <option value="serious_tactical">Serious Tactical</option>
                            </select>
                        </label>

                        <div class="chip">ONLINE</div>
                    </div>
                </div>

                <div id="chat" class="chat-wrap">
                    <div class="message-row bot">
                        <div class="message bot">Hey. I’m SYNK. Pick a voice mood and personality, then let’s get to work.</div>
                    </div>

                    <div class="message-row bot" id="typing-row" style="display:none;">
                        <div class="message bot">
                            <div class="typing">
                                <span></span><span></span><span></span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="input-bar">
                    <div class="input-shell">
                        <input id="question" type="text" placeholder="Message SYNK..." />
                        <button class="send-btn" onclick="askSidekick()">Send</button>
                        <button id="voiceBtn" class="voice-btn" onclick="toggleVoiceInput()">🎤 Talk</button>
                        <button class="stop-btn" onclick="stopSpeaking()">Stop</button>
                    </div>
                </div>
            </main>
        </div>

        <script>
            const input = document.getElementById("question");
            const chat = document.getElementById("chat");
            const typingRow = document.getElementById("typing-row");
            const buddyStatus = document.getElementById("buddy-status");
            const voiceBtn = document.getElementById("voiceBtn");
            const buddy = document.getElementById("buddy");
            const autoSpeakToggle = document.getElementById("autoSpeakToggle");
            const voiceStyleSelect = document.getElementById("voiceStyleSelect");
            const personalitySelect = document.getElementById("personalitySelect");

            let sessionId = localStorage.getItem("synk_session_id");
            if (!sessionId) {
                sessionId = crypto.randomUUID();
                localStorage.setItem("synk_session_id", sessionId);
            }

            voiceStyleSelect.value = localStorage.getItem("synk_voice_style") || "gemini";
            personalitySelect.value = localStorage.getItem("synk_personality") || "calm_strategist";

            let isRequestInFlight = false;
            let isListening = false;
            let availableVoices = [];
            let selectedVoice = null;

            const VOICE_STYLES = {
                gemini: { rate: 1.0, pitch: 1.05, volume: 1.0 },
                cartoon: { rate: 1.15, pitch: 1.45, volume: 1.0 },
                playful: { rate: 1.05, pitch: 1.2, volume: 1.0 },
                normal: { rate: 1.0, pitch: 1.0, volume: 1.0 },
                deep: { rate: 0.92, pitch: 0.82, volume: 1.0 }
            };

            function addMessage(text, role, metaText = "") {
                const row = document.createElement("div");
                row.className = "message-row " + role;

                const bubble = document.createElement("div");
                bubble.className = "message " + role;
                bubble.textContent = text;

                if (metaText && role === "bot") {
                    const meta = document.createElement("div");
                    meta.className = "message-meta";
                    meta.textContent = metaText;
                    bubble.appendChild(document.createElement("br"));
                    bubble.appendChild(meta);
                }

                row.appendChild(bubble);
                chat.insertBefore(row, typingRow);
                chat.scrollTop = chat.scrollHeight;
            }

            function fillPrompt(text) {
                input.value = text;
                input.focus();
            }

            function setStatus(text) {
                buddyStatus.textContent = text;
            }

            function pickPreferredVoice(voices) {
                return (
                    voices.find(v => /Microsoft Aria/i.test(v.name)) ||
                    voices.find(v => /Microsoft Jenny/i.test(v.name)) ||
                    voices.find(v => /Google US English/i.test(v.name)) ||
                    voices.find(v => /Samantha/i.test(v.name)) ||
                    voices.find(v => /Zira/i.test(v.name)) ||
                    voices.find(v => v.lang === "en-US") ||
                    voices.find(v => v.lang && v.lang.startsWith("en")) ||
                    null
                );
            }

            function loadVoices() {
                availableVoices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
                selectedVoice = pickPreferredVoice(availableVoices);
                console.log("Selected voice:", selectedVoice ? selectedVoice.name : "None");
            }

            if ("speechSynthesis" in window) {
                loadVoices();
                window.speechSynthesis.onvoiceschanged = loadVoices;
            }

            function getVoiceStyleSettings() {
                const style = voiceStyleSelect.value || "gemini";
                return VOICE_STYLES[style] || VOICE_STYLES.gemini;
            }

            function speak(text) {
                if (!autoSpeakToggle.checked) return;
                if (!("speechSynthesis" in window)) return;

                window.speechSynthesis.cancel();

                const style = getVoiceStyleSettings();
                const utterance = new SpeechSynthesisUtterance(text);

                utterance.lang = selectedVoice?.lang || "en-US";
                utterance.voice = selectedVoice || null;
                utterance.rate = style.rate;
                utterance.pitch = style.pitch;
                utterance.volume = style.volume;

                utterance.onstart = function () {
                    buddy.classList.add("speaking");
                    setStatus("SYNK is talking...");
                };

                utterance.onend = function () {
                    buddy.classList.remove("speaking");
                    setStatus("Ready for your next question.");
                };

                utterance.onerror = function () {
                    buddy.classList.remove("speaking");
                    setStatus("Voice playback had an issue.");
                };

                window.speechSynthesis.speak(utterance);
            }

            function stopSpeaking() {
                if ("speechSynthesis" in window) {
                    window.speechSynthesis.cancel();
                }
                buddy.classList.remove("speaking");
                setStatus("Voice stopped.");
            }

            async function askSidekick(forcedQuestion = null) {
                const question = (forcedQuestion ?? input.value).trim();
                if (!question || isRequestInFlight) return;

                isRequestInFlight = true;

                if ("speechSynthesis" in window) {
                    window.speechSynthesis.cancel();
                }

                addMessage(question, "user");
                input.value = "";
                setStatus("Thinking, routing personality, and preparing a reply...");
                typingRow.style.display = "flex";
                chat.scrollTop = chat.scrollHeight;

                try {
                    const res = await fetch("/ask", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            question: question,
                            session_id: sessionId,
                            personality: personalitySelect.value
                        })
                    });

                    if (!res.ok) {
                        const errorData = await res.json().catch(() => ({}));
                        throw new Error(errorData.detail || "Request failed.");
                    }

                    const data = await res.json();

                    typingRow.style.display = "none";

                    const source = data.source || "unknown";
                    const confidence = typeof data.confidence === "number"
                        ? Math.round(data.confidence * 100) + "%"
                        : "n/a";

                    const metaText = `source: ${source} | confidence: ${confidence}`;
                    addMessage(data.response, "bot", metaText);

                    setStatus("Answer ready.");
                    speak(data.response);
                } catch (error) {
                    typingRow.style.display = "none";
                    addMessage(error.message || "Something went wrong talking to the server.", "bot");
                    setStatus("Connection issue.");
                } finally {
                    isRequestInFlight = false;
                }
            }

            async function resetMemory() {
                try {
                    const res = await fetch("/reset", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            session_id: sessionId
                        })
                    });

                    if (!res.ok) {
                        throw new Error("Reset request failed.");
                    }

                    stopSpeaking();
                    addMessage("Memory cleared for this session.", "bot");
                    setStatus("Memory cleared. Starting fresh.");
                } catch (error) {
                    addMessage("Couldn't reset memory right now.", "bot");
                    setStatus("Reset failed.");
                }
            }

            voiceStyleSelect.addEventListener("change", function () {
                localStorage.setItem("synk_voice_style", this.value);
                setStatus("Voice mood changed to " + this.value + ".");
            });

            personalitySelect.addEventListener("change", function () {
                localStorage.setItem("synk_personality", this.value);
                setStatus("Personality changed to " + this.value.replaceAll("_", " ") + ".");
            });

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            let recognition = null;

            if (SpeechRecognition) {
                recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.lang = "en-US";

                recognition.onstart = function () {
                    isListening = true;
                    stopSpeaking();
                    setStatus("Listening...");
                    voiceBtn.classList.add("listening");
                    voiceBtn.textContent = "🎤 Listening";
                };

                recognition.onresult = function (event) {
                    const transcript = event.results[0][0].transcript.trim();
                    input.value = transcript;
                    setStatus("Voice captured. Sending...");
                    askSidekick(transcript);
                };

                recognition.onerror = function (event) {
                    isListening = false;
                    voiceBtn.classList.remove("listening");
                    voiceBtn.textContent = "🎤 Talk";

                    if (event.error === "not-allowed") {
                        setStatus("Microphone permission was blocked.");
                    } else if (event.error === "no-speech") {
                        setStatus("I didn’t hear anything. Try again.");
                    } else {
                        setStatus("Voice error: " + event.error);
                    }
                };

                recognition.onend = function () {
                    isListening = false;
                    voiceBtn.classList.remove("listening");
                    voiceBtn.textContent = "🎤 Talk";
                };
            }

            function toggleVoiceInput() {
                if (!recognition) {
                    alert("Voice input is not supported in this browser. Try Chrome or Edge.");
                    return;
                }

                if (isListening) {
                    recognition.stop();
                    setStatus("Stopped listening.");
                    return;
                }

                recognition.start();
            }

            input.addEventListener("keydown", function(event) {
                if (event.key === "Enter") {
                    askSidekick();
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/ask")
async def ask(payload: AskRequest):
    user_input = payload.question.strip()

    if not user_input:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if len(user_input) < 2:
        raise HTTPException(status_code=400, detail="Input is too short.")

    session_id = payload.session_id or str(uuid.uuid4())
    session_memory = get_session_memory(session_id)

    personality = payload.personality or session_memory["meta"].get("personality", "calm_strategist")
    session_memory["meta"]["personality"] = personality
    session_memory["meta"]["updated_at"] = datetime.utcnow().isoformat()

    previous_response_id = session_memory["context"].get("last_response_id")

    log_event("SYNK REQUEST", {
        "user_input": user_input,
        "session_id": session_id,
        "personality": personality,
        "previous_response_id": previous_response_id
    })

    try:
        result = sidekick_reply(
            user_input=user_input,
            game_data=game_facts_cache,
            previous_response_id=previous_response_id,
            personality=personality,
            session_memory=session_memory
        )
    except TypeError:
        # fallback in case logic.py hasn't been updated yet
        result = sidekick_reply(
            user_input=user_input,
            game_data=game_facts_cache,
            previous_response_id=previous_response_id,
            personality=personality
        )

    response_text = result.get("response", "")
    source = result.get("source", "unknown")
    confidence = result.get("confidence", 0.5)
    intent = result.get("intent")
    topic = result.get("topic")
    preferred_style = result.get("preferred_style")
    response_id = result.get("response_id")

    if response_id:
        session_memory["context"]["last_response_id"] = response_id

    if intent:
        session_memory["context"]["last_intent"] = intent

    if topic:
        session_memory["context"]["last_topic"] = topic

    if preferred_style:
        session_memory["meta"]["preferred_style"] = preferred_style

    if result.get("personality"):
        session_memory["meta"]["personality"] = result["personality"]

    # optional profile updates returned by logic.py
    profile_updates = result.get("profile_updates", {})
    if isinstance(profile_updates, dict):
        for key, value in profile_updates.items():
            if key in session_memory["profile"] and value:
                session_memory["profile"][key] = value

    append_history(session_memory, user_input, response_text)

    conversation_memory[session_id] = session_memory
    save_memory()

    log_event("SYNK RESPONSE", {
        "intent": intent,
        "topic": topic,
        "source": source,
        "confidence": confidence,
        "response_preview": response_text[:160]
    })

    return {
        "response": response_text,
        "source": source,
        "confidence": confidence,
        "intent": intent,
        "topic": topic,
        "session_id": session_id,
        "memory": session_memory
    }


@app.post("/reset")
async def reset(payload: ResetRequest):
    session_id = payload.session_id

    if session_id in conversation_memory:
        del conversation_memory[session_id]
        save_memory()

    return {"ok": True}