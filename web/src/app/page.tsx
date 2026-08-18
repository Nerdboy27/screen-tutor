import Link from "next/link";

import { api, type SessionSummary } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SessionsPage() {
  let sessions: SessionSummary[] = [];
  let error: string | null = null;
  try {
    sessions = await api.listSessions();
  } catch (cause) {
    error = cause instanceof Error ? cause.message : String(cause);
  }

  if (error) {
    return (
      <p className="error">
        Cannot reach the tutor API. Start the backend and reload. ({error})
      </p>
    );
  }

  if (sessions.length === 0) {
    return (
      <p className="empty">
        No sessions yet. Press your capture hotkey in the desktop client to start
        one.
      </p>
    );
  }

  return (
    <>
      {sessions.map((session) => (
        <Link key={session.id} href={`/sessions/${session.id}`}>
          <div className="card">
            <h3>{session.title}</h3>
            <p className="meta">
              {session.client} · updated{" "}
              {new Date(session.updated_at).toLocaleString()}
            </p>
          </div>
        </Link>
      ))}
    </>
  );
}
