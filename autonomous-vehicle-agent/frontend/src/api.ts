import type {
  AgentMessage, AppState, BenchmarkResult, Incident, PlaygroundOptions, PlaygroundReport, ResearchAnswer, Run,
  RunResult, Scenario, SimStatus, Vehicle,
} from "./types";

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
  messages: (runId?: string) => request<AgentMessage[]>(`/api/messages${runId ? `?run_id=${runId}` : ""}`),
  benchmark: () => request<BenchmarkResult>("/api/benchmark", "POST"),
  playgroundOptions: () => request<PlaygroundOptions>("/api/playground/options"),
  sendReport: (report: PlaygroundReport) => request<RunResult>("/api/playground/report", "POST", report),
  randomReports: (count: number, seed?: number) =>
    request<RunResult[]>(`/api/playground/random?count=${count}${seed != null ? `&seed=${seed}` : ""}`, "POST"),
  resetPlayground: () => request<{ ok: boolean }>("/api/playground/reset", "POST"),
  moveVehicle: (id: string, move: { segment: string; direction: string; position_m: number }) =>
    request<Vehicle>(`/api/vehicles/${id}/move`, "POST", move),
  ask: (question: string) => request<ResearchAnswer>("/api/research", "POST", { question }),
};
