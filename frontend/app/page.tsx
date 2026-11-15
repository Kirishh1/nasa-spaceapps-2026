"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { LayerPlies } from "@/components/LayerPlies";
import { MapLegend } from "@/components/MapLegend";
import { ToolTray, type Sensor } from "@/components/ToolTray";
import { InterpretationSheet } from "@/dashboard/InterpretationSheet";
import type { Basemap, LayerState } from "@/maps/LightTableMap";
import {
  api, ApiError, type AnalysisConfig, type AnalysisRequest, type AnalysisResult, type Issue, type JobStatus, type MapLayer,
  type Observation, type Polygon, type StudyArea,
} from "@/services/api";

const LightTableMap = dynamic(() => import("@/maps/LightTableMap").then((m) => m.LightTableMap), { ssr: false });

const DEFAULT_CONFIG: AnalysisConfig = {
  frequency: "A", polarization: "HH", threshold_db: 3, speckle_filter: "lee", filter_size: 5, water_threshold_db: -18, min_region_m2: 20000,
};

type View = "change" | "delta" | "water" | "swipe";
const VIEWS: { id: View; label: string; layers: string[]; hint: string }[] = [
  { id: "change", label: "Where it changed", layers: ["change_class", "earlier_db"], hint: "Pixels whose backscatter moved more than the threshold" },
  { id: "delta", label: "How much (ΔB)", layers: ["delta_db"], hint: "Continuous change in dB, blue = darker, red = brighter" },
  { id: "water", label: "Potential water", layers: ["inundation", "later_db"], hint: "Rule-based inundation-consistent patches over the later frame" },
  { id: "swipe", label: "Before / after", layers: [], hint: "Drag the divider across the two radar frames" },
];

const PLY_ORDER = ["inundation", "change_class", "delta_db", "jrc_occurrence", "later_db", "earlier_db"];
const DEFAULT_VISIBLE = new Set(["change_class"]);

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
        <rect x="1" y="1" width="20" height="20" rx="2" stroke="var(--ink-2)" />
        <path d="M3 13h3l2-6 3 10 2.5-7 1.5 3H19" stroke="var(--marker)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-[16px] font-bold tracking-tight text-ink [font-stretch:118%]">SAR-Pulse</span>
    </div>
  );
}

