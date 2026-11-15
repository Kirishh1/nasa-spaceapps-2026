"use client";

import { Loader2, MapPinned, Search, SquareDashed, X } from "lucide-react";
import { useState } from "react";

import type { AnalysisConfig, Issue, Observation, Polygon, StudyArea } from "@/services/api";

export type Sensor = "NISAR" | "RCM" | "COMPARE";

interface Props {
  areas: StudyArea[];
  areaId: string | null;
  onArea: (id: string) => void;
  observations: Observation[];
  obsStatus: "idle" | "loading" | "error";
  earlierId: string | null;
  laterId: string | null;
  onEarlier: (id: string | null) => void;
  onLater: (id: string | null) => void;
  sensor: Sensor;
  onSensor: (s: Sensor) => void;
  rcmReason: string | null;
  config: AnalysisConfig;
  onConfig: (c: AnalysisConfig) => void;
  check: { ok: boolean; errors: Issue[]; warnings: Issue[] } | null;
  checking: boolean;
  running: boolean;
  stage: string | null;
  runErrors: Issue[];
  onRun: () => void;
  drawing: boolean;
  onDrawing: (d: boolean) => void;
  drawn: Polygon | null;
  onClearDrawn: () => void;
  onFlyTo: (bbox: [number, number, number, number]) => void;
}

function Step({ n, title, state, children }: { n: number; title: string; state: "done" | "next" | "waiting"; children: React.ReactNode }) {
  return (
    <section className="relative pl-7" aria-label={title}>
      <div
        className={`absolute top-[3px] left-0 flex h-[18px] w-[18px] items-center justify-center rounded-full text-[10px] font-bold num ${
          state === "done" ? "bg-marker text-marker-ink" : state === "next" ? "border-[1.5px] border-marker text-marker" : "border border-dashed border-ink-3 text-ink-3"
        }`}
        aria-hidden
      >
        {n}
      </div>
      <h2 className={`mb-2.5 text-[13px] font-semibold [font-stretch:108%] ${state === "waiting" ? "text-ink-3" : "text-ink"}`}>{title}</h2>
      {children}
    </section>
  );
}

function obsBlocker(o: Observation, other: Observation | null, side: "earlier" | "later", pol: string, freq: string): string | null {
  if (!(o.polarizations?.[freq] ?? []).includes(pol)) return `No ${pol} in frequency ${freq}`;
  if (!o.ingested_layers.includes(`${freq}_${pol}${pol}`)) return "Listed in CMR · not downloaded";
  if (!other) return null;
  if (o.id === other.id) return "Same acquisition";
  if (side === "later" && o.start_time <= other.start_time) return "Not after earlier frame";
  if (side === "earlier" && o.start_time >= other.start_time) return "Not before later frame";
  if (o.track !== other.track || o.pass_direction !== other.pass_direction) return `Track ${o.track} ${o.pass_direction?.[0]} ≠ ${other.track} ${other.pass_direction?.[0]}`;
  return null;
}

