"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type TimelinePoint } from "@/services/api";

// Categorical palette validated with the dataviz validator against the #161819 surface (dark): all checks pass.
const SERIES = {
  NISAR: { color: "#c98500", label: "NISAR L-band (every processed pass)" },
  DSWX_S1: { color: "#3987e5", label: "OPERA DSWx-S1 (C-band radar)" },
  DSWX_HLS: { color: "#d55181", label: "OPERA DSWx-HLS (optical, ≥50% clear)" },
} as const;
type Key = keyof typeof SERIES;

interface Pt { key: Key; date: string; value: number; note: string }

const W = 320, PL = 34, PR = 8;

function Marker({ k, x, y, active }: { k: Key; x: number; y: number; active: boolean }) {
  const c = SERIES[k].color;
  const r = active ? 5.5 : 4;
  if (k === "NISAR") return <path d={`M${x} ${y - r - 1}L${x + r + 1} ${y}L${x} ${y + r + 1}L${x - r - 1} ${y}Z`} fill={c} stroke="#161819" strokeWidth="2" />;
  if (k === "DSWX_HLS") return <rect x={x - r + 1} y={y - r + 1} width={(r - 1) * 2} height={(r - 1) * 2} fill="#161819" stroke={c} strokeWidth="2" />;
  return <circle cx={x} cy={y} r={r} fill={c} stroke="#161819" strokeWidth="2" />;
}

const fmt = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

/** A small single-measure panel sharing the season's x-scale (one y-axis per chart, never two). */
function Panel({ title, unit, height, points, x, yMin, yMax, kind, analysed, ticks }: {
  title: string; unit: string; height: number; points: { date: string; value: number; label?: string }[];
  x: (d: string) => number; yMin: number; yMax: number; kind: "bars" | "dots"; analysed: string[]; ticks: number[];
}) {
  const [hover, setHover] = useState<number | null>(null);
  const PB = 4, PT = 6;
  const y = (v: number) => PT + (1 - (v - yMin) / (yMax - yMin || 1)) * (height - PT - PB);
  const h = hover !== null ? points[hover] : null;
  return (
    <div className="relative mt-3">
      <p className="mb-0.5 text-[11px] text-ink-2">{title}</p>
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" role="img" aria-label={title} onMouseLeave={() => setHover(null)}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PL} x2={W - PR} y1={y(v)} y2={y(v)} stroke="var(--rule-soft)" />
            <text x={PL - 4} y={y(v) + 3} textAnchor="end" fontSize="9" fill="var(--ink-3)" fontFamily="var(--font-mono)">{v}</text>
          </g>
        ))}
        {analysed.map((d) => <line key={d} x1={x(d)} x2={x(d)} y1={PT} y2={height - PB} stroke={SERIES.NISAR.color} strokeDasharray="3 3" strokeOpacity="0.6" />)}
        {kind === "bars"
          ? points.map((p, i) => {
              const top = y(Math.max(p.value, yMin));
              return <rect key={p.date} x={x(p.date) - 0.9} y={top} width={1.8} height={Math.max(0, y(yMin) - top)} fill={hover === i ? "var(--ink)" : "var(--ink-2)"} onMouseEnter={() => setHover(i)} />;
            })
          : points.map((p, i) => (
              <g key={`${p.date}${i}`}>
                <circle cx={x(p.date)} cy={y(p.value)} r={hover === i ? 4.5 : 3} fill="var(--ink-2)" stroke="#161819" strokeWidth="1.5" />
                <circle cx={x(p.date)} cy={y(p.value)} r="8" fill="transparent" onMouseEnter={() => setHover(i)} />
              </g>
            ))}
      </svg>
      <span className="absolute top-0 right-0 text-[10px] text-ink-3">{unit}</span>
      {h && (
        <div className="pointer-events-none absolute top-4 right-0 z-10 rounded-[3px] border border-rule bg-housing-1 px-2 py-1 text-[11px] text-ink">
          {fmt(h.date)} · <span className="num">{h.value.toFixed(unit === "m³/m³" ? 2 : 1)} {unit}</span>{h.label ? <span className="text-ink-3"> · {h.label}</span> : null}
        </div>
      )}
    </div>
  );
}

