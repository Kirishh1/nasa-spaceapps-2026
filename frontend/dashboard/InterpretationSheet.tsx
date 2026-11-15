"use client";

import { ChevronRight, ExternalLink } from "lucide-react";

import type { AnalysisResult, Observation, StudyArea } from "@/services/api";
import { ChangeHistogram } from "./ChangeHistogram";
import { DataSources } from "./DataSources";
import { RainfallStrip } from "./RainfallStrip";

const km2 = (v: number) => (v >= 100 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v.toFixed(2));

/** One always-visible line naming the NASA data the result is built from. */
function NasaLine() {
  const open = () => {
    const d = document.getElementById("data-sources") as HTMLDetailsElement | null;
    if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }); }
  };
  return (
    <p className="mt-3 text-[12px] leading-snug text-ink-3">
      Data: <span className="text-ink-2">NASA–ISRO NISAR L2 GCOV</span> from NASA&apos;s ASF DAAC, found via NASA CMR.{" "}
      <button type="button" onClick={open} className="text-ink-2 underline underline-offset-2 hover:text-ink">All sources</button>
    </p>
  );
}

/** Collapsible section whose closed row already carries its key value. */
function Fold({ title, value, tone = "ink", defaultOpen = false, id, children }: {
  title: string; value?: React.ReactNode; tone?: "ink" | "muted" | "warn"; defaultOpen?: boolean; id?: string; children: React.ReactNode;
}) {
  const toneCls = tone === "muted" ? "text-ink-3" : tone === "warn" ? "text-warn" : "text-ink";
  return (
    <details id={id} open={defaultOpen} className="group border-t border-rule">
      <summary className="flex cursor-pointer list-none items-center gap-2 py-3 hover:bg-housing-1 [&::-webkit-details-marker]:hidden">
        <ChevronRight size={14} className="shrink-0 text-ink-3 transition-transform group-open:rotate-90" aria-hidden />
        <span className="flex-1 text-[13px] font-semibold text-ink [font-stretch:106%]">{title}</span>
        {value !== undefined && <span className={`num text-right text-[12px] ${toneCls}`}>{value}</span>}
      </summary>
      <div className="pb-5 pl-[22px]">{children}</div>
    </details>
  );
}

function Row({ k, v, sub }: { k: React.ReactNode; v: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-[3px]">
      <dt className="text-[12px] text-ink-3">{k}</dt>
      <dd className="num text-right text-[12.5px] text-ink">{v}{sub && <span className="ml-1 text-ink-3">{sub}</span>}</dd>
    </div>
  );
}

