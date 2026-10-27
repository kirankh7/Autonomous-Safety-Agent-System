import { useEffect, useRef, useState } from "react";
import { Bot, Send, User } from "lucide-react";
import type { ChatMessage } from "../types";
import { api } from "../api";
import AnswerView from "../components/AnswerView";
import { Panel } from "../components/ui";
import { AgentTag } from "../components/TraceTimeline";

const SUGGESTIONS = [
  "Why was an alert generated for Ford Transit?",
  "How many vehicles confirmed the hazard?",
  "Why did the confidence score increase?",
  "What similar incidents happened previously?",
  "Why was the hazard resolved?",
  "What are the current hazards?",
  "What has long-term memory learned from feedback?",
  "Past flooding incidents at underpasses in heavy rain",
];

export default function Research({ messages, setMessages, mode }: {
  messages: ChatMessage[]; setMessages: (fn: (m: ChatMessage[]) => ChatMessage[]) => void; mode: string;
}) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [messages.length]);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: question }]);
    try {
      const answer = await api.ask(question);
      setMessages((m) => [...m, { role: "assistant", text: answer.answer, answer }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid h-[calc(100vh-9rem)] gap-4 lg:grid-cols-[1fr_300px]">
      <Panel className="flex min-h-0 flex-col" title={<span className="flex items-center gap-3"><Bot size={16} /> Research Assistant <AgentTag agent="Research & Memory Agent" /></span>}
             action={<span className="rounded bg-page px-2 py-0.5 text-xs text-muted">LLM: {mode}</span>}>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.length === 0 && (
            <p className="text-sm text-ink-2">
              Ask about current hazards, verification decisions, confidence scores, alerts, historical incidents, or what the
              agent has learned. Answers use only stored event data and retrieved incidents, and cite the record IDs used.
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
              {m.role === "assistant" && <Bot size={18} className="mt-1 shrink-0 text-s1" />}
              <div className={`max-w-[85%] rounded-xl p-3 ${m.role === "user" ? "bg-s1 text-white" : "border border-hairline bg-surface-2"}`}>
                {m.answer ? <AnswerView answer={m.answer} /> : <p className="text-sm">{m.text}</p>}
              </div>
              {m.role === "user" && <User size={18} className="mt-1 shrink-0 text-ink-2" />}
            </div>
          ))}
          {busy && <p className="text-sm text-muted">Searching memory...</p>}
          <div ref={end} />
        </div>
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(input); }}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question about hazards, alerts or history..."
                 className="flex-1 rounded-lg border border-hairline bg-page px-3 py-2 text-sm outline-none focus:border-s1" />
          <button disabled={busy || !input.trim()} className="rounded-lg bg-s1 px-3 text-white disabled:opacity-40">
            <Send size={16} />
          </button>
        </form>
      </Panel>

      <Panel title="Suggested questions">
        <div className="space-y-2">
          {SUGGESTIONS.map((q) => (
            <button key={q} onClick={() => ask(q)} disabled={busy}
                    className="w-full rounded-lg border border-hairline bg-surface-2 p-2 text-left text-xs text-ink-2 hover:border-s1 hover:text-ink">
              {q}
            </button>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted">
          Tip: run a scenario first so there is event data to ask about. Questions about history work any time.
        </p>
      </Panel>
    </div>
  );
}
