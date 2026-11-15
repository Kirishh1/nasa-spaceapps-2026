"use client";

/** ΔB histogram, bars coloured by the class their bin falls in; threshold lines drawn dashed and labeled. */
export function ChangeHistogram({ h, threshold }: { h: { edges: number[]; counts: number[]; clipped_below: number; clipped_above: number }; threshold: number }) {
  const W = 300, H = 92, PB = 16;
  const max = Math.max(1, ...h.counts);
  const lo = h.edges[0], hi = h.edges[h.edges.length - 1];
  const x = (v: number) => ((v - lo) / (hi - lo)) * W;
  const bw = W / h.counts.length;
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Histogram of backscatter change from ${lo} to ${hi} dB`}>
        {h.counts.map((c, i) => {
          const mid = (h.edges[i] + h.edges[i + 1]) / 2;
          const fill = mid <= -threshold ? "var(--decrease)" : mid >= threshold ? "var(--increase)" : "var(--limited)";
          const bh = (c / max) * (H - PB - 4);
          return <rect key={i} x={i * bw + 0.5} y={H - PB - bh} width={bw - 1} height={bh} fill={fill} />;
        })}
        <line x1={0} x2={W} y1={H - PB} y2={H - PB} stroke="var(--rule)" />
        {[-threshold, threshold].map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={2} y2={H - PB} stroke="var(--marker)" strokeDasharray="3 2" />
            <text x={x(t) + (t < 0 ? -3 : 3)} y={10} textAnchor={t < 0 ? "end" : "start"} fill="var(--marker)" fontSize="10" fontFamily="var(--font-mono)">{t > 0 ? "+" : ""}{t} dB</text>
          </g>
        ))}
        {[-15, -10, -5, 0, 5, 10, 15].map((t) => (
          <text key={t} x={x(t)} y={H - 3} textAnchor={t === -15 ? "start" : t === 15 ? "end" : "middle"} fill="var(--ink-3)" fontSize="10" fontFamily="var(--font-mono)">{t}</text>
        ))}
      </svg>
      <figcaption className="text-[11px] text-ink-3">
        ΔB distribution of valid pixels (dB){h.clipped_below + h.clipped_above > 0 ? ` · ${(h.clipped_below + h.clipped_above).toLocaleString()} px beyond ±15 dB not shown` : ""}
      </figcaption>
    </figure>
  );
}