export default function Workspace() {
  const [backend, setBackend] = useState<"checking" | "ok" | "down">("checking");
  const [areas, setAreas] = useState<StudyArea[]>([]);
  const [areaId, setAreaId] = useState<string | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [obsStatus, setObsStatus] = useState<"idle" | "loading" | "error">("idle");
  const [rcmReason, setRcmReason] = useState<string | null>(null);
  const [earlierId, setEarlierId] = useState<string | null>(null);
  const [laterId, setLaterId] = useState<string | null>(null);
  const [sensor, setSensor] = useState<Sensor>("NISAR");
  const [config, setConfig] = useState<AnalysisConfig>(DEFAULT_CONFIG);
  const [check, setCheck] = useState<{ ok: boolean; errors: Issue[]; warnings: Issue[] } | null>(null);
  const [checking, setChecking] = useState(false);
  const [running, setRunning] = useState(false);
  const [runErrors, setRunErrors] = useState<Issue[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [layers, setLayers] = useState<MapLayer[]>([]);
  const [layerState, setLayerState] = useState<Record<string, LayerState>>({});
  const [layerOrder, setLayerOrder] = useState<string[]>(PLY_ORDER);
  const [basemap, setBasemap] = useState<Basemap>("dark");
  const [swipe, setSwipe] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [drawn, setDrawn] = useState<Polygon | null>(null);
  const [flyBox, setFlyBox] = useState<StudyArea | null>(null);
  const poll = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [storedAt, setStoredAt] = useState<string | null>(null);
  const [view, setView] = useState<View>("change");

  const applyView = useCallback((v: View) => {
    setView(v);
    if (v === "swipe") { setSwipe(true); return; }
    setSwipe(false);
    const on = new Set(VIEWS.find((x) => x.id === v)?.layers ?? []);
    setLayerState((st) => Object.fromEntries(Object.keys(st).map((id) => [id, { ...st[id], visible: on.has(id) }])));
  }, []);

  const area = areas.find((a) => a.id === areaId) ?? null;
  const earlier = observations.find((o) => o.id === earlierId) ?? null;
  const later = observations.find((o) => o.id === laterId) ?? null;

  useEffect(() => {
    api.health().then(() => setBackend("ok")).catch(() => setBackend("down"));
    api.studyAreas().then((a) => {
      setAreas(a);
      if (a.length) setAreaId(a[0].id);
    }).catch(() => setAreas([]));
  }, []);

  useEffect(() => {
    if (!areaId) return;
    setObsStatus("loading");
    setEarlierId(null);
    setLaterId(null);
    setResult(null);
    setLayers([]);
    api.observations(areaId).then((r) => {
      setObservations(r.observations);
      setObsStatus("idle");
      // preselect the most recent processed pair from one repeat-pass stack, if any
      const proc = r.observations.filter((o) => o.ingested_layers.includes("A_HHHH"));
      for (let i = proc.length - 1; i > 0; i--) {
        const l = proc[i];
        const e = [...proc.slice(0, i)].reverse().find((o) => o.track === l.track && o.pass_direction === l.pass_direction);
        if (e) {
          setEarlierId(e.id);
          setLaterId(l.id);
          // reopen the newest stored result for this pair so the first view is the finding, not an empty sheet
          api.analyses(areaId).then((list) => {
            const hit = list.find((x) => x.earlier_id === e.id && x.later_id === l.id && !x.subset);
            if (hit) finishRef.current?.(hit.id, true);
          }).catch(() => undefined);
          break;
        }
      }
    }).catch(() => setObsStatus("error"));
    api.observations(areaId, "RCM").then((r) => setRcmReason(r.status === "available" ? null : r.reason ?? "No RCM data.")).catch(() => setRcmReason("RCM availability could not be checked."));
  }, [areaId]);

  const req = useMemo<AnalysisRequest | null>(() => (areaId && earlierId && laterId ? { study_area_id: areaId, earlier_id: earlierId, later_id: laterId, sensor, config, geometry: drawn } : null), [areaId, earlierId, laterId, sensor, config, drawn]);

  useEffect(() => {
    setRunErrors([]);
    if (!req) { setCheck(null); return; }
    setChecking(true);
    const t = setTimeout(() => {
      api.check(req).then(setCheck).catch((e: ApiError) => setCheck({ ok: false, errors: e.errors.length ? e.errors : [{ code: "error", message: e.message }], warnings: [] })).finally(() => setChecking(false));
    }, 200);
    return () => clearTimeout(t);
  }, [req]);

  // before analysis: preview the original frames on the table
  const previewLayers = useMemo<MapLayer[]>(() => {
    if (!area) return [];
    const term = `${config.frequency}_${config.polarization}${config.polarization}`;
    const mk = (o: Observation | null, id: "earlier_db" | "later_db"): MapLayer | null =>
      o && o.ingested_layers.includes(term)
        ? { id, title: `${id === "earlier_db" ? "Earlier" : "Later"} frame · ${o.date} (unfiltered)`, kind: "continuous", tiles: `/api/observations/${encodeURIComponent(o.id)}/tiles/${area.id}/${term}/{z}/{x}/{y}.png`, bounds: area.bbox, units: "dB", rescale: [-25, 0], colormap: "greys_r", description: "Original GCOV backscatter" }
        : null;
    return [mk(later, "later_db"), mk(earlier, "earlier_db")].filter(Boolean) as MapLayer[];
  }, [area, earlier, later, config.frequency, config.polarization]);

  const shownLayers = result ? layers : previewLayers;

  useEffect(() => {
    if (result) return;
    setLayerState({ later_db: { visible: true, opacity: 1 }, earlier_db: { visible: false, opacity: 1 } });
  }, [previewLayers, result]);

  const finish = useCallback(async (aid: string, stored = false) => {
    const r = (await api.analysis(aid)) as AnalysisResult;
    const l = await api.layers(aid);
    setStoredAt(stored ? r.created_at : null);
    setConfig({ ...DEFAULT_CONFIG, ...(r.config as AnalysisConfig) });
    setView("change");
    setSwipe(false);
    setResult(r);
    setLayers(l.layers);
    setLayerState(Object.fromEntries(l.layers.map((x) => [x.id, { visible: DEFAULT_VISIBLE.has(x.id) || x.id === "earlier_db", opacity: 1 }])));
    setLayerOrder(PLY_ORDER.filter((id) => l.layers.some((x) => x.id === id)));
    setRunning(false);
    setStage(null);
  }, []);
  const finishRef = useRef<typeof finish | null>(null);
  finishRef.current = finish;

  const run = useCallback(async () => {
    if (!req) return;
    setRunning(true);
    setStage("Submitting");
    setRunErrors([]);
    try {
      setStage("Processing on the server (about 20 s)");
      const started = await api.start(req);
      const id = started.id;
      if (started.status === "complete") { await finish(id); return; }
      const tick = async () => {
        try {
          const st = await api.analysis(id);
          if ((st as JobStatus).status === "running") { setStage((st as JobStatus).stage ?? "Processing"); poll.current = setTimeout(tick, 700); return; }
          if ((st as JobStatus).status === "failed") { setRunErrors((st as JobStatus).errors ?? []); setRunning(false); setStage(null); return; }
          await finish(id);
        } catch (e) {
          setRunErrors([{ code: "poll", message: (e as Error).message }]);
          setRunning(false);
          setStage(null);
        }
      };
      tick();
    } catch (e) {
      const err = e as ApiError;
      setRunErrors(err.errors?.length ? err.errors : [{ code: "start", message: err.message }]);
      setRunning(false);
      setStage(null);
    }
  }, [req, finish]);

  useEffect(() => () => { if (poll.current) clearTimeout(poll.current); }, []);

  const onDrawn = useCallback((p: Polygon | null) => { setDrawn(p); setDrawing(false); }, []);

  const mapArea = flyBox ?? area;

  return (
    <div className="flex min-h-screen flex-col bg-housing-0 lg:h-screen lg:overflow-hidden">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-rule px-4 py-2.5">
        <Wordmark />
        <p className="text-[12.5px] text-ink-2">Reads real NISAR L-band radar frames, measures how backscatter changed between two dates, and shows how far to trust the result.</p>
        <span className="ml-auto flex items-center gap-2 text-[11.5px] text-ink-3" role="status">
          <span className={`inline-block h-2 w-2 rounded-full ${backend === "ok" ? "bg-ink-2" : backend === "down" ? "bg-error" : "border border-dashed border-ink-3"}`} aria-hidden />
          {backend === "ok" ? "Backend connected" : backend === "down" ? "Backend unreachable" : "Connecting…"}
        </span>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)_372px]">
        <aside className="order-2 border-rule px-4 py-5 lg:order-1 lg:overflow-y-auto lg:border-r" aria-label="Tool tray">
          <ToolTray
            areas={areas} areaId={areaId} onArea={(id) => { setFlyBox(null); setDrawn(null); setAreaId(id); }}
            observations={observations} obsStatus={obsStatus}
            earlierId={earlierId} laterId={laterId}
            onEarlier={(id) => { setEarlierId(id); setResult(null); }} onLater={(id) => { setLaterId(id); setResult(null); }}
            sensor={sensor} onSensor={setSensor} rcmReason={rcmReason}
            config={config} onConfig={setConfig}
            check={check} checking={checking} running={running} stage={stage} runErrors={runErrors} onRun={run}
            drawing={drawing} onDrawing={setDrawing} drawn={drawn} onClearDrawn={() => setDrawn(null)}
            onFlyTo={(bbox) => setFlyBox({ id: "search", name: "search", bbox, geometry: { type: "Polygon", coordinates: [] } })}
          />
          {shownLayers.length > 0 && (
            <section className="mt-7 border-t border-rule pt-4" aria-label="Map layers">
              <h2 className="mb-1 text-[13px] font-semibold text-ink [font-stretch:108%]">Overlays on the table</h2>
              <p className="mb-2 text-[11.5px] text-ink-3">{result ? "Stacked like acetate sheets. The top of the list is the top sheet." : "Original frames, before any processing."}</p>
              <LayerPlies
                layers={shownLayers}
                order={result ? layerOrder : ["later_db", "earlier_db"].filter((id) => shownLayers.some((l) => l.id === id))}
                state={layerState}
                onState={(id, s) => setLayerState((st) => ({ ...st, [id]: s }))}
                onOrder={setLayerOrder}
                swipe={swipe}
              />
            </section>
          )}
        </aside>

        <main className="order-1 flex h-[64vh] min-h-[420px] flex-col px-3 pt-1 pb-3 lg:order-2 lg:h-auto" aria-label="Light table">
          <div className="flex flex-wrap items-center gap-2 py-1.5">
            {result ? (
              <div className="flex rounded-[3px] border border-rule p-0.5" role="radiogroup" aria-label="Map view">
                {VIEWS.map((v) => (
                  <button key={v.id} type="button" role="radio" aria-checked={view === v.id} title={v.hint} onClick={() => applyView(v.id)}
                    className={`rounded-[2px] px-2.5 py-1 text-[12px] ${view === v.id ? "bg-marker font-semibold text-marker-ink" : "text-ink-2 hover:text-ink"}`}>
                    {v.label}
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex rounded-[3px] border border-rule p-0.5" role="radiogroup" aria-label="Comparison mode">
                {[["overlay", "Later frame"], ["swipe", "Before / after"]].map(([k, label]) => {
                  const on = (k === "swipe") === swipe;
                  const disabled = k === "swipe" && !(shownLayers.some((l) => l.id === "earlier_db") && shownLayers.some((l) => l.id === "later_db"));
                  return (
                    <button key={k} type="button" role="radio" aria-checked={on} disabled={disabled} onClick={() => setSwipe(k === "swipe")}
                      className={`rounded-[2px] px-2.5 py-1 text-[12px] ${on ? "bg-housing-3 text-ink" : "text-ink-3 hover:text-ink"} disabled:cursor-not-allowed disabled:line-through disabled:opacity-60`}>
                      {label}
                    </button>
                  );
                })}
              </div>
            )}
            <div className="flex rounded-[3px] border border-rule p-0.5" role="radiogroup" aria-label="Basemap">
              {([["dark", "Graphite base"], ["optical", "Optical reference"]] as [Basemap, string][]).map(([k, label]) => (
                <button key={k} type="button" role="radio" aria-checked={basemap === k} onClick={() => setBasemap(k)}
                  className={`rounded-[2px] px-2.5 py-1 text-[12px] ${basemap === k ? "bg-housing-3 text-ink" : "text-ink-3 hover:text-ink"}`}>
                  {label}
                </button>
              ))}
            </div>
            {result && <span className="ml-auto text-[11.5px] text-ink-3">Click any pixel to read its values</span>}
          </div>
          <div className="relative min-h-0 flex-1">
            {result && <MapLegend layers={layers} state={layerState} order={layerOrder} swipe={swipe} captions={[earlier?.date, later?.date]} />}
            <LightTableMap
              studyArea={mapArea}
              observations={observations}
              selectedIds={[earlierId, laterId].filter(Boolean) as string[]}
              layers={shownLayers}
              layerState={layerState}
              layerOrder={result ? layerOrder : ["later_db", "earlier_db"]}
              analysisId={result?.id ?? null}
              basemap={basemap}
              swipe={swipe}
              drawing={drawing}
              drawn={drawn}
              onDrawn={onDrawn}
              captions={[{ side: "earlier", obs: earlier, pol: config.polarization }, { side: "later", obs: later, pol: config.polarization }]}
            />
          </div>
        </main>

        <aside className="order-3 border-rule px-5 py-5 lg:overflow-y-auto lg:border-l" aria-label="Interpretation sheet">
          <InterpretationSheet area={area} result={result} earlier={earlier} later={later} storedAt={storedAt} />
        </aside>
      </div>
    </div>
  );
}
