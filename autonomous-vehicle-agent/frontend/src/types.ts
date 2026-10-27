export type Direction = "forward" | "reverse";

export interface Vehicle {
  id: string;
  name: string;
  model: string;
  segment: string;
  direction: Direction;
  direction_label: string;
  road: string;
  position_m: number;
  speed_kmh: number;
  sensors: string[];
  lat: number;
  lng: number;
}

export interface Road {
  id: string;
  name: string;
  points: [number, number][];
  length_m: number;
  forward_label: string;
  reverse_label: string;
}

export interface ConfidenceEntry {
  t: number;
  delta: number;
  value: number;
  reason: string;
  report_vehicle: string;
}

export interface Hazard {
  id: string;
  hazard_type: string;
  segment: string;
  direction: Direction;
  direction_label: string;
  road: string;
  position_m: number;
  status: "active" | "resolved" | "expired";
  decision: string;
  confidence: number;
  max_confidence: number;
  severity: string;
  recommended_action: string;
  weather: string;
  visibility_m: number;
  description: string;
  report_ids: string[];
  confirming_vehicles: string[];
  clear_vehicles: string[];
  confidence_history: ConfidenceEntry[];
  retrieved_incidents: { id: string; score: number | null; outcome: string; used_for: string }[];
  retrieval_delta: number;
  resolution: string | null;
  lat: number;
  lng: number;
}

export interface Alert {
  id: string;
  hazard_id: string;
  vehicle_id: string;
  level: "verified" | "caution" | "observation_request" | "all_clear";
  message: string;
  hazard_type: string;
  severity: string;
  confidence: number;
  distance_m: number | null;
  eta_s: number | null;
  t: number;
}

export interface Signal {
  label: string;
  detail: string;
  tone: "neutral" | "info" | "good" | "warning" | "serious" | "critical";
}

export interface TraceStep {
  run_id?: string;
  step: number;
  agent: string;
  stage: string;
  thought: string;
  action: string;
  tool: string;
  result: string;
  confidence: number | null;
  signal?: Signal | null;
}

export interface Run {
  run_id: string;
  steps: TraceStep[];
}

export interface Evidence {
  id: string;
  kind: string;
  summary: string;
}

export interface ResearchAnswer {
  question: string;
  agent?: string;
  answer: string;
  mode: string;
  intent: string;
  evidence: Evidence[];
  tools_used: string[];
  agent_steps?: { reason: string; tool: string; input: Record<string, unknown>; result: string }[];
  unverified_citations?: string[];
}

export interface LogEntry {
  index: number;
  type: "report" | "question";
  narration: string;
  run_id?: string;
  decision?: string | null;
  hazard_id?: string | null;
  confidence?: number | null;
  alerts?: Alert[];
  stored_incident?: { id: string; outcome: string } | null;
  trace?: TraceStep[];
  question?: string;
  answer?: ResearchAnswer;
}

export interface SimStatus {
  scenario: {
    id: string;
    title: string;
    summary: string;
    weather: string;
    visibility_m: number;
    steps: { type: string; narration: string }[];
  } | null;
  index: number;
  total: number;
  done: boolean;
  log: LogEntry[];
}

export interface Scenario {
  id: string;
  title: string;
  summary: string;
  weather: string;
  visibility_m: number;
  steps: number;
}

export interface Incident {
  id: string;
  segment: string;
  hazard_type: string;
  weather: string;
  outcome: string;
  description: string;
  lesson: string;
  source: string;
}

export interface AgentInfo {
  number: number;
  name: string;
  role: string;
}

export interface AppState {
  vehicles: Vehicle[];
  roads: Road[];
  hazards: Hazard[];
  alerts: Alert[];
  stats: {
    total_vehicles: number;
    active_hazards: number;
    verified_hazards: number;
    alerts_generated: number;
    resolved_hazards: number;
    incidents_total: number;
    incidents_learned: number;
  };
  incident_types: Record<string, number>;
  agents: AgentInfo[];
  simulation: SimStatus;
  config: { llm_provider: string; embeddings: string; rules: Record<string, number> };
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  answer?: ResearchAnswer;
}
