import type { CandidateWithContext, DecisionRequest, DecisionResponse } from "../../shared/types.ts";

export async function fetchCandidates(): Promise<CandidateWithContext[]> {
  const res = await fetch("/api/candidates");
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `GET /api/candidates failed (${res.status})`);
  }
  return res.json();
}

export async function sendDecision(req: DecisionRequest): Promise<CandidateWithContext> {
  const res = await fetch("/api/decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  const body = (await res.json()) as DecisionResponse | { error: string };
  if (!res.ok || !("ok" in body)) {
    throw new Error("error" in body ? body.error : `POST /api/decision failed (${res.status})`);
  }
  return body.candidate;
}
