import { useCallback, useEffect, useState } from "react";
import { Activity, Bot, ExternalLink, FlaskConical, Gamepad2, LayoutDashboard, Map, ShieldAlert } from "lucide-react";
import type { AppState, ChatMessage, Run, Scenario } from "./types";
import { api } from "./api";
import Dashboard from "./pages/Dashboard";
import MapPage from "./pages/MapPage";
import Simulation from "./pages/Simulation";
import AgentActivity from "./pages/AgentActivity";
import Research from "./pages/Research";
import Playground from "./pages/Playground";

const PAGES = [
  { key: "dashboard", label: "Fleet Dashboard", Icon: LayoutDashboard },
  { key: "map", label: "Vehicle Map", Icon: Map },
  { key: "simulation", label: "Hazard Simulation", Icon: FlaskConical },
  { key: "playground", label: "Playground", Icon: Gamepad2 },
  { key: "activity", label: "Agent Activity", Icon: Activity },
  { key: "research", label: "Research Assistant", Icon: Bot },
];

export default function App() {
  // The page lives in the URL hash (e.g. #map) so it survives a reload during a demo.
  const [page, setPageState] = useState(() => location.hash.slice(1) || "simulation");
  const setPage = (key: string) => { location.hash = key; setPageState(key); };
  const [state, setState] = useState<AppState | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.state(), api.trace()]);
      setState(s);
      setRuns(r);
      setError(null);
    } catch (e) {
      setError(`Cannot reach the backend (${(e as Error).message}). Is uvicorn running on port 8000?`);
    }
  }, []);

  useEffect(() => {
    refresh();
    api.scenarios().then(setScenarios).catch(() => {});
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [refresh]);

  // Run a backend action, then refresh everything the dashboard shows.
  const run = useCallback(async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      await refresh();
      setBusy(false);
    }
  }, [refresh]);

  return (
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col border-r border-hairline bg-surface">
        <div className="flex items-center gap-2 border-b border-hairline p-4">
          <ShieldAlert className="text-s1" size={22} />
          <div>
            <div className="text-sm font-semibold leading-tight">AV Safety Agent</div>
            <div className="text-[11px] text-muted">Fleet monitoring center</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {PAGES.map(({ key, label, Icon }) => (
            <button key={key} onClick={() => setPage(key)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                      page === key ? "bg-s1/15 text-ink" : "text-ink-2 hover:bg-surface-2"}`}>
              <Icon size={16} className={page === key ? "text-s1" : ""} />
              {label}
            </button>
          ))}
        </nav>
        <div className="space-y-1 border-t border-hairline p-4 text-[11px] text-muted">
          <div>Simulated data only. Alerts are advisory and never control vehicles.</div>
          {state && <div>LLM: {state.config.llm_provider}<br />Vector DB: {state.config.vector_db}</div>}
          <div>CMU Agentic AI capstone - Kiran Haridas</div>
          <a href="https://github.com/kirankh7/Autonomous-Safety-Agent-System" target="_blank" rel="noreferrer"
             className="inline-flex items-center gap-1 text-s1 hover:underline">
            Source code on GitHub <ExternalLink size={11} />
          </a>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-hairline px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold">{PAGES.find((p) => p.key === page)?.label}</h1>
            <p className="text-xs text-muted">Autonomous Vehicle Intercommunication Safety Agent System</p>
          </div>
          {state && (
            <div className="flex items-center gap-4 text-xs text-ink-2">
              <span><b className="text-ink">{state.stats.active_hazards}</b> active hazards</span>
              <span><b className="text-ink">{state.stats.alerts_generated}</b> alerts</span>
              <span><b className="text-ink">{state.stats.incidents_total}</b> incidents in memory</span>
            </div>
          )}
        </header>
        {error && <div className="mx-6 mt-3 rounded-lg border border-critical/50 bg-critical/10 p-2 text-sm">{error}</div>}
        <div className="flex-1 overflow-y-auto p-6">
          {!state ? <p className="text-sm text-muted">Loading...</p> : (
            <>
              {page === "dashboard" && <Dashboard state={state} runs={runs} go={setPage} />}
              {page === "map" && <MapPage state={state} />}
              {page === "simulation" && <Simulation state={state} scenarios={scenarios} run={run} busy={busy} />}
              {page === "playground" && <Playground state={state} run={run} busy={busy} />}
              {page === "activity" && <AgentActivity runs={runs} agents={state.agents} names={Object.fromEntries(state.vehicles.map((v) => [v.id, v.name]))} />}
              {page === "research" && <Research messages={messages} setMessages={setMessages} mode={state.config.llm_provider} />}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
