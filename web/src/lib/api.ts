export type Turn = {
  id: string;
  role: "user" | "tutor";
  text: string;
  source: string;
  image_width: number | null;
  image_height: number | null;
  latency_ms: number | null;
  created_at: string;
};

export type SessionSummary = {
  id: string;
  title: string;
  client: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
};

export type SessionDetail = SessionSummary & {
  turns: Turn[];
  has_visual_context: boolean;
};

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

function headers(): HeadersInit {
  const base: Record<string, string> = { "content-type": "application/json" };
  if (API_KEY) base["x-api-key"] = API_KEY;
  return base;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...headers(), ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listSessions: () => request<SessionSummary[]>("/sessions"),
  getSession: (id: string) => request<SessionDetail>(`/sessions/${id}`),
  followUp: (id: string, prompt: string) =>
    request<{ turn: Turn }>(`/sessions/${id}/follow-up`, {
      method: "POST",
      body: JSON.stringify({ prompt, source: "web" }),
    }),
  purgeVisualContext: (id: string) =>
    request<void>(`/sessions/${id}/visual-context`, { method: "DELETE" }),
  deleteSession: (id: string) =>
    request<void>(`/sessions/${id}`, { method: "DELETE" }),
};

export function sessionSocketUrl(sessionId: string): string {
  const url = new URL(`${API_BASE_URL}/ws/sessions/${sessionId}`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  if (API_KEY) url.searchParams.set("api_key", API_KEY);
  return url.toString();
}
