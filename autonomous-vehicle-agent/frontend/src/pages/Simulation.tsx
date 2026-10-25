import { useEffect, useState } from "react";
import { CheckCircle2, CircleDot, CloudFog, MessageSquare, Play, RotateCcw, Send, SkipForward, Trash2 } from "lucide-react";
import type { AppState, LogEntry, Scenario } from "../types";
import { api } from "../api";
import AnswerView from "../components/AnswerView";
import FleetMap from "../components/FleetMap";
import TraceTimeline from "../components/TraceTimeline";
import { Button, ConfidenceMeter, Panel, StatusBadge, alertStatus, decisionStatus, fmtType } from "../components/ui";

interface Props {
  state: AppState;
  scenarios: Scenario[];
  run: (action: () => Promise<unknown>) => Promise<void>;
  busy: boolean;
}

export default function Simulation({ state, scenarios, run, busy }: Props) {
  const sim = state.simulation;
  const [viewIndex, setViewIndex] = useState<number | null>(null);

  // Always jump to the newest step after "Next Step".
  useEffect(() => setViewIndex(sim.log.length ? sim.log.length - 1 : null), [sim.log.length]);
  const entry: LogEntry | undefined = viewIndex !== null ? sim.log[viewIndex] : undefined;
  const hazard = state.hazards.find((h) => h.id === (entry?.hazard_id ?? sim.log.findLast((l) => l.hazard_id)?.hazard_id));

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-5">
        {scenarios.map((s, i) => {
          const active = sim.scenario?.id === s.id;
          return (
            <button key={s.id} disabled={busy} onClick={() => run(() => api.startScenario(s.id))}
                    className={`rounded-xl border p-3 text-left transition ${
                      active ? "border-s1 bg-s1/10" : "border-hairline bg-surface hover:border-axis"}`}>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface-2 text-xs">{i + 1}</span>
                {s.title}
              </div>
              <p className="mt-1 line-clamp-3 text-xs text-ink-2">{s.summary}</p>
              <div className="mt-2 flex items-center gap-1 text-[11px] text-muted">
                <CloudFog size={12} /> {s.weather.replace("_", " ")}, {s.visibility_m} m visibility - {s.steps} steps
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-hairline bg-surface p-3">
        <div className="mr-auto text-sm">
          {sim.scenario
            ? <><span className="font-semibold">{sim.scenario.title}</span><span className="ml-2 text-ink-2">step {sim.index} / {sim.total}{sim.done && " - complete"}</span></>
            : <span className="text-ink-2">Choose a scenario above to begin.</span>}
        </div>
        <Button onClick={() => run(api.nextStep)} disabled={!sim.scenario || sim.done || busy}>
          <SkipForward size={16} /> Next Step
        </Button>
        <Button variant="secondary" onClick={() => run(() => api.reset(false))} disabled={!sim.scenario || busy}
                title="Restart this scenario (keeps learned long-term memory)">
          <RotateCcw size={16} /> Reset Scenario
        </Button>
        <Button variant="ghost" disabled={busy} title="Also forget incidents learned from feedback"
                onClick={() => confirm("Reset the scenario AND forget learned incidents?") && run(() => api.reset(true))}>
          <Trash2 size={16} /> Reset All Memory
        </Button>
      </div>

      {sim.scenario && (
        <div className="grid gap-4 xl:grid-cols-[320px_1fr_380px]">
          <Panel title="Scenario steps">
            <ol className="space-y-2">
              {sim.scenario.steps.map((s, i) => {
                const done = i < sim.log.length;
                const next = i === sim.log.length;
                const log = sim.log[i];
                return (
                  <li key={i}>
                    <button disabled={!done} onClick={() => setViewIndex(i)}
                            className={`flex w-full gap-2 rounded-lg border p-2 text-left text-xs transition ${
                              viewIndex === i ? "border-s1 bg-s1/10"
                                : next ? "border-dashed border-s1/60" : "border-hairline"} ${done ? "hover:border-axis" : ""}`}>
                      {done ? <CheckCircle2 size={16} className="shrink-0 text-good" />
                        : <CircleDot size={16} className={`shrink-0 ${next ? "text-s1" : "text-muted"}`} />}
                      <div className="space-y-1">
                        <div className={done || next ? "text-ink" : "text-muted"}>
                          {s.type === "question" ? <MessageSquare size={12} className="mr-1 inline" /> : <Send size={12} className="mr-1 inline" />}
                          {s.narration}
                        </div>
                        {log?.type === "report" && log.decision && (
                          <div className="flex items-center gap-2">
                            <StatusBadge info={decisionStatus(log.decision)} />
                            <span className="tabular text-ink-2">{log.confidence?.toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ol>
            {sim.done && <p className="mt-3 text-xs text-good">Scenario complete. Try another one, or open the Research Assistant.</p>}
          </Panel>

          <div className="space-y-4">
            {!entry && (
              <Panel>
                <div className="flex flex-col items-center gap-2 py-10 text-center text-sm text-ink-2">
                  <Play size={28} className="text-s1" />
                  Press <b>Next Step</b> to send the first vehicle report through the agent workflow.
                </div>
              </Panel>
            )}
            {entry?.type === "report" && (
              <>
                <Panel title={`Step ${entry.index + 1}: ${entry.run_id}`}
                       action={entry.decision && <StatusBadge info={decisionStatus(entry.decision)} />}>
                  <p className="mb-3 text-sm text-ink-2">{entry.narration}</p>
                  {entry.alerts && entry.alerts.length > 0 ? (
                    <div className="space-y-2">
                      {entry.alerts.map((a) => (
                        <div key={a.id} className="rounded-lg border border-hairline bg-surface-2 p-2 text-xs">
                          <div className="mb-1 flex items-center justify-between">
                            <StatusBadge info={alertStatus(a.level)} />
                            <span className="font-mono text-muted">{a.id} to {a.vehicle_id}</span>
                          </div>
                          <div className="text-ink">{a.message}</div>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-xs text-muted">No new alerts at this step.</p>}
                  {entry.stored_incident && (
                    <p className="mt-2 text-xs text-good">
                      Stored in long-term memory as {entry.stored_incident.id} (outcome: {entry.stored_incident.outcome.replace("_", " ")}).
                    </p>
                  )}
                </Panel>
                <Panel title="Agent trace for this step">
                  <TraceTimeline steps={entry.trace ?? []} />
                </Panel>
              </>
            )}
            {entry?.type === "question" && entry.answer && (
              <Panel title={<span className="flex items-center gap-2"><MessageSquare size={14} /> Research Assistant</span>}>
                <p className="mb-3 rounded-lg bg-surface-2 p-2 text-sm"><span className="text-muted">Q: </span>{entry.question}</p>
                <AnswerView answer={entry.answer} />
              </Panel>
            )}
          </div>

          <div className="space-y-4">
            <FleetMap roads={state.roads} vehicles={state.vehicles} hazards={state.hazards}
                      alerts={state.alerts} height="320px" />
            {hazard && (
              <Panel title={`${hazard.id}: ${fmtType(hazard.hazard_type)}`}
                     action={<StatusBadge info={decisionStatus(hazard.decision, hazard.status)} />}>
                <ConfidenceMeter value={hazard.confidence} decision={hazard.decision} status={hazard.status} />
                <div className="mt-3 grid grid-cols-2 gap-y-1 text-xs">
                  <span className="text-muted">Severity</span><span>{hazard.severity}</span>
                  <span className="text-muted">Action</span><span>{hazard.recommended_action}</span>
                  <span className="text-muted">Reports</span><span>{hazard.report_ids.length}</span>
                  <span className="text-muted">History effect</span><span className="tabular">{hazard.retrieval_delta >= 0 ? "+" : ""}{hazard.retrieval_delta.toFixed(2)}</span>
                </div>
              </Panel>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
