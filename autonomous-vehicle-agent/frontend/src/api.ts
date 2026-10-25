import type { AppState, Incident, ResearchAnswer, Run, Scenario, SimStatus } from "./types";

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  state: () => request<AppState>("/api/state"),
  scenarios: () => request<Scenario[]>("/api/scenarios"),
  startScenario: (id: string) => request<SimStatus>(`/api/scenarios/${id}/start`, "POST"),
  nextStep: () => request<SimStatus>("/api/simulation/next", "POST"),
  reset: (full = false) => request<SimStatus>(`/api/simulation/reset?full=${full}`, "POST"),
  trace: () => request<Run[]>("/api/trace"),
  incidents: () => request<Incident[]>("/api/incidents"),
  ask: (question: string) => request<ResearchAnswer>("/api/research", "POST", { question }),
};
