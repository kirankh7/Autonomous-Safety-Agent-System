import { ArrowLeftRight, ArrowRight } from "lucide-react";
import type { AgentMessage } from "../types";
import { AGENT_COLORS } from "./ui";

/** Inter-agent messages for one run: who told whom what, and whether it was a one-way handoff or
 *  part of a two-way request/reply. */
export default function MessageLog({ messages }: { messages: AgentMessage[] }) {
  if (!messages.length) return <p className="text-xs text-muted">No messages for this run.</p>;
  return (
    <ol className="space-y-1.5">
      {messages.map((m) => {
        const twoWay = m.protocol === "two_way";
        const Icon = twoWay ? ArrowLeftRight : ArrowRight;
        return (
          <li key={m.seq} className="grid grid-cols-[auto_1fr] gap-x-2 text-xs">
            <span className="mt-0.5 w-5 font-mono text-muted">{m.seq}</span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <Party name={m.sender} />
                <Icon size={12} className={twoWay ? "text-s1" : "text-muted"} aria-label={twoWay ? "two-way" : "one-way"} />
                <Party name={m.receiver} />
                <span className="rounded border border-hairline px-1.5 py-px font-mono text-[10px] text-ink-2">{m.kind}</span>
                <span className={`text-[10px] uppercase tracking-wide ${twoWay ? "text-s1" : "text-muted"}`}>
                  {twoWay ? "two-way" : "one-way"}
                </span>
              </div>
              <p className="mt-0.5 break-words text-ink-2">{m.content}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Party({ name }: { name: string }) {
  const color = AGENT_COLORS[name];
  return (
    <span className="inline-flex items-center gap-1 font-medium text-ink">
      <span className="h-2 w-2 rounded-full" style={{ background: color ?? "#898781" }} />
      {name.replace(" Agent", "")}
    </span>
  );
}
