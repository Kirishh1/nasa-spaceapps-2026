"use client";

import { useEffect, useState } from "react";

import { api, type Diagnostics } from "@/services/api";

const cache = new Map<string, Promise<Diagnostics>>();
function useDiagnostics(id: string): Diagnostics | null {
  const [d, setD] = useState<Diagnostics | null>(null);
  useEffect(() => {
    let live = true;
    if (!cache.has(id)) cache.set(id, api.diagnostics(id).catch(() => ({ status: "unavailable" }) as Diagnostics));
    cache.get(id)!.then((x) => live && setD(x));
    return () => { live = false; };
  }, [id]);
  return d?.status === "available" ? d : null;
}

const pct = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(100 * x)}%`);
const f2 = (x: number | null | undefined) => (x == null ? "–" : x.toFixed(2));
const range = (xs: number[], fmt: (x: number) => string) => (xs.length ? `${fmt(Math.min(...xs))}–${fmt(Math.max(...xs))}` : "–");

/** Why pixel-level change agreement with the C-band reference is weak (scripts/validation_diagnostics.py). */
export function ChangeDiagnostics({ id }: { id: string }) {
  const d = useDiagnostics(id);
  const tracks = d?.B_change_vs_s1 ?? [];
  const opt = d?.A_reference_quality?.s1_vs_optical_same_days ?? [];
  if (!d || (!tracks.length && !opt.length)) return null;
  const june = tracks.map((t) => t.reference_water_km2[0]);
  const edge3 = tracks.map((t) => ({ f0: t.edge_buffer.find((e) => e.exclude_within_px === 0)?.f1, f3: t.edge_buffer.find((e) => e.exclude_within_px === 3)?.f1 }));
  const budget = d.B_error_budget?.per_date_water_map_disagreement ?? [];
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-[11.5px] text-ink-3 underline underline-offset-2">Why the change check is weak: diagnostics</summary>
      <ul className="mt-1.5 list-disc pl-4 text-[11.5px] leading-snug text-ink-3">
        {opt.length > 0 && (
          <li className="mb-1">
            The C-band reference finds less water than optical maps from the same days: Sentinel-1 {range(opt.map((o) => o.s1_water_fraction ?? 0), (x) => pct(x))} open water vs optical{" "}
            {range(opt.map((o) => o.optical_water_fraction ?? 0), (x) => pct(x))} (F1 {range(opt.map((o) => o.f1_open ?? 0), f2)}, {opt.length} same-week pairs).
          </li>
        )}
        {june.length > 1 && (
          <li className="mb-1">
            Sentinel-1 orbits disagree with each other: within one week of {tracks[0].dates[0].slice(5)}, the four orbits map{" "}
            <span className="num text-ink-2">{Math.round(Math.min(...june))}–{Math.round(Math.max(...june))} km²</span> of open water (NISAR: {Math.round(tracks[0].nisar_water_km2[0])} km²).
          </li>
        )}
        {edge3.some((e) => e.f0 != null) && (
          <li className="mb-1">
            Not edge jitter: leaving out every pixel within 60 m of a water edge changes F1 from {range(edge3.map((e) => e.f0 ?? 0), f2)} to {range(edge3.map((e) => e.f3 ?? 0), f2)}, so the disagreement lies inside water bodies, not along their edges.
          </li>
        )}
        {budget.length > 0 && (
          <li className="mb-1">
            Each date&apos;s water map differs from its reference over {range(budget.map((b) => b.disagreement_km2), (x) => `${Math.round(x)}`)} km², about the size of the {Math.round(d.B_error_budget!.nisar_lost_km2)} km² change, so the
            pixel pattern of a change map is much less certain than either date&apos;s map. Per-date F1 is <em>not</em> change accuracy.
          </li>
        )}
        <li className="mb-1">Timing is not the main cause: all reference pairs are within 5–7 days of the NISAR dates, and the differences between orbits are larger than the differences between dates.</li>
      </ul>
    </details>
  );
}

/** Threshold sensitivity of the impact numbers and the population caveat. */
export function ImpactSensitivity({ id }: { id: string }) {
  const d = useDiagnostics(id);
  const s = d?.D_impact?.threshold_sensitivity ?? [];
  if (!d || !s.length) return null;
  const lo = s.find((x) => x.threshold_shift_db === -1), hi = s.find((x) => x.threshold_shift_db === 1);
  const pop = d.D_impact?.population;
  return (
    <div className="mt-2 text-[11.5px] leading-snug text-ink-3">
      {lo && hi && (
        <p>
          Shifting both water thresholds by ±1 dB gives <span className="num text-ink-2">{Math.round(Math.min(lo.lost_km2, hi.lost_km2))}–{Math.round(Math.max(lo.lost_km2, hi.lost_km2))} km²</span> receded
          {lo.cropland_emerged_km2 != null && hi.cropland_emerged_km2 != null ? <>, of which cropland <span className="num text-ink-2">{Math.round(Math.min(lo.cropland_emerged_km2, hi.cropland_emerged_km2))}–{Math.round(Math.max(lo.cropland_emerged_km2, hi.cropland_emerged_km2))} km²</span></> : null}.
        </p>
      )}
      {pop && (
        <p className="mt-1">
          Residents within 200 m / 500 m / 1 km of drained land: <span className="num text-ink-2">{(pop.people_within_distance_of_drained_land["0.2km"] ?? 0).toLocaleString()}</span> /{" "}
          <span className="num text-ink-2">{(pop.people_within_distance_of_drained_land["0.5km"] ?? 0).toLocaleString()}</span> /{" "}
          <span className="num text-ink-2">{(pop.people_within_distance_of_drained_land["1km"] ?? 0).toLocaleString()}</span> of {pop.people_in_area.toLocaleString()}. {pop.note}
        </p>
      )}
      {d.D_impact?.landcover_caveat && <p className="mt-1">{d.D_impact.landcover_caveat}</p>}
    </div>
  );
}
