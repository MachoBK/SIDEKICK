import { useEffect, useMemo, useRef, useState } from "react";
import SynkWaterBackground from "./components/SynkWaterBackground";

const API_BASE_URL = "https://sidekick-p0n2.onrender.com";
const ENABLE_TEXT_TO_SPEECH = false;

const LANGUAGES = {
  English: { label: "English", voiceCode: "en-US" },
  Spanish: { label: "Spanish", voiceCode: "es-ES" },
  French: { label: "French", voiceCode: "fr-FR" },
  Japanese: { label: "Japanese", voiceCode: "ja-JP" },
};

export default function App() {
  const [avatarState, setAvatarState] = useState("idle");
  const [statusText, setStatusText] = useState("Ready.");
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isMicMuted, setIsMicMuted] = useState(false);

  const [language, setLanguage] = useState("English");
  const [latestUserText, setLatestUserText] = useState("");
  const [latestAssistantText, setLatestAssistantText] = useState(
    "Ask me about a video game."
  );

  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);

  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const micStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);
  const mountedRef = useRef(true);
  const micMutedRef = useRef(false);

  function setMicMutedState(value) {
    micMutedRef.current = value;
    setIsMicMuted(value);
  }

  function getRealtimeStatusText() {
    return micMutedRef.current
      ? "Mic muted. SYNK can finish speaking."
      : "Realtime on. Speak naturally.";
  }

  async function readErrorMessage(res, fallback) {
    try {
      const text = await res.text();

      if (!text) return fallback;

      try {
        const parsed = JSON.parse(text);
        return (
          parsed?.error?.message ||
          parsed?.detail ||
          parsed?.message ||
          text ||
          fallback
        );
      } catch {
        return text;
      }
    } catch {
      return fallback;
    }
  }

  async function sendTypedMessage() {
    const cleanMessage = inputText.trim();
    if (!cleanMessage || isSending) return;

    setInputText("");
    setLatestUserText(cleanMessage);
    setLatestAssistantText("");
    setIsSending(true);
    setAvatarState("thinking");
    setStatusText("Thinking...");

    try {
      const res = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: cleanMessage,
          personality: "calm_strategist",
          mode: "game",
          language,
        }),
      });

      if (!res.ok) {
        const errorText = await readErrorMessage(res, "Text chat failed.");
        throw new Error(errorText);
      }

      const data = await res.json();
      const reply =
        data.message || data.reply || "I don't have that information yet.";

      setLatestAssistantText(reply);
      setAvatarState("idle");
      setStatusText("SYNK responded.");

      if (ENABLE_TEXT_TO_SPEECH) {
        speakText(reply);
      }
    } catch (error) {
      console.error("Text chat failed:", error);
      setAvatarState("error");
      setStatusText("Text chat failed.");
      setLatestAssistantText(`Error: ${error.message}`);
    } finally {
      setIsSending(false);

      setTimeout(() => {
        if (mountedRef.current && !isConnected) {
          setAvatarState("idle");
          setStatusText("Ready.");
        }
      }, 1200);
    }
  }

  function handleInputKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendTypedMessage();
    }
  }

  function speakText(text) {
    if (!text || !window.speechSynthesis) return;

    window.speechSynthesis.cancel();

    const selectedVoiceCode = LANGUAGES[language]?.voiceCode || "en-US";
    const utterance = new SpeechSynthesisUtterance(text);

    utterance.lang = selectedVoiceCode;
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.volume = 1;

    const voices = window.speechSynthesis.getVoices();
    const matchingVoice = voices.find((voice) =>
      voice.lang
        .toLowerCase()
        .startsWith(selectedVoiceCode.toLowerCase().slice(0, 2))
    );

    if (matchingVoice) utterance.voice = matchingVoice;

    utterance.onstart = () => {
      setAvatarState("talking");
      setStatusText("SYNK is speaking...");
    };

    utterance.onend = () => {
      if (isConnected) {
        setAvatarState("listening");
        setStatusText(getRealtimeStatusText());
      } else {
        setAvatarState("idle");
        setStatusText("Ready.");
      }
    };

    window.speechSynthesis.speak(utterance);
  }

  function stopRealtime() {
    if (dcRef.current) {
      try {
        dcRef.current.close();
      } catch {}
      dcRef.current = null;
    }

    if (pcRef.current) {
      try {
        pcRef.current.getSenders().forEach((sender) => {
          try {
            sender.track?.stop();
          } catch {}
        });
        pcRef.current.close();
      } catch {}
      pcRef.current = null;
    }

    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }

    if (remoteAudioRef.current) {
      try {
        remoteAudioRef.current.pause();
        remoteAudioRef.current.srcObject = null;
      } catch {}
      remoteAudioRef.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
    setMicMutedState(false);
    setAvatarState("idle");
    setStatusText("Ready.");
  }

  async function startRealtime() {
    if (isConnected || isConnecting) return;

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Microphone access is not supported in this browser.");
      }

      setIsConnecting(true);
      setMicMutedState(false);
      setAvatarState("thinking");
      setStatusText("Connecting realtime voice...");
      setLatestAssistantText("");

      const sessionRes = await fetch(
        `${API_BASE_URL}/realtime/session?language=${encodeURIComponent(
          language
        )}`
      );

      if (!sessionRes.ok) {
        const errorText = await readErrorMessage(
          sessionRes,
          "Could not create realtime session."
        );
        throw new Error(errorText);
      }

      const sessionData = await sessionRes.json();

      const ephemeralKey =
        sessionData?.client_secret?.value || sessionData?.value;

      if (!ephemeralKey) {
        console.error("Realtime session response:", sessionData);
        throw new Error("No realtime client secret returned from backend.");
      }

      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      pc.onconnectionstatechange = () => {
        if (
          pc.connectionState === "failed" ||
          pc.connectionState === "disconnected" ||
          pc.connectionState === "closed"
        ) {
          if (mountedRef.current) {
            setIsConnected(false);
            setIsConnecting(false);
            setMicMutedState(false);
            setAvatarState("idle");
            setStatusText("Realtime disconnected.");
          }
        }
      };

      const remoteAudio = new Audio();
      remoteAudio.autoplay = true;
      remoteAudioRef.current = remoteAudio;

      pc.ontrack = (event) => {
        remoteAudio.srcObject = event.streams[0];

        remoteAudio.play().catch(() => {
          // Browser may block autoplay until user gesture.
        });

        setAvatarState("talking");
        setStatusText("SYNK is speaking...");
      };

      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      micStreamRef.current = micStream;

      micStream.getTracks().forEach((track) => {
        track.enabled = true;
        pc.addTrack(track, micStream);
      });

      const dc = pc.createDataChannel("oai-events");
      dcRef.current = dc;

      dc.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        setMicMutedState(false);
        setAvatarState("listening");
        setStatusText("Realtime on. Speak naturally.");
      };

      dc.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (
            msg.type ===
            "conversation.item.input_audio_transcription.completed"
          ) {
            if (msg.transcript) setLatestUserText(msg.transcript);
          }

          if (msg.type === "response.created") {
            setLatestAssistantText("");
            setAvatarState("thinking");
            setStatusText("Thinking...");
          }

          if (msg.type === "response.audio_transcript.delta") {
            if (msg.delta) {
              setLatestAssistantText((prev) => prev + msg.delta);
            }
          }

          if (
            msg.type === "response.audio.done" ||
            msg.type === "response.done"
          ) {
            setAvatarState("listening");
            setStatusText(getRealtimeStatusText());
          }

          if (msg.type === "error") {
            console.error("Realtime API error:", msg);
            setAvatarState("error");
            setStatusText("Realtime error.");
            setLatestAssistantText(
              `Realtime error: ${msg.error?.message || "Unknown error"}`
            );
          }
        } catch {
          // Ignore non-JSON events.
        }
      };

      dc.onerror = () => {
        setAvatarState("error");
        setStatusText("Realtime connection error.");
      };

      dc.onclose = () => {
        setIsConnected(false);
        setIsConnecting(false);
        setMicMutedState(false);
      };

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const sdpRes = await fetch("https://api.openai.com/v1/realtime/calls", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${ephemeralKey}`,
          "Content-Type": "application/sdp",
        },
        body: offer.sdp,
      });

      if (!sdpRes.ok) {
        const errorText = await readErrorMessage(
          sdpRes,
          "Realtime SDP request failed."
        );
        throw new Error(errorText);
      }

      const answerSdp = await sdpRes.text();

      if (!mountedRef.current) {
        return;
      }

      if (!pcRef.current || pcRef.current !== pc) {
        return;
      }

      if (pc.signalingState === "closed") {
        return;
      }

      await pc.setRemoteDescription({
        type: "answer",
        sdp: answerSdp,
      });
    } catch (error) {
      console.error("Realtime failed:", error);
      setLatestAssistantText(`Realtime error: ${error.message}`);
      setAvatarState("error");
      setStatusText("Realtime failed.");

      if (pcRef.current) {
        stopRealtime();
      } else {
        setIsConnected(false);
        setIsConnecting(false);
        setMicMutedState(false);
        setAvatarState("idle");
        setStatusText("Ready.");
      }
    }
  }

  function toggleRealtime() {
    if (isConnecting) return;

    if (!isConnected) {
      startRealtime();
      return;
    }

    const nextMutedState = !micMutedRef.current;

    if (micStreamRef.current) {
      micStreamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = !nextMutedState;
      });
    }

    setMicMutedState(nextMutedState);

    if (nextMutedState) {
      setStatusText("Mic muted. SYNK can finish speaking.");
    } else {
      setStatusText("Realtime on. Speak naturally.");
    }
  }

  function handleLanguageChange(event) {
    const selectedLanguage = event.target.value;
    setLanguage(selectedLanguage);
    setStatusText(`Language set to ${selectedLanguage}.`);

    if (isConnected || isConnecting) {
      stopRealtime();
    }
  }

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      stopRealtime();
    };
  }, []);

  const badgeLabel = isConnecting
    ? "Connecting"
    : isMicMuted
    ? "Muted"
    : isConnected
    ? "Realtime"
    : avatarState === "talking"
    ? "Speaking"
    : language;

  const orbClass = useMemo(() => {
    if (isConnecting || isSending) return "thinking";
    if (isConnected && avatarState === "talking") return "talking";
    if (isConnected) return "listening";
    return avatarState;
  }, [avatarState, isConnected, isConnecting, isSending]);

  return (
    <div className="synk-shell">
      <style>{`
        * {
          box-sizing: border-box;
        }

        html,
        body,
        #root {
          width: 100%;
          height: 100%;
          margin: 0;
          padding: 0;
          overflow: hidden;
          background: #020512;
          font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .synk-shell {
          position: relative;
          width: 100%;
          height: 100vh;
          overflow: hidden;
          color: white;
          background: #020512;
        }

        .synk-topbar {
          position: absolute;
          top: 26px;
          left: 28px;
          right: 28px;
          z-index: 5;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
        }

        .synk-logo {
          padding: 18px 34px;
          border-radius: 50px;
          border: 1px solid rgba(155, 226, 255, 0.28);
          background: rgba(2, 10, 24, 0.38);
          backdrop-filter: blur(24px);
          box-shadow:
            0 0 40px rgba(0, 180, 255, 0.1),
            inset 0 0 28px rgba(0, 204, 255, 0.04);
        }

        .synk-logo h1 {
          margin: 0;
          font-size: clamp(2.4rem, 4vw, 4.4rem);
          letter-spacing: 0.22em;
          font-weight: 300;
          color: #c8f6ff;
          text-shadow:
            0 0 16px rgba(0, 225, 255, 0.65),
            0 0 42px rgba(0, 120, 255, 0.34);
        }

        .synk-language-select {
          padding: 13px 18px;
          border-radius: 999px;
          border: 1px solid rgba(138, 239, 255, 0.5);
          background: rgba(2, 10, 24, 0.5);
          color: #e8fbff;
          outline: none;
          backdrop-filter: blur(18px);
          box-shadow:
            0 0 26px rgba(0, 225, 255, 0.14),
            inset 0 0 18px rgba(0, 225, 255, 0.06);
        }

        .synk-language-select option {
          background: #020512;
          color: #e8fbff;
        }

        .synk-main {
          position: relative;
          z-index: 3;
          width: 100%;
          height: 100%;
          display: grid;
          place-items: center;
          padding: 124px 24px 44px;
        }

        .synk-stage {
          width: min(980px, 100%);
          height: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 18px;
        }

        .synk-avatar-wrap {
          position: relative;
          width: min(650px, 100%);
          height: min(38vh, 410px);
          min-height: 240px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .synk-avatar-ring {
          position: absolute;
          width: min(430px, 70vw);
          aspect-ratio: 1;
          border-radius: 50%;
          border: 1px solid rgba(0, 225, 255, 0.42);
          box-shadow:
            0 0 0 18px rgba(0, 225, 255, 0.025),
            0 0 110px rgba(0, 225, 255, 0.18),
            inset 0 0 60px rgba(0, 225, 255, 0.06);
          pointer-events: none;
          animation: ringBreathe 6s ease-in-out infinite;
        }

        .synk-avatar-ring::before,
        .synk-avatar-ring::after {
          content: "";
          position: absolute;
          border-radius: inherit;
          inset: 16px;
          border: 1px solid rgba(91, 171, 255, 0.18);
        }

        .synk-avatar-ring::after {
          inset: -22px;
          border-color: rgba(153, 105, 255, 0.16);
        }

        .synk-avatar-core {
          position: relative;
          width: 100%;
          height: 100%;
          display: grid;
          place-items: center;
        }

        .synk-orb {
          position: relative;
          width: min(250px, 52vw);
          aspect-ratio: 1;
          border-radius: 50%;
          display: grid;
          place-items: center;
          background:
            radial-gradient(circle at 50% 42%, rgba(190, 250, 255, 0.58), rgba(0, 225, 255, 0.18) 30%, rgba(0, 28, 55, 0.16) 58%, transparent 72%),
            radial-gradient(circle at center, rgba(0, 225, 255, 0.22), transparent 64%);
          box-shadow:
            0 0 42px rgba(0, 225, 255, 0.45),
            0 0 120px rgba(0, 125, 255, 0.22),
            inset 0 0 48px rgba(0, 225, 255, 0.18);
          animation: orbIdle 4s ease-in-out infinite;
        }

        .synk-orb::before {
          content: "";
          position: absolute;
          inset: -28px;
          border-radius: inherit;
          background:
            repeating-radial-gradient(
              circle,
              rgba(0, 225, 255, 0.32) 0px,
              rgba(0, 225, 255, 0.13) 2px,
              transparent 7px,
              transparent 26px
            );
          opacity: 0.55;
          animation: orbRipple 4s ease-in-out infinite;
        }

        .synk-orb::after {
          content: "";
          position: absolute;
          inset: 28px;
          border-radius: inherit;
          border: 1px solid rgba(210, 250, 255, 0.36);
          box-shadow:
            inset 0 0 26px rgba(255, 255, 255, 0.1),
            0 0 28px rgba(0, 225, 255, 0.22);
        }

        .synk-orb-word {
          position: relative;
          z-index: 2;
          padding-left: 0.22em;
          font-size: clamp(2rem, 5vw, 4.8rem);
          letter-spacing: 0.22em;
          font-weight: 300;
          color: #e6fbff;
          text-shadow:
            0 0 18px rgba(0, 225, 255, 0.9),
            0 0 60px rgba(0, 120, 255, 0.45);
        }

        .synk-orb.listening {
          animation: orbListening 1.7s ease-in-out infinite;
        }

        .synk-orb.talking {
          animation: orbTalking 0.7s ease-in-out infinite;
        }

        .synk-orb.thinking {
          animation: orbThinking 1.1s ease-in-out infinite;
        }

        .synk-orb.error {
          animation: orbError 0.8s ease-in-out infinite;
        }

        .synk-wave {
          position: absolute;
          bottom: 18%;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          align-items: end;
          justify-content: center;
          gap: 7px;
          height: 54px;
          z-index: 2;
        }

        .synk-wave span {
          width: 5px;
          height: 14px;
          border-radius: 999px;
          background: rgba(180, 250, 255, 0.86);
          box-shadow: 0 0 14px rgba(0, 225, 255, 0.72);
          animation: waveIdle 1.6s ease-in-out infinite;
          opacity: 0.72;
        }

        .synk-wave span:nth-child(2) { animation-delay: 0.1s; }
        .synk-wave span:nth-child(3) { animation-delay: 0.2s; }
        .synk-wave span:nth-child(4) { animation-delay: 0.3s; }
        .synk-wave span:nth-child(5) { animation-delay: 0.4s; }
        .synk-wave span:nth-child(6) { animation-delay: 0.5s; }
        .synk-wave span:nth-child(7) { animation-delay: 0.6s; }

        .synk-orb.talking .synk-wave span,
        .synk-orb.listening .synk-wave span {
          animation-name: waveActive;
          animation-duration: 0.55s;
        }

        .synk-chat-panel {
          width: min(760px, 90vw);
          max-height: 170px;
          overflow-y: auto;
          padding: 18px 24px;
          color: #d1f5ff;
          font-size: clamp(1rem, 1.2vw, 1.2rem);
          line-height: 1.6;
          text-align: left;
          background: rgba(2, 10, 24, 0.35);
          border: 1px solid rgba(125, 211, 252, 0.18);
          border-radius: 24px;
          backdrop-filter: blur(16px);
          box-shadow:
            0 0 40px rgba(0, 180, 255, 0.08),
            inset 0 0 22px rgba(0, 225, 255, 0.035);
        }

        .synk-chat-row {
          margin-bottom: 10px;
        }

        .synk-chat-row:last-child {
          margin-bottom: 0;
        }

        .synk-chat-label {
          display: inline-block;
          min-width: 58px;
          color: #8ef4ff;
          font-weight: 700;
        }

        .synk-chat-text {
          color: #e8fbff;
        }

        .synk-input-row {
          width: min(760px, 90vw);
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px;
          border-radius: 999px;
          border: 1px solid rgba(125, 211, 252, 0.18);
          background: rgba(2, 10, 24, 0.36);
          backdrop-filter: blur(18px);
          box-shadow:
            0 0 30px rgba(0, 180, 255, 0.08),
            inset 0 0 24px rgba(0, 225, 255, 0.035);
        }

        .synk-text-input {
          flex: 1;
          min-width: 0;
          border: none;
          outline: none;
          background: transparent;
          color: #e8fbff;
          padding: 14px 18px;
          font-size: 1rem;
        }

        .synk-text-input::placeholder {
          color: rgba(209, 245, 255, 0.55);
        }

        .synk-send-button {
          border: 1px solid rgba(138, 239, 255, 0.65);
          background:
            radial-gradient(circle at 50% 30%, rgba(184, 246, 255, 0.3), rgba(0, 180, 255, 0.16) 48%, rgba(2, 8, 22, 0.9) 100%);
          color: #e9fbff;
          min-width: 92px;
          padding: 13px 18px;
          border-radius: 999px;
          cursor: pointer;
          font-weight: 700;
          letter-spacing: 0.04em;
          box-shadow:
            0 0 22px rgba(0, 225, 255, 0.28),
            inset 0 0 18px rgba(0, 225, 255, 0.08);
          transition: transform 180ms ease, opacity 180ms ease;
        }

        .synk-send-button:hover {
          transform: scale(1.04);
        }

        .synk-send-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          transform: none;
        }

        .synk-mic-wrap {
          margin-top: 4px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
        }

        .synk-mic-button {
          position: relative;
          width: 118px;
          height: 118px;
          border-radius: 999px;
          border: 2px solid rgba(138, 239, 255, 0.8);
          background:
            radial-gradient(circle at 50% 42%, rgba(184, 246, 255, 0.28), rgba(0, 180, 255, 0.16) 38%, rgba(2, 8, 22, 0.9) 72%),
            rgba(2, 8, 22, 0.92);
          color: #e9fbff;
          cursor: pointer;
          box-shadow:
            0 0 32px rgba(0, 225, 255, 0.55),
            0 0 90px rgba(0, 125, 255, 0.24),
            inset 0 0 30px rgba(0, 225, 255, 0.15);
          transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease, opacity 180ms ease;
        }

        .synk-mic-button::before {
          content: "";
          position: absolute;
          inset: -34px;
          border-radius: inherit;
          background:
            repeating-radial-gradient(
              circle,
              rgba(0, 225, 255, 0.3) 0px,
              rgba(0, 225, 255, 0.16) 2px,
              transparent 6px,
              transparent 22px
            );
          opacity: 0.55;
          animation: micRipple 3.8s ease-in-out infinite;
          z-index: -1;
        }

        .synk-mic-button:hover {
          transform: scale(1.04);
        }

        .synk-mic-button.active {
          border-color: rgba(255, 145, 220, 0.75);
          box-shadow:
            0 0 44px rgba(255, 95, 205, 0.45),
            0 0 120px rgba(0, 225, 255, 0.38),
            inset 0 0 38px rgba(255, 95, 205, 0.16);
        }

        .synk-mic-button.muted {
          opacity: 0.55;
          border-color: rgba(180, 220, 255, 0.35);
          box-shadow:
            0 0 18px rgba(0, 225, 255, 0.18),
            inset 0 0 22px rgba(0, 225, 255, 0.08);
        }

        .synk-mic-button.muted::before {
          opacity: 0.18;
          animation-duration: 6s;
        }

        .synk-mic-icon {
          width: 44px;
          height: 44px;
        }

        .synk-status {
          min-height: 22px;
          color: #b7e8ff;
          font-size: 0.98rem;
          text-align: center;
        }
         .synk-end-voice-button {
  border: 1px solid rgba(138, 239, 255, 0.35);
  background: rgba(2, 10, 24, 0.45);
  color: #d3f2ff;
  padding: 8px 14px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.82rem;
  letter-spacing: 0.06em;
  backdrop-filter: blur(14px);
  box-shadow:
    0 0 18px rgba(0, 225, 255, 0.12),
    inset 0 0 14px rgba(0, 225, 255, 0.04);
  transition: transform 180ms ease, opacity 180ms ease;
}

.synk-end-voice-button:hover {
  transform: scale(1.04);
}
        .synk-badge {
          position: absolute;
          right: 28px;
          bottom: 24px;
          z-index: 5;
          padding: 10px 16px;
          border-radius: 999px;
          background: rgba(3, 15, 30, 0.42);
          border: 1px solid rgba(125, 211, 252, 0.2);
          color: #d3f2ff;
          font-size: 0.85rem;
          letter-spacing: 0.08em;
          backdrop-filter: blur(18px);
        }

        @keyframes ringBreathe {
          0%, 100% { transform: scale(1); opacity: 0.8; }
          50% { transform: scale(1.035); opacity: 1; }
        }

        @keyframes orbIdle {
          0%, 100% { transform: scale(1); filter: brightness(1); }
          50% { transform: scale(1.025); filter: brightness(1.12); }
        }

        @keyframes orbListening {
          0%, 100% { transform: scale(1); filter: brightness(1.05); }
          50% { transform: scale(1.06); filter: brightness(1.35); }
        }

        @keyframes orbTalking {
          0%, 100% { transform: scale(1.02); filter: brightness(1.25); }
          50% { transform: scale(1.12); filter: brightness(1.65); }
        }

        @keyframes orbThinking {
          0%, 100% { transform: rotate(0deg) scale(1.02); filter: hue-rotate(0deg); }
          50% { transform: rotate(1deg) scale(1.06); filter: hue-rotate(25deg); }
        }

        @keyframes orbError {
          0%, 100% { transform: scale(1); filter: hue-rotate(120deg) brightness(1.15); }
          50% { transform: scale(1.06); filter: hue-rotate(160deg) brightness(1.35); }
        }

        @keyframes orbRipple {
          0%, 100% { transform: scale(0.92); opacity: 0.28; }
          50% { transform: scale(1.15); opacity: 0.72; }
        }

        @keyframes waveIdle {
          0%, 100% { height: 12px; opacity: 0.45; }
          50% { height: 24px; opacity: 0.85; }
        }

        @keyframes waveActive {
          0%, 100% { height: 12px; opacity: 0.5; }
          50% { height: 52px; opacity: 1; }
        }

        @keyframes micRipple {
          0%, 100% { transform: scale(0.92); opacity: 0.28; }
          50% { transform: scale(1.12); opacity: 0.7; }
        }

        @media (max-width: 900px) {
          .synk-topbar {
            left: 16px;
            right: 16px;
          }

          .synk-main {
            padding-top: 142px;
          }

          .synk-avatar-wrap {
            min-height: 220px;
            height: 32vh;
          }

          .synk-mic-button {
            width: 100px;
            height: 100px;
          }

          .synk-input-row {
            border-radius: 24px;
          }

          .synk-send-button {
            min-width: 76px;
          }
        }
      `}</style>

      <SynkWaterBackground />

      <header className="synk-topbar">
        <div className="synk-logo">
          <h1>SYNK</h1>
        </div>

        <select
          className="synk-language-select"
          value={language}
          onChange={handleLanguageChange}
          disabled={isConnected || isConnecting}
          title={
            isConnected
              ? "Stop realtime voice before changing language"
              : "Choose language"
          }
        >
          {Object.keys(LANGUAGES).map((lang) => (
            <option key={lang} value={lang}>
              {LANGUAGES[lang].label}
            </option>
          ))}
        </select>
      </header>

      <main className="synk-main">
        <div className="synk-stage">
          <div className="synk-avatar-wrap">
            <div className="synk-avatar-ring" />

            <div className="synk-avatar-core">
              <div className={`synk-orb ${orbClass}`}>
                <div className="synk-orb-word">SYNK</div>

                <div className="synk-wave">
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          </div>

          <div className="synk-chat-panel">
            {latestUserText && (
              <div className="synk-chat-row">
                <span className="synk-chat-label">You:</span>
                <span className="synk-chat-text">{latestUserText}</span>
              </div>
            )}

            <div className="synk-chat-row">
              <span className="synk-chat-label">SYNK:</span>
              <span className="synk-chat-text">
                {latestAssistantText || "Thinking..."}
              </span>
            </div>
          </div>

          <div className="synk-input-row">
            <input
              className="synk-text-input"
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder={`Ask SYNK about a game in ${language}...`}
              disabled={isSending}
            />

            <button
              className="synk-send-button"
              onClick={sendTypedMessage}
              disabled={isSending || !inputText.trim()}
            >
              {isSending ? "..." : "Send"}
            </button>
          </div>

          <div className="synk-mic-wrap">
            <button
              className={`synk-mic-button ${isConnected ? "active" : ""} ${
                isMicMuted ? "muted" : ""
              }`}
              onClick={toggleRealtime}
              aria-label={
                !isConnected
                  ? "Start realtime voice"
                  : isMicMuted
                  ? "Unmute mic"
                  : "Mute mic"
              }
              title={
                !isConnected
                  ? "Start realtime voice"
                  : isMicMuted
                  ? "Unmute mic"
                  : "Mute mic"
              }
            >
              <svg
                className="synk-mic-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 15a3 3 0 0 0 3-3V7a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
                <path d="M19 11a7 7 0 0 1-14 0" />
                <path d="M12 18v3" />
                <path d="M8 21h8" />
              </svg>
            </button>

            <div className="synk-status">{statusText}</div>
             {isConnected && (
              <button className="synk-end-voice-button" onClick={stopRealtime}>
                End Voice
              </button>
        )}
          </div>
        </div>
      </main>

      <div className="synk-badge">{badgeLabel}</div>
    </div>
  );
}