function FrameList({ label, side, observations, selected, other, onSelect, pol, freq }: {
  label: string; side: "earlier" | "later"; observations: Observation[]; selected: string | null; other: Observation | null;
  onSelect: (id: string | null) => void; pol: string; freq: string;
}) {
  return (
    <fieldset className="mb-3">
      <legend className="label mb-1.5">{label}</legend>
      <ul className="flex flex-col gap-1" role="radiogroup" aria-label={label}>
        {observations.map((o) => {
          const blocker = obsBlocker(o, other, side, pol, freq);
          const isSel = selected === o.id;
          return (
            <li key={o.id}>
              <button
                type="button"
                role="radio"
                aria-checked={isSel}
                disabled={!!blocker && !isSel}
                onClick={() => onSelect(isSel ? null : o.id)}
                title={o.id}
                className={`group relative grid w-full grid-cols-[auto_1fr] items-center gap-x-3 rounded-[3px] border px-2.5 py-1.5 text-left transition-colors ${
                  isSel
                    ? "border-marker bg-marker/10"
                    : blocker
                      ? "cursor-not-allowed border-dashed border-rule-soft"
                      : "border-rule hover:border-ink-3 hover:bg-housing-2"
                }`}
              >
                <span className={`num text-[13px] ${blocker && !isSel ? "text-ink-3 line-through decoration-ink-3/60" : isSel ? "text-marker" : "text-ink"}`}>{o.date}</span>
                <span className="strip truncate text-[10px]">
                  T{String(o.track).padStart(3, "0")} {o.pass_direction?.[0]} · F{String(o.frame).padStart(3, "0")} · {(o.polarizations?.[freq] ?? []).join("+")}
                </span>
                {blocker && !isSel && (
                  <span className="col-span-2 mt-0.5 text-[11px] text-ink-3">
                    <span className="mr-1.5 inline-block rounded-[2px] border border-ink-3/60 px-1 text-[10.5px] font-semibold tracking-wide uppercase">Unusable</span>
                    {blocker}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}

function Slider({ label, value, min, max, step, unit, onChange, hint }: { label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void; hint: string }) {
  const id = `s-${label.replace(/\W+/g, "-")}`;
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-baseline justify-between">
        <label htmlFor={id} className="label">{label}</label>
        <span className="num text-[12px] text-ink">{value}{unit}</span>
      </div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full" />
      <p className="mt-0.5 text-[11px] leading-snug text-ink-3">{hint}</p>
    </div>
  );
}

export function ToolTray(p: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ name: string; bbox: [number, number, number, number] }[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchErr, setSearchErr] = useState<string | null>(null);
  const earlier = p.observations.find((o) => o.id === p.earlierId) ?? null;
  const later = p.observations.find((o) => o.id === p.laterId) ?? null;
  const pol = p.config.polarization;
  const freq = p.config.frequency;
  const usable = p.observations.filter((o) => o.ingested_layers.length > 0).length;

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setSearching(true);
    setSearchErr(null);
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(q)}`);
      const j: { display_name: string; boundingbox: [string, string, string, string] }[] = await r.json();
      setResults(j.map((x) => ({ name: x.display_name, bbox: [Number(x.boundingbox[2]), Number(x.boundingbox[0]), Number(x.boundingbox[3]), Number(x.boundingbox[1])] })));
      if (!j.length) setSearchErr("No places found.");
    } catch {
      setSearchErr("Place search is unavailable (offline?).");
    } finally {
      setSearching(false);
    }
  }

  const areaDone = !!p.areaId;
  const framesDone = !!(p.earlierId && p.laterId);
  const canRun = framesDone && p.sensor === "NISAR" && (p.check?.ok ?? false) && !p.running && !p.checking;

  return (
    <div className="flex flex-col gap-6">
      <Step n={1} title="Study area" state={areaDone ? "done" : "next"}>
        <label htmlFor="area" className="label mb-1 block">Demonstration area with processed data</label>
        <select
          id="area"
          value={p.areaId ?? ""}
          onChange={(e) => p.onArea(e.target.value)}
          className="w-full rounded-[3px] border border-rule bg-housing-2 px-2.5 py-2 text-[13px] text-ink"
        >
          {!p.areas.length && <option value="">No study areas registered</option>}
          {p.areas.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        <form onSubmit={search} className="mt-2.5 flex gap-1.5" role="search">
          <label htmlFor="place" className="sr-only">Search for a place</label>
          <input
            id="place"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Find a place on the map"
            className="min-w-0 flex-1 rounded-[3px] border border-rule bg-housing-2 px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-3"
          />
          <button type="submit" aria-label="Search place" className="rounded-[3px] border border-rule px-2 text-ink-2 hover:border-ink-3 hover:text-ink">
            {searching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
          </button>
        </form>
        {searchErr && <p className="mt-1 text-[11px] text-ink-3">{searchErr}</p>}
        {results.length > 0 && (
          <ul className="mt-1.5 max-h-32 overflow-auto rounded-[3px] border border-rule-soft">
            {results.map((r) => (
              <li key={r.name}>
                <button type="button" onClick={() => { p.onFlyTo(r.bbox); setResults([]); }} className="flex w-full gap-2 px-2.5 py-1.5 text-left text-[12px] text-ink-2 hover:bg-housing-2 hover:text-ink">
                  <MapPinned size={13} className="mt-0.5 shrink-0" />
                  <span className="line-clamp-2">{r.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-1.5 text-[11px] leading-snug text-ink-3">Searching moves the map only. Analysis runs where NISAR frames have been downloaded and processed.</p>
        <div className="mt-2.5 flex items-center gap-2">
          <button
            type="button"
            onClick={() => p.onDrawing(!p.drawing)}
            aria-pressed={p.drawing}
            className={`flex items-center gap-1.5 rounded-[3px] border px-2.5 py-1.5 text-[12px] ${p.drawing ? "border-marker bg-marker text-marker-ink" : "border-rule text-ink-2 hover:border-ink-3 hover:text-ink"}`}
          >
            <SquareDashed size={14} />
            {p.drawing ? "Drag on the map…" : "Draw sub-area"}
          </button>
          {p.drawn && (
            <button type="button" onClick={p.onClearDrawn} className="flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink">
              <X size={13} /> Clear drawn area
            </button>
          )}
        </div>
      </Step>

      <Step n={2} title="Frames to compare" state={!areaDone ? "waiting" : framesDone ? "done" : "next"}>
        <div className="mb-3 grid grid-cols-3 gap-1" role="radiogroup" aria-label="Sensor">
          {(["NISAR", "RCM", "COMPARE"] as Sensor[]).map((s) => {
            const disabled = s !== "NISAR" && !!p.rcmReason;
            return (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={p.sensor === s}
                disabled={disabled}
                title={disabled ? p.rcmReason ?? "" : ""}
                onClick={() => p.onSensor(s)}
                className={`rounded-[3px] border py-1.5 text-[12px] font-semibold ${
                  p.sensor === s ? "border-marker bg-marker/10 text-marker" : disabled ? "border-dashed border-rule-soft text-ink-3 line-through" : "border-rule text-ink-2 hover:text-ink"
                }`}
              >
                {s === "COMPARE" ? "L vs C" : s}
              </button>
            );
          })}
        </div>
        {p.rcmReason && <p className="-mt-1.5 mb-3 text-[11px] leading-snug text-ink-3" title={p.rcmReason}>RCM (C-band): no data ingested for this area, so only NISAR can run.</p>}

        <div className="mb-3 grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="pol" className="label mb-1 block">Polarization</label>
            <select id="pol" value={pol} onChange={(e) => p.onConfig({ ...p.config, polarization: e.target.value as AnalysisConfig["polarization"] })} className="w-full rounded-[3px] border border-rule bg-housing-2 px-2 py-1.5 text-[13px] text-ink">
              {["HH", "HV", "VV", "VH"].map((x) => <option key={x}>{x}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="prod" className="label mb-1 block">Product</label>
            <select id="prod" value={freq} onChange={(e) => p.onConfig({ ...p.config, frequency: e.target.value as "A" | "B" })} className="w-full rounded-[3px] border border-rule bg-housing-2 px-2 py-1.5 text-[13px] text-ink">
              <option value="A">GCOV · freq A</option>
              <option value="B">GCOV · freq B</option>
            </select>
          </div>
        </div>

        {p.obsStatus === "loading" && <p className="text-[12px] text-ink-3">Loading observations…</p>}
        {p.obsStatus === "error" && <p className="text-[12px] text-error">Could not load observations.</p>}
        {p.obsStatus === "idle" && p.observations.length === 0 && areaDone && (
          <p className="text-[12px] leading-snug text-ink-2">No NISAR observations are registered for this area. Run <code className="num text-ink">scripts/fetch_demo.py</code>.</p>
        )}
        {p.observations.length > 0 && (
          <>
            <p className="mb-2 text-[11px] text-ink-3">
              <span className="num text-ink-2">{p.observations.length}</span> NISAR GCOV acquisitions in NASA CMR · <span className="num text-ink-2">{usable}</span> processed
            </p>
            <FrameList label="Earlier frame" side="earlier" observations={p.observations} selected={p.earlierId} other={later} onSelect={p.onEarlier} pol={pol} freq={freq} />
            <FrameList label="Later frame" side="later" observations={p.observations} selected={p.laterId} other={earlier} onSelect={p.onLater} pol={pol} freq={freq} />
          </>
        )}
      </Step>

      <Step n={3} title="Run change detection" state={!framesDone ? "waiting" : "next"}>
        <details className="group mb-3 rounded-[3px] border border-rule-soft">
          <summary className="flex cursor-pointer list-none items-center justify-between px-2.5 py-2 text-[12px] text-ink-2 hover:text-ink">
            <span>Analysis settings</span>
            <span className="num text-[11px] text-ink-3">±{p.config.threshold_db} dB · {p.config.water_threshold_db} dB · {p.config.speckle_filter} {p.config.filter_size}×{p.config.filter_size}</span>
          </summary>
          <div className="border-t border-rule-soft px-2.5 pt-3">
            <Slider label="Change threshold |ΔB|" value={p.config.threshold_db} min={1} max={8} step={0.5} unit=" dB" onChange={(v) => p.onConfig({ ...p.config, threshold_db: v })} hint="Pixels changing less than this are classed as limited change." />
            <Slider label="Open-water threshold" value={p.config.water_threshold_db} min={-26} max={-12} step={0.5} unit=" dB" onChange={(v) => p.onConfig({ ...p.config, water_threshold_db: v })} hint="Later backscatter below this, after a decrease, is water-like." />
            <Slider label="Minimum connected area" value={p.config.min_region_m2 / 10000} min={0} max={20} step={0.5} unit=" ha" onChange={(v) => p.onConfig({ ...p.config, min_region_m2: v * 10000 })} hint="Smaller isolated patches are not flagged as potential inundation." />
            <div className="mb-3 grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="flt" className="label mb-1 block">Speckle filter</label>
                <select id="flt" value={p.config.speckle_filter} onChange={(e) => p.onConfig({ ...p.config, speckle_filter: e.target.value as AnalysisConfig["speckle_filter"] })} className="w-full rounded-[3px] border border-rule bg-housing-2 px-2 py-1.5 text-[13px] text-ink">
                  <option value="lee">Lee</option>
                  <option value="boxcar">Boxcar</option>
                  <option value="none">None</option>
                </select>
              </div>
              <div>
                <label htmlFor="win" className="label mb-1 block">Window</label>
                <select id="win" value={p.config.filter_size} onChange={(e) => p.onConfig({ ...p.config, filter_size: Number(e.target.value) })} className="w-full rounded-[3px] border border-rule bg-housing-2 px-2 py-1.5 text-[13px] text-ink">
                  {[3, 5, 7, 9, 11].map((n) => <option key={n} value={n}>{n}×{n} px</option>)}
                </select>
              </div>
            </div>

          </div>
        </details>
        {framesDone && p.check && !p.check.ok && (
          <div role="alert" className="mb-3 rounded-[3px] border border-error/60 bg-error/10 px-3 py-2">
            <p className="mb-1 text-[12px] font-semibold text-error">This pair cannot be analysed</p>
            <ul className="list-disc pl-4 text-[12px] leading-snug text-ink-2">
              {p.check.errors.map((e) => <li key={e.code + e.message}>{e.message}</li>)}
            </ul>
          </div>
        )}
        {framesDone && p.check?.ok && p.check.warnings.length > 0 && (
          <ul className="mb-3 list-disc pl-4 text-[11.5px] leading-snug text-warn">
            {p.check.warnings.map((w) => <li key={w.code}>{w.message}</li>)}
          </ul>
        )}
        {p.runErrors.length > 0 && (
          <div role="alert" className="mb-3 rounded-[3px] border border-error/60 bg-error/10 px-3 py-2 text-[12px] text-ink-2">
            {p.runErrors.map((e) => <p key={e.code + e.message}>{e.message}</p>)}
          </div>
        )}
        <button
          type="button"
          onClick={p.onRun}
          disabled={!canRun}
          className="flex w-full items-center justify-center gap-2 rounded-[3px] bg-marker py-2.5 text-[13px] font-bold text-marker-ink transition-opacity [font-stretch:110%] disabled:cursor-not-allowed disabled:bg-housing-3 disabled:text-ink-3"
        >
          {p.running && <Loader2 size={15} className="animate-spin" />}
          {p.running ? "Processing real frames…" : p.checking ? "Checking compatibility…" : "Run analysis"}
        </button>
        {p.running && p.stage && (
          <p className="mt-2 flex items-center gap-2 text-[11.5px] text-ink-2" role="status" aria-live="polite">
            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-marker" aria-hidden />
            {p.stage}
          </p>
        )}
        {!framesDone && <p className="mt-1.5 text-[11px] text-ink-3">Select an earlier and a later frame first.</p>}
      </Step>
    </div>
  );
}
