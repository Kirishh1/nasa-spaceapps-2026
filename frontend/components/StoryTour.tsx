"use client";

import { ChevronLeft, ChevronRight, X } from "lucide-react";

import type { AnalysisResult } from "@/services/api";

export type TourView = "water" | "change" | "delta" | "lc" | "impact" | "photo" | "swipe";

export interface TourStep {
  title: string;
  body: string;
  view: TourView;
  fold?: string;
}

const pct = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${Math.round(x * 100)}%`);
const km = (x: number) => (x >= 100 ? x.toFixed(0) : x.toFixed(1));
const day = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

/** Steps built from the computed result, so every number in the tour is real. */
export function buildTour(r: AnalysisResult): TourStep[] {
  const w = r.water;
  const acc = r.validation.accuracy ?? [];
  const opt = acc.find((a) => a.product === "DSWX_HLS");
  const s1 = acc.find((a) => a.product === "DSWX_S1" && a.side === "later");
  const sc = r.sensor_comparison;
  const swp = r.validation.swot?.status === "available" ? r.validation.swot.passes ?? [] : [];
  const wet = (sc.by_landcover ?? []).find((x) => x.class === 90);
  const water80 = (sc.by_landcover ?? []).find((x) => x.class === 80 && x.cells >= 1000);
  const steps: TourStep[] = [
    {
      title: "The problem",
      body: r.study_area.story?.problem ?? `${r.study_area.name}: radar sees through cloud and vegetation, so it can track surface water through the season when optical satellites cannot.`,
      view: "water",
    },
    {
      title: "The data",
      body: `Two real NASA–ISRO NISAR L-band radar passes from the same orbit: ${day(r.earlier.date)} (monsoon) and ${day(r.later.date)} (post-monsoon), ${r.days_between} days apart. Drag the divider to compare them. Dark is smooth water; bright is land and vegetation.`,
      view: "swipe",
    },
  ];
  if (w) {
    steps.push({
      title: "The discovery",
      body: `Open water ${w.later_km2 < w.earlier_km2 ? "shrank" : "grew"} from ${km(w.earlier_km2)} km² to ${km(w.later_km2)} km²: ${km(w.lost_km2)} km² receded (orange) and ${km(w.gained_km2)} km² newly flooded (cyan). The water threshold is chosen automatically for each image, not tuned by hand.`,
      view: "water",
      fold: "fold-water",
    });
  }
  if (opt || s1) {
    steps.push({
      title: "Is it right?",
      body: (opt
        ? `We checked the ${day(opt.nisar_date)} water map against an independent NASA OPERA map from a cloud-free optical satellite ${opt.offset_days === 0 ? "the same day" : `${opt.offset_days} day${opt.offset_days === 1 ? "" : "s"} apart`}: F1 ${opt.open_water.f1?.toFixed(2)}, IoU ${opt.open_water.iou?.toFixed(2)}. Shifting the threshold by ±3 dB keeps F1 between ${Math.min(...(opt.threshold_sensitivity ?? []).map((x) => x.f1 ?? 1)).toFixed(2)} and ${Math.max(...(opt.threshold_sensitivity ?? []).map((x) => x.f1 ?? 0)).toFixed(2)}. This scores one date's water map; where exactly water changed is less certain (see the validation panel).`
        : `We checked the water maps against independent NASA OPERA surface-water maps from within a day of each pass.`) +
        (swp.length ? ` Separately, NASA/CNES's SWOT satellite measured the lakes' water height: every lake it saw fell, by a median of ${swp.map((p) => `${Math.abs(p.median_change_m).toFixed(2)} m`).join(" and ")}.` : ""),
      view: "water",
      fold: "fold-validation",
    });
  }
  if (s1 || sc.status === "available") {
    steps.push({
      title: "Two wavelengths, two answers",
      body:
        (s1 ? `Over the same pixels on ${day(s1.date)}, NISAR's L-band maps ${pct(s1.open_water.predicted_fraction)} as open water and Sentinel-1's C-band ${pct(s1.open_water.reference_fraction)}.` +
          (opt && opt.nisar_date === s1.nisar_date
            ? ` The optical map (${pct(opt.open_water.reference_fraction)}) is closer to ${Math.abs((opt.open_water.predicted_fraction ?? 0) - (opt.open_water.reference_fraction ?? 0)) < Math.abs((s1.open_water.reference_fraction ?? 0) - (opt.open_water.reference_fraction ?? 0)) ? "L-band" : "C-band"}. `
            : " ") : "") +
        (sc.status === "available" && wet
          ? `In herbaceous wetland their change maps agree on ${wet.agree_percent}% of cells (κ ${wet.kappa != null ? wet.kappa.toFixed(2) : "–"}); ` +
            (wet.c_band_only_percent > 2 * wet.l_band_only_percent && wet.c_band_only_percent > 20
              ? `C-band alone reports change on ${wet.c_band_only_percent}%. `
              : wet.l_band_only_percent > 2 * wet.c_band_only_percent && wet.l_band_only_percent > 20
                ? `L-band alone reports change on ${wet.l_band_only_percent}%. `
                : "") +
            (water80 && water80.c_band_only_percent > 20 ? `On permanent open water C-band alone reports change on ${water80.c_band_only_percent}%, consistent with its sensitivity to wind ripples. ` : "") +
            "The bands also differ in polarization and viewing geometry, so these are plausible explanations, not proven ones."
          : ""),
      view: sc.status === "available" ? "lc" : "water",
      fold: "fold-lband",
    });
  }
  const im = r.impact;
  if (im && (im.cropland_emerged_km2 || im.people_within_1km_of_receded_water)) {
    steps.push({
      title: "Why it matters",
      body: `${im.cropland_emerged_km2 ? `${Math.round(im.cropland_emerged_km2)} km² of cropland came out of the water${im.cropland_flooded_km2 ? ` and ${Math.round(im.cropland_flooded_km2)} km² went under` : ""}. ${r.study_area.story?.impact ?? ""} ` : ""}` +
        `${im.people_in_area ? `About ${im.people_in_area >= 1e5 ? `${(im.people_in_area / 1e6).toFixed(2)} million` : im.people_in_area.toLocaleString()} people live in the area (WorldPop 2025); living near changing water is exposure context, not harm. ` : ""}` +
        `${im.volume_change_km3_approx ? `Roughly ${Math.abs(im.volume_change_km3_approx).toFixed(1)} km³ of water left the basin (order of magnitude, from NISAR area × SWOT level drop).` : ""}`,
      view: "impact",
      fold: "fold-impact",
    });
  }
  steps.push({
    title: "What it can and can't tell us",
    body: `This maps where open water changed and how well that matches independent observations. It does not measure depth, and flooded vegetation under a canopy can be missed. The references are other satellites, not field data. The season chart shows how much the C-band reference itself swings between orbits.`,
    view: "water",
    fold: "fold-season",
  });
  return steps;
}

