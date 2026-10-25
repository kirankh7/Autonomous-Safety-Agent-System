import { useEffect, useState } from "react";
import type { Run } from "../types";
import TraceTimeline, { Pipeline } from "../components/TraceTimeline";
import { Panel, StatusBadge, decisionStatus } from "../components/ui";

/** Shows each processed report as a pass through the agent pipeline, step by step. */
export default function AgentActivity({ runs }: { runs: Run[] }) {
  const [runId, setRunId] = useState<string | null>(null);
  const [stage, setStage] = useState<string | null>(null);

  useEffect(() => {
    if (!runs.find((r) => r.run_id === runId)) setRunId(runs.at(-1)?.run_id ?? null);
  }, [runs, runId]);
  const current = runs.find((r) => r.run_id === runId);

  if (!runs.length) {
    return <Panel><p className="py-10 text-center text-sm text-muted">No agent runs yet. Start a scenario and press Next Step.</p></Panel>;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <Panel title="Agent runs (one per report)">
        <ul className="space-y-1">
          {runs.map((r) => {
            const verify = r.steps.find((s) => s.stage === "verify");
            const decision = verify?.result.match(/-> (verified alert|caution advisory|wait|resolve hazard)/)?.[1];
            const key = decision?.startsWith("verified") ? "verified" : decision?.startsWith("caution") ? "caution"
              : decision?.startsWith("wait") ? "wait" : decision?.startsWith("resolve") ? "resolved" : undefined;
            const who = r.steps[0]?.thought.match(/\((CAR-\d+)\)/)?.[1];
            return (
              <li key={r.run_id}>
                <button onClick={() => { setRunId(r.run_id); setStage(null); }}
                        className={`w-full rounded-lg border p-2 text-left text-xs ${
                          r.run_id === runId ? "border-s1 bg-s1/10" : "border-hairline hover:border-axis"}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold">{r.run_id}</span>
                    <span className="text-muted">{who}</span>
                  </div>
                  <div className="mt-1">{key ? <StatusBadge info={decisionStatus(key, key === "resolved" ? "resolved" : "active")} />
                    : <span className="text-muted">no hazard update</span>}</div>
                </button>
              </li>
            );
          })}
        </ul>
      </Panel>

      {current && (
        <div className="space-y-4">
          <Panel title={`Workflow for ${current.run_id}`}>
            <p className="mb-3 text-xs text-ink-2">
              Each report passes through the LangGraph agents below. Click a stage to focus on it; dashed stages were skipped
              (for example, history retrieval only runs when a new hazard is opened).
            </p>
            <Pipeline steps={current.steps} selected={stage} onSelect={setStage} />
          </Panel>
          <Panel title="ReAct trace: reason, act with a tool, observe the result">
            <TraceTimeline steps={current.steps} stageFilter={stage} />
          </Panel>
        </div>
      )}
    </div>
  );
}
