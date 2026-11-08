import { useEffect, useState } from "react";
import type { AgentInfo, AgentMessage, Run } from "../types";
import { api } from "../api";
import MessageLog from "../components/MessageLog";
import CoordinationGraph from "../components/CoordinationGraph";
import TraceTimeline, { AgentTag, Pipeline } from "../components/TraceTimeline";
import { SignalStrip } from "../components/Signals";
import { Panel, StatusBadge, decisionStatus } from "../components/ui";

/** Shows each processed report as a pass through the agent pipeline, step by step. */
export default function AgentActivity({ runs, names, agents }: {
  runs: Run[]; names: Record<string, string>; agents: AgentInfo[];
}) {
  const [runId, setRunId] = useState<string | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [details, setDetails] = useState(false);

  useEffect(() => {
    if (!runs.find((r) => r.run_id === runId)) setRunId(runs.at(-1)?.run_id ?? null);
  }, [runs, runId]);
  const current = runs.find((r) => r.run_id === runId);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  useEffect(() => {
    if (!runId) return;
    let live = true;
    api.messages(runId).then((m) => { if (live) setMessages(m); }).catch(() => live && setMessages([]));
    return () => { live = false; };
  }, [runId, runs.length]);

  const roster = (
    <>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {agents.map((a) => (
          <div key={a.name} className="rounded-xl border border-hairline bg-surface p-3">
            <AgentTag agent={a.name} />
            <p className="mt-1.5 text-xs text-ink-2">{a.role}</p>
          </div>
        ))}
      </div>
      <Panel title="How the agents coordinate">
        <CoordinationGraph />
      </Panel>
    </>
  );

  if (!runs.length) {
    return <div className="space-y-4">{roster}<Panel><p className="py-10 text-center text-sm text-muted">No agent runs yet. Start a scenario and press Next Step.</p></Panel></div>;
  }

  return (
    <div className="space-y-4">
    {roster}
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <Panel title="Agent runs (one per report)">
        <ul className="space-y-1">
          {runs.map((r) => {
            const verify = r.steps.findLast((s) => s.stage === "verify");
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
                    <span className="text-ink-2">{who ? names[who] ?? who : ""}</span>
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
            <Pipeline steps={current.steps} selected={stage} onSelect={setStage} />
            <div className="mt-3"><SignalStrip steps={current.steps} /></div>
          </Panel>
          <Panel title="Agent messages"
                 action={<span className="text-xs text-muted">one-way handoffs · two-way request/reply</span>}>
            <MessageLog messages={messages} />
          </Panel>
          <Panel title="ReAct trace"
                 action={<button onClick={() => setDetails(!details)} className="text-xs text-s1 hover:underline">
                   {details ? "Hide reasoning" : "Show reasoning for all steps"}</button>}>
            <TraceTimeline steps={current.steps} stageFilter={stage} expandAll={details} />
          </Panel>
        </div>
      )}
    </div>
    </div>
  );
}
