"use client";

import { ExternalLink } from "lucide-react";

import type { AnalysisResult, Observation, StudyArea } from "@/services/api";
import { ChangeHistogram } from "./ChangeHistogram";
import { RainfallStrip } from "./RainfallStrip";

const km2 = (v: number) => (v >= 100 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v.toFixed(2));

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-rule pt-4 pb-5">
      <h3 className="mb-3 text-[13px] font-semibold text-ink [font-stretch:108%]">{title}</h3>
      {children}
    </section>
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
        <h2 className="text-[19px] leading-tight font-semibold text-ink [font-stretch:104%]">{area?.name ?? "No study area"}</h2>
        {area?.description && <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{area.description}</p>}
        {area?.research_question && (
          <div className="mt-4 border-l border-marker pl-3">
            <p className="label mb-1">Research question</p>
            <p className="text-[13px] leading-relaxed text-ink">{area.research_question}</p>
          </div>
        )}
        <div className="mt-6 rounded-[3px] border border-dashed border-rule px-4 py-5 text-[12.5px] leading-relaxed text-ink-2">
          {earlier && later ? (
            <>Frames {earlier.date} and {later.date} are on the table. Run the analysis to compute ΔB and its statistics.</>
          ) : (
            <>Pick two dated frames in the tool tray. Statistics appear here only after the backend has processed real observations. Nothing on this sheet is precomputed.</>
          )}
        </div>
        {area && (
          <dl className="mt-5">
            <Row k="Bounding box W, S" v={`${area.bbox[0].toFixed(3)}°, ${area.bbox[1].toFixed(3)}°`} />
            <Row k="Bounding box E, N" v={`${area.bbox[2].toFixed(3)}°, ${area.bbox[3].toFixed(3)}°`} />
          </dl>
        )}
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

  return (
    <div>
      {storedAt && (
        <p className="mb-3 rounded-[3px] border border-dashed border-rule px-3 py-2 text-[11.5px] leading-snug text-ink-3">
          Stored result, computed {storedAt.slice(0, 16).replace("T", " ")} UTC from the frames below. Press <span className="text-ink-2">Run analysis</span> to recompute it live.
        </p>
      )}
      <h2 className="text-[19px] leading-tight font-semibold text-ink [font-stretch:104%]">{result.study_area.name}</h2>
      <p className="mt-1 text-[12.5px] text-ink-2">
        <span className="num">{result.days_between}</span>-day NISAR L-band comparison · {result.config.polarization} · GCOV freq {result.config.frequency}
      </p>
      {area?.research_question && (
        <p className="mt-3 border-l border-marker pl-3 text-[12.5px] leading-relaxed text-ink-2">{area.research_question}</p>
      )}

      {/* the reading, stated in sentences built from the computed values */}
      <p className="mt-4 text-[14px] leading-relaxed text-ink">
        Across <span className="num">{km2(s.analyzed_area_km2)}</span> km², backscatter fell by more than {result.config.threshold_db} dB over{" "}
        <span className="num text-decrease">{km2(s.classes.significant_decrease.area_km2)} km²</span> and rose over{" "}
        <span className="num text-increase">{km2(s.classes.significant_increase.area_km2)} km²</span>.{" "}
        {ow.pixels > 0 ? (
          <>Of the decreases, <span className="num text-water">{km2(ow.area_km2)} km²</span> reached water-like returns in connected patches. These are <em>potential</em> inundation-related changes, not confirmed flooding.</>
        ) : (
          <>No connected decrease reached water-like returns under the current thresholds.</>
        )}
      </p>

      <Section title="Change analysis">
        <ClassBar r={result} />
        <dl className="mt-3">
          <Row k="Analysed area" v={km2(s.analyzed_area_km2)} sub="km²" />
          <Row k="Valid pixels" v={`${s.valid_percent.toFixed(1)}%`} sub={`${s.valid_pixels.toLocaleString()} px`} />
          <Row k="Missing data" v={km2(s.missing_area_km2)} sub="km²" />
          <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-decrease" aria-hidden />Significant decrease</span>} v={km2(s.classes.significant_decrease.area_km2)} sub={`km² · ${s.classes.significant_decrease.percent_of_valid.toFixed(1)}%`} />
          <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-increase" aria-hidden />Significant increase</span>} v={km2(s.classes.significant_increase.area_km2)} sub={`km² · ${s.classes.significant_increase.percent_of_valid.toFixed(1)}%`} />
          <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-limited" aria-hidden />Limited change</span>} v={km2(s.classes.limited_change.area_km2)} sub={`km² · ${s.classes.limited_change.percent_of_valid.toFixed(1)}%`} />
        </dl>
        <div className="mt-4">
          <ChangeHistogram h={s.histogram} threshold={result.config.threshold_db} />
          <p className="num mt-1 text-[11px] text-ink-3">
            ΔB median {s.delta_db.median?.toFixed(2)} dB · p05 {s.delta_db.p05?.toFixed(2)} · p95 {s.delta_db.p95?.toFixed(2)}
          </p>
          {s.noise_reference && (
            <div className="mt-3">
              <p className="label mb-1">Change versus scatter</p>
              <dl>
                <Row k="Robust ΔB spread (σ)" v={s.noise_reference.robust_sigma_db.toFixed(2)} sub={`dB · threshold = ${s.noise_reference.threshold_in_sigma}σ`} />
                <Row k="Pixels past threshold, observed" v={`${s.noise_reference.observed_exceedance_percent.toFixed(1)}%`} />
                <Row k="Expected from Gaussian scatter alone" v={`${s.noise_reference.expected_exceedance_percent_gaussian.toFixed(1)}%`} />
              </dl>
              <p className="mt-1 text-[11.5px] leading-snug text-ink-3">An observed share well above the Gaussian expectation points to change beyond the overall ΔB scatter. Some significant pixels are still expected to be residual speckle.</p>
            </div>
          )}
        </div>
      </Section>

      <Section title="Potential inundation">
        <dl>
          <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-water" aria-hidden />Open-water emergence</span>} v={km2(ow.area_km2)} sub={`km² · ${ow.percent_of_valid.toFixed(2)}%`} />
          <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-vegetated" aria-hidden />Flooded-vegetation candidates</span>} v={result.inundation.vegetated_flooding_evaluated ? km2(vf.area_km2) : "not evaluated"} sub={result.inundation.vegetated_flooding_evaluated ? "km²" : undefined} />
        </dl>
        <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
          Rule: ΔB ≤ −{result.config.threshold_db} dB, later return below {result.config.water_threshold_db} dB, connected patch ≥ {(result.config.min_region_m2 / 10000).toFixed(1)} ha.
          Flooded vegetation: ΔB ≥ +{result.config.threshold_db} dB inside WorldCover tree, wetland or mangrove cover (possible double bounce).
          {result.inundation.reason ? ` ${result.inundation.reason}` : ""}
          {result.inundation.vegetated_flooding_reason ? ` ${result.inundation.vegetated_flooding_reason}` : ""}
        </p>
      </Section>

      <Section title="Observations">
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
      </Section>

      <Section title="Sensor comparison · L-band vs C-band">
        <p className="rounded-[3px] border border-dashed border-rule px-3 py-2.5 text-[12px] leading-relaxed text-ink-2">
          <span className="mr-1.5 inline-block rounded-[2px] border border-ink-3/60 px-1 text-[10.5px] font-semibold tracking-wide text-ink-3 uppercase">Unavailable</span>
          {result.sensor_comparison.reason}
        </p>
        <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
          When RCM data exists, each sensor&apos;s change map is derived on its own and compared on a common coarser grid. Raw L-band and C-band backscatter are never subtracted from each other.
        </p>
      </Section>

      <Section title="Environmental context">
        <RainfallStrip p={result.precipitation} earlier={result.earlier.date} later={result.later.date} />
      </Section>

      <Section title="Reference consistency">
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
      </Section>

      <Section title="Uncertainty & limitations">
        <p className="mb-2 text-[12.5px] leading-relaxed text-ink">
          <span className="mr-1.5 inline-block rounded-[2px] bg-marker px-1 text-[10.5px] font-bold tracking-wide text-marker-ink uppercase">Not validated</span>
          {v.statement}
        </p>
        <p className="mb-2 text-[12px] leading-relaxed text-ink-2">{u.interpretation_caveat}</p>
        <ul className="list-disc pl-4 text-[11.5px] leading-snug text-ink-3 marker:text-ink-3">
          {u.false_positive_sources.map((x) => <li key={x} className="mb-1">{x}</li>)}
        </ul>
        <p className="strip mt-3 text-[10.5px] text-ink-3">Analysis {result.id} · {result.created_at.slice(0, 19).replace("T", " ")} UTC</p>
      </Section>
    </div>
  );
}
