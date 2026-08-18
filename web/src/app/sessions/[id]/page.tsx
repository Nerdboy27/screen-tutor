import { api, type SessionDetail } from "@/lib/api";
import { SessionView } from "@/components/SessionView";

export const dynamic = "force-dynamic";

export default async function SessionPage({
  params,
}: {
  params: { id: string };
}) {
  let session: SessionDetail | null = null;
  let error: string | null = null;
  try {
    session = await api.getSession(params.id);
  } catch (cause) {
    error = cause instanceof Error ? cause.message : String(cause);
  }

  if (!session) {
    return <p className="error">Could not load this session. ({error})</p>;
  }

  return <SessionView initial={session} />;
}