function FrameColumn({ o, side }: { o: Observation; side: string }) {
  return (
    <div className="min-w-0">
      <p className={`strip mb-1 ${side === "Later" ? "text-marker" : "text-ink"}`}>{side}</p>
      <p className="num text-[15px] text-ink">{o.date}</p>
      <p className="strip mt-0.5 leading-relaxed">
        {o.start_time.slice(11, 19)} UTC<br />
        T{String(o.track).padStart(3, "0")} {o.pass_direction} <br />F{String(o.frame).padStart(3, "0")} · v{o.product_version}
      </p>
      <div className="mt-1 flex gap-3 text-[11px]">
        {o.qa_report_url && <a href={o.qa_report_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink-2 underline underline-offset-2 hover:text-ink">QA report <ExternalLink size={10} /></a>}
        {o.browse_url && <a href={o.browse_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink-2 underline underline-offset-2 hover:text-ink">Browse <ExternalLink size={10} /></a>}
      </div>
    </div>
  );
}

/** Proportional bar of class areas; each segment labeled in text below so colour is never the only carrier. */
function ClassBar({ r }: { r: AnalysisResult }) {
  const s = r.statistics;
  const total = s.analyzed_pixels || 1;
  const seg = [
    { k: "Decrease", px: s.classes.significant_decrease.pixels, c: "var(--decrease)", pattern: false },
    { k: "Limited", px: s.classes.limited_change.pixels, c: "var(--limited)", pattern: false },
    { k: "Increase", px: s.classes.significant_increase.pixels, c: "var(--increase)", pattern: false },
    { k: "No data", px: s.missing_pixels, c: "transparent", pattern: true },
  ];
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-[1px] border border-rule" role="img" aria-label="Share of analysed area by change class">
        {seg.map((x) => (
          <div key={x.k} style={{ width: `${(100 * x.px) / total}%`, background: x.pattern ? "repeating-linear-gradient(135deg,transparent 0 3px,var(--rule) 3px 4px)" : x.c }} />
        ))}
      </div>
    </div>
  );
}

export function InterpretationSheet({ area, result, earlier, later, storedAt }: { area: StudyArea | null; result: AnalysisResult | null; earlier: Observation | null; later: Observation | null; storedAt?: string | null }) {
  if (!result) {
    return (
      <div>
        <h2 className="text-[20px] leading-tight font-semibold text-ink [font-stretch:104%]">{area?.name ?? "No study area"}</h2>
        {area?.research_question && <p className="mt-3 text-[14px] leading-relaxed text-ink">{area.research_question}</p>}
        <p className="mt-4 text-[12.5px] leading-relaxed text-ink-3">
          {earlier && later
            ? <>Frames from {earlier.date} and {later.date} are ready. Press <span className="text-ink-2">Run analysis</span> to measure what changed.</>
            : <>Pick an earlier and a later frame on the left. Results appear here only after the real frames have been processed.</>}
        </p>
        <NasaLine />
        <div className="mt-6">
          {area?.description && (
            <Fold title="About this area" tone="muted">
              <p className="text-[12.5px] leading-relaxed text-ink-2">{area.description}</p>
            </Fold>
          )}
          <Fold title="Data sources" value="NASA NISAR · CMR · Earthdata" tone="muted" id="data-sources">
            <DataSources />
          </Fold>
        </div>
      </div>
    );
  }

  const s = result.statistics;
  const u = result.uncertainty;
  const v = result.validation;
  const jrc = v.jrc_surface_water;
  const lc = v.landcover_breakdown;
  const ow = s.potential_inundation.open_water;
  const vf = s.potential_inundation.vegetated;
  const pct = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${(100 * x).toFixed(1)}%`);

  const changed = s.classes.significant_decrease.area_km2 + s.classes.significant_increase.area_km2;
  const nr = s.noise_reference;
  const fmtDate = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

  return (
    <div>
      <h2 className="text-[20px] leading-tight font-semibold text-ink [font-stretch:104%]">{result.study_area.name}</h2>
      <p className="mt-1 text-[12.5px] text-ink-2">
        {fmtDate(result.earlier.date)} → {fmtDate(result.later.date)} {result.later.date.slice(0, 4)} · {result.days_between} days · NISAR L-band {result.config.polarization}
      </p>

      {/* the answer, stated in a sentence built from the computed values */}
      <p className="mt-4 text-[15px] leading-relaxed text-ink">
        Backscatter fell over <span className="num text-decrease">{km2(s.classes.significant_decrease.area_km2)} km²</span> and rose over{" "}
        <span className="num text-increase">{km2(s.classes.significant_increase.area_km2)} km²</span> of the {km2(s.analyzed_area_km2)} km² basin.{" "}
        {ow.pixels > 0
          ? <><span className="num text-water">{km2(ow.area_km2)} km²</span> of the decreases look like possible new open water.</>
          : <>No decrease looks like new open water under the current thresholds.</>}
      </p>

      <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] leading-snug text-ink-2">
        <span className="rounded-[2px] bg-marker px-1.5 py-px text-[10.5px] font-bold tracking-wide text-marker-ink uppercase">Not validated</span>
        {nr ? <span>{nr.observed_exceedance_percent.toFixed(1)}% of pixels changed; noise alone would explain about {nr.expected_exceedance_percent_gaussian.toFixed(1)}%.</span> : <span>Treat as potential change, not confirmed flooding.</span>}
      </p>

      <NasaLine />
      {storedAt && <p className="mt-2 text-[11px] text-ink-3">Stored result from {storedAt.slice(0, 16).replace("T", " ")} UTC · Run analysis to recompute it live.</p>}

      <div className="mt-5">
        <Fold title="Change breakdown" value={`${km2(changed)} km² changed`}>
          <ClassBar r={result} />
          <dl className="mt-3">
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-decrease" aria-hidden />Significant decrease</span>} v={km2(s.classes.significant_decrease.area_km2)} sub={`km² · ${s.classes.significant_decrease.percent_of_valid.toFixed(1)}%`} />
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-increase" aria-hidden />Significant increase</span>} v={km2(s.classes.significant_increase.area_km2)} sub={`km² · ${s.classes.significant_increase.percent_of_valid.toFixed(1)}%`} />
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-limited" aria-hidden />Limited change</span>} v={km2(s.classes.limited_change.area_km2)} sub={`km² · ${s.classes.limited_change.percent_of_valid.toFixed(1)}%`} />
          </dl>
          <div className="mt-4">
            <ChangeHistogram h={s.histogram} threshold={result.config.threshold_db} />
          </div>
          <dl className="mt-3">
            <Row k="Analysed area" v={km2(s.analyzed_area_km2)} sub="km²" />
            <Row k="Valid pixels" v={`${s.valid_percent.toFixed(1)}%`} sub={`${s.valid_pixels.toLocaleString()} px`} />
            <Row k="Missing data" v={km2(s.missing_area_km2)} sub="km²" />
            <Row k="ΔB median · p05 · p95" v={`${s.delta_db.median?.toFixed(2)} · ${s.delta_db.p05?.toFixed(2)} · ${s.delta_db.p95?.toFixed(2)}`} sub="dB" />
          </dl>
        </Fold>

        <Fold title="Possible new water" value={`${km2(ow.area_km2)} km²`}>
          <dl>
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-water" aria-hidden />Open-water emergence</span>} v={km2(ow.area_km2)} sub={`km² · ${ow.percent_of_valid.toFixed(2)}%`} />
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-vegetated" aria-hidden />Flooded-vegetation candidates</span>} v={result.inundation.vegetated_flooding_evaluated ? km2(vf.area_km2) : "not evaluated"} sub={result.inundation.vegetated_flooding_evaluated ? "km²" : undefined} />
          </dl>
          <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
            Flagged when ΔB ≤ −{result.config.threshold_db} dB, the later return is below {result.config.water_threshold_db} dB, and the patch is at least {(result.config.min_region_m2 / 10000).toFixed(1)} ha.
            Flooded-vegetation candidates are increases of at least {result.config.threshold_db} dB inside tree, wetland or mangrove cover (possible double bounce).
            {result.inundation.reason ? ` ${result.inundation.reason}` : ""}
            {result.inundation.vegetated_flooding_reason ? ` ${result.inundation.vegetated_flooding_reason}` : ""}
          </p>
        </Fold>

        <Fold title="How confident is this?" value="Not validated" tone="warn">
          <p className="mb-2 text-[12.5px] leading-relaxed text-ink">{v.statement}</p>
          {nr && (
            <dl className="mb-2">
              <Row k="Pixels past the threshold" v={`${nr.observed_exceedance_percent.toFixed(1)}%`} />
              <Row k="Expected from noise alone" v={`${nr.expected_exceedance_percent_gaussian.toFixed(1)}%`} />
              <Row k="ΔB spread (robust σ)" v={nr.robust_sigma_db.toFixed(2)} sub={`dB · threshold = ${nr.threshold_in_sigma}σ`} />
            </dl>
          )}
          <p className="mb-2 text-[12px] leading-relaxed text-ink-2">{u.interpretation_caveat}</p>
          <p className="label mb-1">What else can change backscatter</p>
          <ul className="list-disc pl-4 text-[11.5px] leading-snug text-ink-3 marker:text-ink-3">
            {u.false_positive_sources.map((x) => <li key={x} className="mb-1">{x}</li>)}
          </ul>
        </Fold>

        <Fold title="Reference checks" value={jrc && !jrc.status ? `${pct(jrc.fraction_candidates_in_historically_wet_pixels)} in known wet areas` : "not run"} tone="muted">
          {jrc && !jrc.status ? (
            <>
              <dl>
                <Row k="Candidates in historically wet pixels" v={pct(jrc.fraction_candidates_in_historically_wet_pixels)} />
                <Row k="Baseline: all valid pixels" v={pct(jrc.baseline_fraction_historically_wet)} />
                <Row k="Candidates in permanent water (≥90%)" v={pct(jrc.fraction_candidates_in_permanent_water)} />
              </dl>
              {jrc.caveat && <p className="mt-2 text-[12px] leading-snug text-warn">{jrc.caveat}</p>}
              <p className="mt-2 text-[11.5px] leading-snug text-ink-3">{jrc.interpretation}</p>
              <p className="mt-1 text-[11px] text-ink-3">{jrc.source?.name}. {jrc.source?.citation}.</p>
            </>
          ) : (
            <p className="text-[12px] text-ink-3">{jrc?.reason ?? "JRC reference not evaluated."}</p>
          )}
          {lc?.rows && (
            <table className="mt-3 w-full text-[11.5px]">
              <caption className="label mb-1 text-left">Change by ESA WorldCover class</caption>
              <thead>
                <tr className="text-ink-3"><th className="py-1 text-left font-normal">Class</th><th className="text-right font-normal">Decr.</th><th className="text-right font-normal">Incr.</th></tr>
              </thead>
              <tbody className="num">
                {lc.rows.filter((x) => x.pixels > 0.01 * s.valid_pixels).map((x) => (
                  <tr key={x.class} className="border-t border-rule-soft">
                    <td className="py-1 font-sans text-ink-2">{x.name}</td>
                    <td className="text-right text-ink">{x.percent_decrease.toFixed(1)}%</td>
                    <td className="text-right text-ink">{x.percent_increase.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Fold>

        <Fold title="The two radar frames" value={`${fmtDate(result.earlier.date)} · ${fmtDate(result.later.date)}`} tone="muted">
          <div className="grid grid-cols-2 gap-4">
            <FrameColumn o={result.earlier} side="Earlier" />
            <FrameColumn o={result.later} side="Later" />
          </div>
          <dl className="mt-3">
            <Row k="Grid" v={result.grid.crs} />
            <Row k="Pixel spacing" v={`${result.grid.pixel_spacing_m[0]} × ${result.grid.pixel_spacing_m[1]}`} sub="m" />
            <Row k="Raster size" v={`${result.grid.shape[1]} × ${result.grid.shape[0]}`} sub="px" />
            <Row k="Speckle filter" v={String(u.method.speckle_filter)} />
          </dl>
          <ul className="mt-2 list-disc pl-4 text-[11.5px] leading-snug text-ink-3">
            {u.alignment.map((a) => <li key={a}>{a}</li>)}
            {u.compatibility_warnings.map((w) => <li key={w.code} className="text-warn">{w.message}</li>)}
          </ul>
        </Fold>

        <Fold title="Rainfall (NASA GPM)" value={result.precipitation?.status === "available" ? `${result.precipitation.between_acquisitions?.total_mm ?? "—"} mm` : "unavailable"} tone="muted">
          <RainfallStrip p={result.precipitation} earlier={result.earlier.date} later={result.later.date} />
        </Fold>

        <Fold title="L-band vs C-band" value="no C-band data" tone="muted">
          <p className="text-[12px] leading-relaxed text-ink-2">{result.sensor_comparison.reason}</p>
          <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
            When RCM data exists, each sensor&apos;s change map is derived on its own and compared on a common coarser grid. Raw L-band and C-band backscatter are never subtracted from each other.
          </p>
        </Fold>

        <Fold title="Data sources" value="NASA NISAR · CMR · Earthdata" tone="muted" id="data-sources">
          <DataSources analysisId={result.id} />
        </Fold>
      </div>
      <p className="strip mt-4 text-[10.5px] text-ink-3">Analysis {result.id} · {result.created_at.slice(0, 19).replace("T", " ")} UTC</p>
    </div>
  );
}
