"use client";

import { useEffect, useRef, useState } from "react";

import {
  api,
  sessionSocketUrl,
  type SessionDetail,
  type Turn,
} from "@/lib/api";

export function SessionView({ initial }: { initial: SessionDetail }) {
  const [turns, setTurns] = useState<Turn[]>(initial.turns);
  const [prompt, setPrompt] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasContext, setHasContext] = useState(initial.has_visual_context);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const socket = new WebSocket(sessionSocketUrl(initial.id));
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: string; turn?: Turn };
      if (payload.type === "turn" && payload.turn) {
        const turn = payload.turn;
        setTurns((current) =>
          current.some((existing) => existing.id === turn.id)
            ? current
            : [...current, turn],
        );
      }
    };
    return () => socket.close();
  }, [initial.id]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length]);

  async function send() {
    const text = prompt.trim();
    if (!text || pending) return;
    setPending(true);
    setError(null);
    const optimistic: Turn = {
      id: `local-${Date.now()}`,
      role: "user",
      text,
      source: "web",
      image_width: null,
      image_height: null,
      latency_ms: null,
      created_at: new Date().toISOString(),
    };
    setTurns((current) => [...current, optimistic]);
    setPrompt("");
    try {
      await api.followUp(initial.id, text);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setPending(false);
    }
  }

  async function purge() {
    await api.purgeVisualContext(initial.id);
    setHasContext(false);
  }

  return (
    <>
      <div className="card">
        <h3>{initial.title}</h3>
        <p className="meta">
          {initial.client} · started {new Date(initial.created_at).toLocaleString()}{" "}
          · visual context {hasContext ? "active in server memory" : "purged"}
        </p>
        {hasContext && (
          <button className="ghost" onClick={purge}>
            Purge visual context
          </button>
        )}
      </div>

      <div className="card">
        {turns.map((turn) => (
          <div key={turn.id} className={`turn ${turn.role}`}>
            <div className="role">
              {turn.role}
              {turn.image_width
                ? ` · capture ${turn.image_width}×${turn.image_height}`
                : ""}
              {turn.latency_ms ? ` · ${turn.latency_ms} ms` : ""}
            </div>
            {turn.text}
          </div>
        ))}
        <div ref={bottom} />

        <div className="composer">
          <input
            type="text"
            value={prompt}
            placeholder="Ask a follow-up about the captured screen…"
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void send();
            }}
          />
          <button onClick={() => void send()} disabled={pending}>
            {pending ? "Thinking…" : "Send"}
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </div>
    </>
  );
}
