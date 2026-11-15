"use client";

import { ChevronRight, ExternalLink } from "lucide-react";

import type { AnalysisResult, Observation, StudyArea } from "@/services/api";
import { ChangeHistogram } from "./ChangeHistogram";
import { DataSources } from "./DataSources";
import { WaterTimeline } from "./WaterTimeline";
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
      Data: <span className="text-ink-2">NASA–ISRO NISAR L2 GCOV</span> (NASA ASF DAAC), checked against <span className="text-ink-2">NASA OPERA</span> surface-water maps.{" "}
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
  const vf = s.potential_inundation.vegetated;

  const changed = s.classes.significant_decrease.area_km2 + s.classes.significant_increase.area_km2;
  const nr = s.noise_reference;
  const w = result.water;
  const acc = v.accuracy ?? [];
  const optical = acc.find((x) => x.product === "DSWX_HLS");
  const best = optical ?? acc.find((x) => x.product === "DSWX_S1");
  const f = (x: number | null | undefined, d = 2) => (x === null || x === undefined ? "—" : x.toFixed(d));
  const fmtDate = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  const refName = (p: string) => (p === "DSWX_HLS" ? "optical (DSWx-HLS)" : "C-band radar (DSWx-S1)");
  const sc = result.sensor_comparison;

  return (
    <div>
      <h2 className="text-[20px] leading-tight font-semibold text-ink [font-stretch:104%]">{result.study_area.name}</h2>
      <p className="mt-1 text-[12.5px] text-ink-2">
        {fmtDate(result.earlier.date)} → {fmtDate(result.later.date)} {result.later.date.slice(0, 4)} · {result.days_between} days · NISAR L-band {result.config.polarization}
      </p>

      {/* the answer, stated in sentences built from the computed values */}
      {w ? (
        <p className="mt-4 text-[15px] leading-relaxed text-ink">
          Open water {w.later_km2 < w.earlier_km2 ? "shrank" : "grew"} from <span className="num">{km2(w.earlier_km2)} km²</span> to{" "}
          <span className="num">{km2(w.later_km2)} km²</span>: <span className="num text-[#d97706]">{km2(w.lost_km2)} km²</span> receded and{" "}
          <span className="num text-water">{km2(w.gained_km2)} km²</span> newly flooded.
        </p>
      ) : (
        <p className="mt-4 text-[15px] leading-relaxed text-ink">
          Backscatter fell over <span className="num text-decrease">{km2(s.classes.significant_decrease.area_km2)} km²</span> and rose over{" "}
          <span className="num text-increase">{km2(s.classes.significant_increase.area_km2)} km²</span> of the {km2(s.analyzed_area_km2)} km² basin.
        </p>
      )}

      <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] leading-snug text-ink-2">
        {best ? (
          <>
            <span className="rounded-[2px] bg-marker px-1.5 py-px text-[10.5px] font-bold tracking-wide text-marker-ink uppercase">Checked vs NASA OPERA</span>
            <span>
              The {fmtDate(best.nisar_date)} water map matches the {refName(best.product)} map from {fmtDate(best.date)} with F1 <span className="num text-ink">{f(best.open_water.f1)}</span>, IoU <span className="num text-ink">{f(best.open_water.iou)}</span>.
            </span>
          </>
        ) : (
          <>
            <span className="rounded-[2px] bg-marker px-1.5 py-px text-[10.5px] font-bold tracking-wide text-marker-ink uppercase">Not validated</span>
            {nr ? <span>{nr.observed_exceedance_percent.toFixed(1)}% of pixels changed; noise alone would explain about {nr.expected_exceedance_percent_gaussian.toFixed(1)}%.</span> : null}
          </>
        )}
      </p>

      <NasaLine />
      {storedAt && <p className="mt-2 text-[11px] text-ink-3">Stored result from {storedAt.slice(0, 16).replace("T", " ")} UTC · Run analysis to recompute it live.</p>}

      <div className="mt-5">
        {w && (
          <Fold id="fold-water" title="Water change" value={`${km2(w.lost_km2)} km² receded`}>
            <dl>
              <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-[#d97706]" aria-hidden />Water receded</span>} v={km2(w.lost_km2)} sub="km²" />
              <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-water" aria-hidden />Newly flooded</span>} v={km2(w.gained_km2)} sub="km²" />
              <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-[#1d4ed8]" aria-hidden />Water on both dates</span>} v={km2(w.persistent_km2)} sub="km²" />
              <Row k={`Open water ${fmtDate(result.earlier.date)}`} v={km2(w.earlier_km2)} sub={`km² · ${(100 * w.earlier_fraction).toFixed(0)}%`} />
              <Row k={`Open water ${fmtDate(result.later.date)}`} v={km2(w.later_km2)} sub={`km² · ${(100 * w.later_fraction).toFixed(0)}%`} />
            </dl>
            <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
              Open water = speckle-filtered HH backscatter below a threshold chosen automatically for each image (Otsu):{" "}
              <span className="num">{w.thresholds.earlier.threshold_db} dB</span> and <span className="num">{w.thresholds.later.threshold_db} dB</span>.
              Flooded vegetation can look bright, not dark, so it is not counted as open water.
            </p>
          </Fold>
        )}

        <Fold id="fold-validation" title="Validation & confidence" value={best ? `F1 ${f(best.open_water.f1)} vs ${best.product === "DSWX_HLS" ? "optical" : "C-band"}` : "Not validated"} tone={best ? "ink" : "warn"}>
          {acc.length > 0 && (
            <>
              <p className="mb-2 text-[12px] leading-relaxed text-ink-2">
                Each NISAR water map is compared pixel by pixel with an independent NASA OPERA surface-water map from within {Math.max(...acc.map((a) => a.offset_days))} day of the NISAR pass.
              </p>
              <table className="w-full text-[11.5px]">
                <thead>
                  <tr className="text-ink-3">
                    <th className="py-1 text-left font-normal">NISAR vs reference</th>
                    <th className="text-right font-normal">Precision</th><th className="text-right font-normal">Recall</th>
                    <th className="text-right font-normal">F1</th><th className="text-right font-normal">IoU</th>
                  </tr>
                </thead>
                <tbody className="num">
                  {acc.map((a) => (
                    <tr key={`${a.side}${a.product}`} className="border-t border-rule-soft">
                      <td className="py-1 font-sans text-ink-2">{fmtDate(a.nisar_date)} · {a.product === "DSWX_HLS" ? "optical" : "C-band"} {fmtDate(a.date)}</td>
                      <td className="text-right text-ink">{f(a.open_water.precision)}</td><td className="text-right text-ink">{f(a.open_water.recall)}</td>
                      <td className="text-right font-semibold text-ink">{f(a.open_water.f1)}</td><td className="text-right text-ink">{f(a.open_water.iou)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {optical?.threshold_sensitivity && (
                <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
                  Robustness: shifting the water threshold by ±3 dB keeps F1 against the optical map between{" "}
                  <span className="num text-ink-2">{f(Math.min(...optical.threshold_sensitivity.map((x) => x.f1 ?? 1)))}</span> and{" "}
                  <span className="num text-ink-2">{f(Math.max(...optical.threshold_sensitivity.map((x) => x.f1 ?? 0)))}</span>.
                </p>
              )}
              {(v.change_accuracy ?? []).filter((c) => c.change === "water_lost").map((c) => (
                <p key={c.product} className="mt-2 text-[11.5px] leading-snug text-ink-3">
                  Change check: NISAR&apos;s “water receded” map agrees with the change between the two {c.product === "DSWX_HLS" ? "optical" : "C-band"} reference maps with F1 <span className="num text-ink-2">{f(c.f1)}</span>.
                  This is weak, partly because the C-band reference itself swings between Sentinel-1 orbits (see the season chart).
                </p>
              ))}
              <p className="mt-2 text-[11.5px] leading-snug text-warn">{v.statement}</p>
            </>
          )}
          {nr && (
            <dl className="mt-3">
              <Row k="Pixels past the backscatter threshold" v={`${nr.observed_exceedance_percent.toFixed(1)}%`} />
              <Row k="Expected from noise alone" v={`${nr.expected_exceedance_percent_gaussian.toFixed(1)}%`} />
            </dl>
          )}
          <p className="mt-2 mb-1 text-[12px] leading-relaxed text-ink-2">{u.interpretation_caveat}</p>
          <details className="mt-1">
            <summary className="cursor-pointer text-[11.5px] text-ink-3 underline underline-offset-2">What else can change backscatter</summary>
            <ul className="mt-1 list-disc pl-4 text-[11.5px] leading-snug text-ink-3">{u.false_positive_sources.map((x) => <li key={x} className="mb-1">{x}</li>)}</ul>
          </details>
          {jrc && !jrc.status && jrc.caveat && <p className="mt-2 text-[11.5px] leading-snug text-ink-3">JRC historical water: {jrc.caveat}</p>}
        </Fold>

        <Fold id="fold-lband" title="L-band vs C-band" value={sc.status === "available" ? `${f(sc.stats?.overall_agreement_percent, 0)}% of cells agree` : acc.length ? "L-band sees more water" : "no C-band data"} tone={sc.status === "available" || acc.length ? "ink" : "muted"}>
          {acc.length > 0 && (
            <>
              <p className="mb-2 text-[12px] leading-relaxed text-ink-2">Open water on the same days, counted over the pixels both maps observed:</p>
              <dl>
                {acc.map((a) => (
                  <Row key={`f${a.product}${a.side}`}
                    k={`${fmtDate(a.nisar_date)} · NISAR vs ${a.product === "DSWX_HLS" ? "optical" : "C-band"} (${fmtDate(a.date)})`}
                    v={`${Math.round(100 * (a.open_water.predicted_fraction ?? 0))}% vs ${Math.round(100 * (a.open_water.reference_fraction ?? 0))}%`} />
                ))}
              </dl>
              <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
                NISAR&apos;s longer L-band wavelength agrees closely with the cloud-free optical map, while the C-band map finds far less water.
                A likely reason: in shallow haor water with emergent rice and grasses, C-band scatters off the vegetation and looks like land, whereas L-band passes through to the water surface.
                This is consistent with known wavelength behaviour but has not been proven for this scene.
              </p>
            </>
          )}
          {sc.status === "available" ? (() => {
            const rows = [...(sc.by_landcover ?? [])].filter((r) => r.cells >= 1000);
            const cOnly = [...rows].sort((a, b) => b.c_band_only_percent - a.c_band_only_percent).slice(0, 2);
            const stable = [...rows].sort((a, b) => b.agree_percent - a.agree_percent)[0];
            return (
              <>
                <p className="mt-3 mb-1 text-[12px] leading-relaxed text-ink-2">
                  Change maps from each band, on {sc.cell_size_m?.toFixed(0)} m cells (Sentinel-1 {sc.earlier?.date} → {sc.later?.date}, orbit {sc.earlier?.track}):
                  the bands agree on <span className="num text-ink">{f(sc.stats?.overall_agreement_percent, 0)}%</span> of cells.
                </p>
                <table className="mt-2 w-full text-[11.5px]">
                  <thead><tr className="text-ink-3"><th className="py-1 text-left font-normal">Land cover</th><th className="text-right font-normal">Agree</th><th className="text-right font-normal">L only</th><th className="text-right font-normal">C only</th></tr></thead>
                  <tbody className="num">
                    {rows.map((r) => (
                      <tr key={r.class} className="border-t border-rule-soft">
                        <td className="py-1 font-sans text-ink-2">{r.name}</td><td className="text-right text-ink">{r.agree_percent}%</td>
                        <td className="text-right text-ink">{r.l_band_only_percent}%</td><td className="text-right text-ink">{r.c_band_only_percent}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {cOnly.length > 0 && (
                  <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
                    The disagreement is concentrated where there is water: C-band alone reports change on{" "}
                    {cOnly.map((r, i) => <span key={r.class}>{i ? " and " : ""}<span className="num text-ink">{r.c_band_only_percent}%</span> of {r.name.toLowerCase()}</span>)},
                    while {stable?.name.toLowerCase()} agrees on <span className="num text-ink">{stable?.agree_percent}%</span>.
                    C-band (5.6 cm) is highly sensitive to centimetre-scale wind ripples on water and to emergent vegetation; L-band (24 cm) is not.
                    That fits C-band reacting to water-surface roughness and plant growth rather than to drainage alone. It is a physically consistent explanation, not a proven one.
                  </p>
                )}
                <p className="mt-2 text-[11.5px] leading-snug text-ink-3">{sc.method}</p>
              </>
            );
          })() : (
            <p className="mt-3 text-[11.5px] leading-snug text-ink-3">C-band change map: {sc.reason}</p>
          )}
        </Fold>

        <Fold id="fold-season" title="Season context" value="Jun–Nov 2026" tone="muted">
          <WaterTimeline areaId={result.study_area.id} nisar={w ? [{ date: result.earlier.date, fraction: w.earlier_fraction }, { date: result.later.date, fraction: w.later_fraction }] : []} />
        </Fold>

        <Fold title="Backscatter change" value={`${km2(changed)} km² past ±${result.config.threshold_db} dB`} tone="muted">
          <ClassBar r={result} />
          <dl className="mt-3">
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-decrease" aria-hidden />Significant decrease</span>} v={km2(s.classes.significant_decrease.area_km2)} sub={`km² · ${s.classes.significant_decrease.percent_of_valid.toFixed(1)}%`} />
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-increase" aria-hidden />Significant increase</span>} v={km2(s.classes.significant_increase.area_km2)} sub={`km² · ${s.classes.significant_increase.percent_of_valid.toFixed(1)}%`} />
            <Row k={<span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-limited" aria-hidden />Limited change</span>} v={km2(s.classes.limited_change.area_km2)} sub={`km² · ${s.classes.limited_change.percent_of_valid.toFixed(1)}%`} />
            <Row k="Flooded-vegetation candidates" v={result.inundation.vegetated_flooding_evaluated ? km2(vf.area_km2) : "not evaluated"} sub={result.inundation.vegetated_flooding_evaluated ? "km²" : undefined} />
          </dl>
          <div className="mt-4"><ChangeHistogram h={s.histogram} threshold={result.config.threshold_db} /></div>
          <p className="mt-2 text-[11.5px] leading-snug text-ink-3">
            ΔB = B<sub>later</sub> − B<sub>earlier</sub>. Flooded-vegetation candidates are increases inside tree, wetland or mangrove cover (possible double bounce).
          </p>
        </Fold>

        <Fold title="The two radar frames" value={`${fmtDate(result.earlier.date)} · ${fmtDate(result.later.date)}`} tone="muted">
          <div className="grid grid-cols-2 gap-4">
            <FrameColumn o={result.earlier} side="Earlier" />
            <FrameColumn o={result.later} side="Later" />
          </div>
          <dl className="mt-3">
            <Row k="Grid" v={result.grid.crs} />
            <Row k="Pixel spacing" v={`${result.grid.pixel_spacing_m[0]} × ${result.grid.pixel_spacing_m[1]}`} sub="m" />
            <Row k="Speckle filter" v={String(u.method.speckle_filter)} />
            <Row k="Valid pixels" v={`${s.valid_percent.toFixed(1)}%`} />
          </dl>
          <ul className="mt-2 list-disc pl-4 text-[11.5px] leading-snug text-ink-3">
            {u.alignment.map((a) => <li key={a}>{a}</li>)}
            {u.compatibility_warnings.map((cw) => <li key={cw.code} className="text-warn">{cw.message}</li>)}
          </ul>
        </Fold>

        <Fold title="Rainfall (NASA GPM)" value={result.precipitation?.status === "available" ? `${result.precipitation.between_acquisitions?.total_mm ?? "—"} mm` : "unavailable"} tone="muted">
          <RainfallStrip p={result.precipitation} earlier={result.earlier.date} later={result.later.date} />
        </Fold>

        <Fold title="Data sources" value="NASA NISAR · OPERA · CMR" tone="muted" id="data-sources">
          <DataSources analysisId={result.id} />
        </Fold>
      </div>
      <p className="strip mt-4 text-[10.5px] text-ink-3">Analysis {result.id} · {result.created_at.slice(0, 19).replace("T", " ")} UTC</p>
    </div>
  );
}