/** Season context: water extent from three sensors, with rainfall, lake level and soil moisture underneath. */
export function WaterTimeline({ areaId, nisar }: { areaId: string; nisar: { date: string; fraction: number }[] }) {
  const [series, setSeries] = useState<TimelinePoint[] | null>(null);
  const [season, setSeason] = useState<{ date: string; water_fraction: number; water_km2: number }[]>([]);
  const [rain, setRain] = useState<{ date: string; mean_mm: number }[]>([]);
  const [swot, setSwot] = useState<{ pass: string; series: { date: string; lakes: number; median_wse_change_m: number | null }[] }[]>([]);
  const [soil, setSoil] = useState<{ date: string; mean_m3m3: number | null }[]>([]);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    api.timeline(areaId).then((t) => setSeries(t.series)).catch(() => setSeries([]));
    api.nisarSeason(areaId).then((t) => setSeason(t.series)).catch(() => setSeason([]));
    api.rainfall(areaId).then((r) => setRain(r.series)).catch(() => setRain([]));
    api.swotLevels(areaId).then((r) => setSwot(r.passes)).catch(() => setSwot([]));
    api.soilMoisture(areaId).then((r) => setSoil(r.series)).catch(() => setSoil([]));
  }, [areaId]);

  const pts = useMemo<Pt[]>(() => {
    const out: Pt[] = [];
    for (const s of series ?? []) {
      if (s.open_water_fraction === null) continue;
      if (s.product === "DSWX_HLS" && s.observed_fraction < 0.5) continue;
      out.push({ key: s.product, date: s.date, value: s.open_water_fraction, note: `${Math.round(s.observed_fraction * 100)}% of basin observed` });
    }
    const nis = season.length ? season.map((s) => ({ date: s.date, fraction: s.water_fraction, km2: s.water_km2 })) : nisar.map((n) => ({ ...n, km2: undefined }));
    for (const n of nis) out.push({ key: "NISAR", date: n.date, value: n.fraction, note: n.km2 ? `${n.km2} km² open water` : "open water" });
    return out.sort((a, b) => a.date.localeCompare(b.date));
  }, [series, season, nisar]);

  if (series === null) return null;
  if (!pts.length) return <p className="text-[12px] text-ink-3">No surface-water timeline has been computed for this area.</p>;

  const t = (d: string) => Date.parse(`${d}T00:00:00Z`);
  const t0 = Math.min(...pts.map((p) => t(p.date))), t1 = Math.max(...pts.map((p) => t(p.date)));
  const x = (d: string) => PL + ((t(d) - t0) / Math.max(1, t1 - t0)) * (W - PL - PR);
  const H = 150, PT = 10, PB = 22;
  const y = (v: number) => PT + (1 - v) * (H - PT - PB);
  const months = Array.from(new Set(pts.map((p) => p.date.slice(0, 7)))).map((m) => `${m}-01`).filter((d) => t(d) >= t0);
  const h = hover !== null ? pts[hover] : null;
  const analysed = nisar.map((n) => n.date);
  const inRange = (d: string) => t(d) >= t0 && t(d) <= t1;
  const swotPts = swot.flatMap((p) => p.series.filter((s) => s.median_wse_change_m !== null && inRange(s.date)).map((s) => ({ date: s.date, value: s.median_wse_change_m as number, label: `pass ${p.pass}, ${s.lakes} lakes` })));
  const soilPts = soil.filter((s) => s.mean_m3m3 !== null && inRange(s.date)).map((s) => ({ date: s.date, value: s.mean_m3m3 as number }));
  const rainPts = rain.filter((r) => inRange(r.date)).map((r) => ({ date: r.date, value: r.mean_mm }));
  const maxRain = Math.max(10, ...rainPts.map((r) => r.value));

  return (
    <figure>
      <p className="mb-1 text-[11px] text-ink-2">Share of the basin that is open water</p>
      <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1" aria-label="Legend">
        {(Object.keys(SERIES) as Key[]).map((k) => (
          <span key={k} className="flex items-center gap-1.5 text-[11px] text-ink-2">
            <svg width="12" height="12" aria-hidden><Marker k={k} x={6} y={6} active={false} /></svg>
            {SERIES[k].label}
          </span>
        ))}
      </div>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Open-water fraction of the basin over the 2026 season from NISAR and NASA OPERA" onMouseLeave={() => setHover(null)}>
          {[0, 0.25, 0.5, 0.75, 1].map((v) => (
            <g key={v}>
              <line x1={PL} x2={W - PR} y1={y(v)} y2={y(v)} stroke="var(--rule-soft)" />
              <text x={PL - 4} y={y(v) + 3} textAnchor="end" fontSize="9" fill="var(--ink-3)" fontFamily="var(--font-mono)">{v * 100}%</text>
            </g>
          ))}
          {months.map((d) => (
            <text key={d} x={x(d)} y={H - 6} textAnchor="middle" fontSize="9" fill="var(--ink-3)" fontFamily="var(--font-mono)">
              {new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" })}
            </text>
          ))}
          {analysed.map((d) => <line key={d} x1={x(d)} x2={x(d)} y1={PT} y2={H - PB} stroke={SERIES.NISAR.color} strokeDasharray="3 3" strokeOpacity="0.6" />)}
          {pts.map((p, i) => (
            <g key={`${p.key}${p.date}`}>
              <Marker k={p.key} x={x(p.date)} y={y(p.value)} active={hover === i} />
              <circle cx={x(p.date)} cy={y(p.value)} r="9" fill="transparent" onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={0} aria-label={`${SERIES[p.key].label}, ${fmt(p.date)}: ${Math.round(p.value * 100)}% open water`} />
            </g>
          ))}
        </svg>
        {h && (
          <div className="pointer-events-none absolute z-10 rounded-[3px] border border-rule bg-housing-1 px-2 py-1.5 text-[11px] shadow-[0_6px_16px_rgba(0,0,0,0.5)]"
            style={{ left: `${(x(h.date) / W) * 100}%`, top: `${(y(h.value) / H) * 100}%`, transform: `translate(${x(h.date) > W / 2 ? "-105%" : "8%"}, -110%)` }}>
            <p className="text-ink">{fmt(h.date)} · <span className="num">{Math.round(h.value * 100)}%</span> open water</p>
            <p className="text-ink-3">{SERIES[h.key].label}</p>
            <p className="text-ink-3">{h.note}</p>
          </div>
        )}
      </div>

      {rainPts.length > 0 && <Panel title="Daily rainfall, basin mean (NASA GPM IMERG)" unit="mm/day" height={60} points={rainPts} x={x} yMin={0} yMax={maxRain} kind="bars" analysed={analysed} ticks={[0, Math.round(maxRain)]} />}
      {swotPts.length > 0 && <Panel title="Lake water level vs early June, median per SWOT pass (NASA/CNES SWOT)" unit="m" height={60} points={swotPts} x={x} yMin={-1.6} yMax={0.8} kind="dots" analysed={analysed} ticks={[-1.5, 0, 0.5]} />}
      {soilPts.length > 0 && <Panel title="Soil moisture, basin mean where not flooded (NASA SMAP)" unit="m³/m³" height={56} points={soilPts} x={x} yMin={0.1} yMax={0.55} kind="dots" analysed={analysed} ticks={[0.2, 0.4]} />}

      <figcaption className="mt-2 text-[11px] leading-snug text-ink-3">
        Dashed lines mark the two NISAR passes in this analysis. The C-band series jumps between Sentinel-1 orbits; optical points appear only on mostly clear days.
        SMAP does not retrieve soil moisture over flooded cells.
      </figcaption>
      <details className="mt-1">
        <summary className="cursor-pointer text-[11px] text-ink-3 underline underline-offset-2">Show water series as table</summary>
        <table className="mt-1 w-full text-[11px]">
          <thead><tr className="text-ink-3"><th className="text-left font-normal">Date</th><th className="text-left font-normal">Source</th><th className="text-right font-normal">Open water</th></tr></thead>
          <tbody className="num">
            {pts.map((p) => (
              <tr key={`t${p.key}${p.date}`} className="border-t border-rule-soft">
                <td className="py-0.5 text-ink">{p.date}</td><td className="font-sans text-ink-2">{SERIES[p.key].label}</td><td className="text-right text-ink">{Math.round(p.value * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
