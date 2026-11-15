"use client";

import type { Precipitation } from "@/services/api";

export function RainfallStrip({ p, earlier, later }: { p: Precipitation | null; earlier: string; later: string }) {
  if (!p || p.status !== "available" || !p.series?.length) {
    return (
      <p className="rounded-[3px] border border-dashed border-rule px-3 py-2.5 text-[12px] leading-relaxed text-ink-2">
        <span className="mr-1.5 inline-block rounded-[2px] border border-ink-3/60 px-1 text-[10.5px] font-semibold tracking-wide text-ink-3 uppercase">Unavailable</span>
        {p?.reason ?? "Precipitation was not requested for this analysis."}
      </p>
    );
  }
  const series = p.series;
  const W = 300, H = 70, PB = 14;
  const max = Math.max(1, ...series.map((d) => d.mean_mm));
  const bw = W / series.length;
  const idx = (d: string) => series.findIndex((s) => s.date === d);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Daily area-mean precipitation from GPM IMERG">
        {series.map((d, i) => {
          const bh = (d.mean_mm / max) * (H - PB - 10);
          return <rect key={d.date} x={i * bw + 0.5} y={H - PB - bh} width={Math.max(1, bw - 1)} height={bh} fill="var(--ink-2)"><title>{`${d.date}: ${d.mean_mm} mm (${d.run})`}</title></rect>;
        })}
        {[earlier, later].map((d, k) => {
          const i = idx(d);
          if (i < 0) return null;
          const xx = i * bw + bw / 2;
          return (
            <g key={d}>
              <line x1={xx} x2={xx} y1={0} y2={H - PB} stroke={k ? "var(--marker)" : "var(--ink)"} strokeDasharray="3 2" />
              <text x={xx} y={H - 2} textAnchor="middle" fontSize="10" fill={k ? "var(--marker)" : "var(--ink)"} fontFamily="var(--font-mono)">{d.slice(5)}</text>
            </g>
          );
        })}
      </svg>
      <dl className="mt-2 text-[12px]">
        {[
          ["7 days before earlier frame", p.before_earlier_7d],
          ["7 days before later frame", p.before_later_7d],
          ["Between acquisitions", p.between_acquisitions],
        ].map(([k, w]) => {
          const ww = w as { total_mm: number | null; days_available: number } | undefined;
          return (
            <div key={k as string} className="grid grid-cols-[1fr_auto] py-[3px]">
              <dt className="text-ink-3">{k as string}</dt>
              <dd className="num text-ink">{ww?.total_mm ?? "—"} mm <span className="text-ink-3">({ww?.days_available ?? 0} d)</span></dd>
            </div>
          );
        })}
      </dl>
      <p className="mt-1.5 text-[11px] leading-snug text-ink-3">{p.source}. {p.caveat}{p.missing_days?.length ? ` Missing days: ${p.missing_days.length}.` : ""}</p>
    </div>
  );
}
