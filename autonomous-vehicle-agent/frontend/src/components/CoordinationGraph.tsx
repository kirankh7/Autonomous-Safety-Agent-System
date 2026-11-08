import { AGENT_COLORS } from "./ui";

/** The coordination graph the backend compiles (GET /api/graph has the Mermaid version):
 *  solid = always taken, dashed = conditional edge, double-headed = two-way request/reply. */
type Node = { id: string; x: number; y: number; w: number; label: string; sub?: string; agent?: string };

const NODES: Node[] = [
  { id: "report", x: 10, y: 80, w: 110, label: "Vehicle report" },
  { id: "analysis", x: 170, y: 80, w: 140, label: "1 · Hazard Analysis", agent: "Hazard Analysis Agent" },
  { id: "verify", x: 390, y: 80, w: 130, label: "2 · Verification", agent: "Verification Agent" },
  { id: "alert", x: 600, y: 80, w: 100, label: "3 · Alert", agent: "Alert Agent" },
  { id: "memory", x: 780, y: 80, w: 130, label: "4 · Memory update", agent: "Research & Memory Agent" },
  { id: "retrieve", x: 390, y: 195, w: 130, label: "4 · History (RAG)", agent: "Research & Memory Agent" },
  { id: "fleet", x: 600, y: 195, w: 100, label: "Vehicles", sub: "alerts · look requests" },
  { id: "operator", x: 780, y: 195, w: 130, label: "Fleet operator", sub: "escalation" },
];
const H = 38;
const at = (id: string) => NODES.find((n) => n.id === id)!;
const cx = (n: Node) => n.x + n.w / 2;
const mid = (n: Node) => n.y + H / 2;

function Edge({ d, dashed, both, label, lx, ly }: {
  d: string; dashed?: boolean; both?: boolean; label?: string; lx?: number; ly?: number;
}) {
  return (
    <g>
      <path d={d} fill="none" stroke="var(--color-ink-2)" strokeWidth={1.4}
            strokeDasharray={dashed ? "5 4" : undefined} markerEnd="url(#arrow)"
            markerStart={both ? "url(#arrow-start)" : undefined} />
      {label && <text x={lx} y={ly} fontSize={10} fill="var(--color-muted)" textAnchor="middle">{label}</text>}
    </g>
  );
}

export default function CoordinationGraph() {
  const [r, an, v, a, m, rt, f, op] = ["report", "analysis", "verify", "alert", "memory", "retrieve", "fleet", "operator"].map(at);
  const y = mid(an);
  const hop = (from: Node, to: Node, label: string) => (
    <Edge d={`M${from.x + from.w},${y} L${to.x},${y}`} label={label} lx={(from.x + from.w + to.x) / 2} ly={y - 8} />
  );
  return (
    <figure>
      <svg viewBox="0 0 920 280" className="h-auto w-full" role="img"
           aria-label="Coordination graph: report to Hazard Analysis, Verification, Alert and Memory, with a two-way history loop, escalation to the fleet operator and observation requests to vehicles">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--color-ink-2)" />
          </marker>
          <marker id="arrow-start" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M10,0 L0,5 L10,10 z" fill="var(--color-ink-2)" />
          </marker>
        </defs>

        <Edge d={`M${r.x + r.w},${y} L${an.x},${y}`} />
        {hop(an, v, "hazard event")}
        {hop(v, a, "decision")}
        {hop(a, m, "alerts sent")}
        {/* nothing to clear: straight to memory */}
        <Edge d={`M${cx(an)},${an.y} C${cx(an)},22 ${cx(m)},22 ${cx(m)},${m.y}`} dashed
              label="clear report, nothing to clear" lx={(cx(an) + cx(m)) / 2} ly={30} />
        {/* two-way history loop, new hazards only */}
        <Edge d={`M${cx(v)},${v.y + H} L${cx(v)},${rt.y}`} dashed both />
        <text x={cx(v) + 8} y={(v.y + H + rt.y) / 2 + 4} fontSize={10} fill="var(--color-muted)">history request / reply (new hazards)</text>
        {/* alerts and look requests to vehicles; escalation to the operator */}
        <Edge d={`M${cx(a)},${a.y + H} L${cx(a)},${f.y}`} both />
        <Edge d={`M${a.x + a.w},${a.y + H - 6} L${op.x},${op.y + 8}`} dashed />
        <text x={(a.x + a.w + op.x) / 2 + 6} y={(a.y + H + op.y) / 2 + 2} fontSize={10} fill="var(--color-muted)">conflict &gt; 2 min</text>
        {/* fleet loop: a vehicle's next report */}
        <Edge d={`M${cx(f)},${f.y + H} C${cx(f)},272 ${cx(r)},272 ${cx(r)},${r.y + H}`} dashed
              label="a vehicle's next report answers a look request" lx={300} ly={262} />

        {NODES.map((n) => (
          <g key={n.id}>
            <rect x={n.x} y={n.y} width={n.w} height={H} rx={8} fill="var(--color-surface-2)"
                  stroke={n.agent ? AGENT_COLORS[n.agent] : "var(--color-axis)"} strokeWidth={n.agent ? 1.8 : 1} />
            <text x={n.x + n.w / 2} y={n.y + (n.sub ? 16 : 23)} fontSize={11.5} fill="var(--color-ink)"
                  textAnchor="middle" fontWeight={600}>{n.label}</text>
            {n.sub && <text x={n.x + n.w / 2} y={n.y + 30} fontSize={9.5} fill="var(--color-muted)" textAnchor="middle">{n.sub}</text>}
          </g>
        ))}
      </svg>
      <figcaption className="mt-1 text-[11px] text-muted">
        Solid: always taken · dashed: conditional · two arrowheads: two-way request and reply.
      </figcaption>
    </figure>
  );
}