export function StoryTour({ steps, index, onIndex, onClose }: { steps: TourStep[]; index: number; onIndex: (i: number) => void; onClose: () => void }) {
  const s = steps[index];
  if (!s) return null;
  return (
    <div className="pointer-events-auto absolute top-4 left-1/2 z-30 w-[min(460px,calc(100%-32px))] -translate-x-1/2 rounded-[3px] border border-marker/70 bg-housing-1/95 px-4 py-3 shadow-[0_10px_30px_rgba(0,0,0,0.55)] backdrop-blur-[2px]" role="dialog" aria-label="Guided tour">
      <div className="mb-1 flex items-center justify-between">
        <p className="num text-[11px] text-marker">{index + 1} / {steps.length}</p>
        <button type="button" onClick={onClose} aria-label="Close tour" className="text-ink-3 hover:text-ink"><X size={15} /></button>
      </div>
      <h3 className="text-[15px] font-semibold text-ink [font-stretch:106%]">{s.title}</h3>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{s.body}</p>
      <div className="mt-3 flex items-center justify-between">
        <button type="button" disabled={index === 0} onClick={() => onIndex(index - 1)} className="flex items-center gap-1 text-[12px] text-ink-2 hover:text-ink disabled:opacity-30">
          <ChevronLeft size={14} /> Back
        </button>
        <div className="flex gap-1" aria-hidden>
          {steps.map((_, i) => <span key={i} className={`h-1.5 w-1.5 rounded-full ${i === index ? "bg-marker" : "bg-rule"}`} />)}
        </div>
        {index < steps.length - 1 ? (
          <button type="button" onClick={() => onIndex(index + 1)} className="flex items-center gap-1 rounded-[3px] bg-marker px-2.5 py-1 text-[12px] font-semibold text-marker-ink">
            Next <ChevronRight size={14} />
          </button>
        ) : (
          <button type="button" onClick={onClose} className="rounded-[3px] bg-marker px-2.5 py-1 text-[12px] font-semibold text-marker-ink">Explore</button>
        )}
      </div>
    </div>
  );
}
