"use client";

import maplibregl, { type Map as MlMap, type StyleSpecification } from "maplibre-gl";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, tileUrl, type MapLayer, type Observation, type Polygon, type StudyArea } from "@/services/api";
import { Graticule } from "./Graticule";

export type Basemap = "dark" | "optical";

export interface LayerState {
  visible: boolean;
  opacity: number;
}

export interface FrameCaption {
  side: "earlier" | "later";
  obs: Observation | null;
  pol: string;
}

interface Props {
  studyArea: StudyArea | null;
  observations: Observation[];
  selectedIds: string[];
  layers: MapLayer[];
  layerState: Record<string, LayerState>;
  layerOrder: string[];
  analysisId: string | null;
  basemap: Basemap;
  swipe: boolean;
  drawing: boolean;
  drawn: Polygon | null;
  onDrawn: (p: Polygon | null) => void;
  captions: [FrameCaption, FrameCaption];
}

const BASEMAPS: Record<Basemap, { tiles: string[]; attribution: string; maxzoom: number }> = {
  dark: {
    tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Base: Esri, HERE, Garmin, © OpenStreetMap contributors",
    maxzoom: 16,
  },
  optical: {
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Optical reference: Esri, Maxar, Earthstar Geographics",
    maxzoom: 18,
  },
};

const LABELS = ["https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"];

/** Both basemaps live in one style; switching only toggles visibility, so overlay layers are never rebuilt. */
function baseStyle(): StyleSpecification {
  const d = BASEMAPS.dark;
  const o = BASEMAPS.optical;
  return {
    version: 8,
    sources: {
      "base-dark": { type: "raster", tiles: d.tiles, tileSize: 256, attribution: d.attribution, maxzoom: d.maxzoom },
      "base-optical": { type: "raster", tiles: o.tiles, tileSize: 256, attribution: o.attribution, maxzoom: o.maxzoom },
      labels: { type: "raster", tiles: LABELS, tileSize: 256, maxzoom: 16 },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#121415" } },
      { id: "base-dark", type: "raster", source: "base-dark" },
      { id: "base-optical", type: "raster", source: "base-optical", layout: { visibility: "none" }, paint: { "raster-saturation": -0.35, "raster-brightness-max": 0.85 } },
      { id: "labels-anchor", type: "background", paint: { "background-opacity": 0 } },
      { id: "labels", type: "raster", source: "labels", paint: { "raster-opacity": 0.85 } },
    ],
  };
}

function showBasemap(map: MlMap, basemap: Basemap) {
  if (!map.getLayer("base-dark") || !map.getLayer("base-optical")) return;
  map.setLayoutProperty("base-dark", "visibility", basemap === "dark" ? "visible" : "none");
  map.setLayoutProperty("base-optical", "visibility", basemap === "optical" ? "visible" : "none");
}

const EMPTY_FC = { type: "FeatureCollection" as const, features: [] };

function ensureVectorLayers(map: MlMap) {
  if (!map.getSource("footprints")) map.addSource("footprints", { type: "geojson", data: EMPTY_FC });
  if (!map.getSource("boundary")) map.addSource("boundary", { type: "geojson", data: EMPTY_FC });
  if (!map.getSource("drawn")) map.addSource("drawn", { type: "geojson", data: EMPTY_FC });
  if (!map.getLayer("footprints-line"))
    map.addLayer({
      id: "footprints-line",
      type: "line",
      source: "footprints",
      paint: {
        "line-color": ["case", ["get", "selected"], "#f3c53a", "#8e8c86"],
        "line-width": ["case", ["get", "selected"], 1.5, 1],
        "line-dasharray": [3, 2],
        "line-opacity": ["case", ["get", "selected"], 0.9, 0.5],
      },
    });
  if (!map.getLayer("boundary-line"))
    map.addLayer({ id: "boundary-line", type: "line", source: "boundary", paint: { "line-color": "#f3c53a", "line-width": 2 } });
  if (!map.getLayer("drawn-fill"))
    map.addLayer({ id: "drawn-fill", type: "fill", source: "drawn", paint: { "fill-color": "#f3c53a", "fill-opacity": 0.08 } });
  if (!map.getLayer("drawn-line"))
    map.addLayer({ id: "drawn-line", type: "line", source: "drawn", paint: { "line-color": "#f3c53a", "line-width": 2.5, "line-dasharray": [1.5, 1] } });
}

function syncRasters(map: MlMap, layers: MapLayer[], state: Record<string, LayerState>, order: string[], only?: string) {
  const wanted = new Set(layers.map((l) => `r-${l.id}`));
  for (const l of map.getStyle().layers ?? []) {
    if (l.id.startsWith("r-") && !wanted.has(l.id)) {
      map.removeLayer(l.id);
      if (map.getSource(l.id)) map.removeSource(l.id);
    }
  }
  // bottom-most ply first; labels stay on top of every ply
  const ordered = [...order].reverse().map((id) => layers.find((l) => l.id === id)).filter(Boolean) as MapLayer[];
  for (const l of ordered) {
    const id = `r-${l.id}`;
    if (!map.getSource(id)) {
      map.addSource(id, { type: "raster", tiles: [tileUrl(l.tiles)], tileSize: 256, bounds: l.bounds, minzoom: 6, maxzoom: 15 });
    }
    if (!map.getLayer(id)) {
      map.addLayer({ id, type: "raster", source: id, paint: { "raster-resampling": l.kind === "categorical" ? "nearest" : "linear", "raster-fade-duration": 120 } }, "labels-anchor");
    } else {
      map.moveLayer(id, "labels-anchor");
    }
    const s = state[l.id] ?? { visible: false, opacity: 1 };
    const visible = only ? l.id === only : s.visible;
    map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    map.setPaintProperty(id, "raster-opacity", only ? 1 : s.opacity);
  }
}

function fmt(v: number | null | undefined, unit = "", digits = 2) {
  return v === null || v === undefined ? "no data" : `${v.toFixed(digits)}${unit}`;
}

const CLASS_NAMES: Record<number, string> = { 1: "Significant decrease", 2: "Limited change", 3: "Significant increase" };
const INUND_NAMES: Record<number, string> = { 1: "Not flagged", 2: "Potential open-water emergence", 3: "Potential flooded vegetation" };

export function LightTableMap(props: Props) {
  const { studyArea, observations, selectedIds, layers, layerState, layerOrder, basemap, swipe, drawing, drawn, onDrawn, captions } = props;
  const wrapRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const afterRef = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const after = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(0);
  const afterReady = useRef(false);
  const [split, setSplit] = useState(50);
  const [bounds, setBounds] = useState<maplibregl.LngLatBounds | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  const latest = useRef(props);
  latest.current = props;

  // create maps once
  useEffect(() => {
    if (!mainRef.current || !afterRef.current) return;
    const m = new maplibregl.Map({ container: mainRef.current, style: baseStyle(), center: [91.2, 24.95], zoom: 8, attributionControl: { compact: true }, maxPitch: 0, dragRotate: false });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    const a = new maplibregl.Map({ container: afterRef.current, style: baseStyle(), center: [91.2, 24.95], zoom: 8, interactive: false, attributionControl: false });
    const sync = () => {
      a.jumpTo({ center: m.getCenter(), zoom: m.getZoom(), bearing: m.getBearing(), pitch: m.getPitch() });
      setBounds(m.getBounds());
    };
    m.on("move", sync);
    m.on("load", () => {
      ensureVectorLayers(m);
      setBounds(m.getBounds());
      setReady((r) => r + 1);
    });
    a.on("load", () => {
      afterReady.current = true;
      setReady((r) => r + 1);
    });
    map.current = m;
    after.current = a;
    const ro = new ResizeObserver(() => {
      m.resize();
      a.resize();
      setBounds(m.getBounds());
    });
    ro.observe(mainRef.current);
    return () => {
      ro.disconnect();
      m.remove();
      a.remove();
    };
  }, []);

  // basemap swap (rebuild style, then re-add overlays)
  useEffect(() => {
    for (const m of [map.current, after.current]) if (m) showBasemap(m, basemap);
  }, [basemap, ready]);

  // footprints + boundary
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getSource("footprints")) return;
    const feats = observations
      .filter((o) => o.footprint)
      .map((o) => ({ type: "Feature" as const, geometry: o.footprint!, properties: { id: o.id, selected: selectedIds.includes(o.id) } }));
    (m.getSource("footprints") as maplibregl.GeoJSONSource).setData({ type: "FeatureCollection", features: feats });
    (m.getSource("boundary") as maplibregl.GeoJSONSource).setData(
      studyArea && studyArea.geometry.coordinates.length ? { type: "FeatureCollection", features: [{ type: "Feature", geometry: studyArea.geometry, properties: {} }] } : EMPTY_FC,
    );
  }, [observations, selectedIds, studyArea, ready]);

  // fly to the study area when it changes
  useEffect(() => {
    const m = map.current;
    if (!m || !studyArea) return;
    const [w, s, e, n] = studyArea.bbox;
    m.fitBounds([[w, s], [e, n]], { padding: 48, duration: 900 });
  }, [studyArea]);

  // drawn polygon
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getSource("drawn")) return;
    (m.getSource("drawn") as maplibregl.GeoJSONSource).setData(
      drawn ? { type: "FeatureCollection", features: [{ type: "Feature", geometry: drawn, properties: {} }] } : EMPTY_FC,
    );
  }, [drawn, ready]);

  // rasters
  useEffect(() => {
    const m = map.current;
    const a = after.current;
    if (!m || !a || !ready || !m.getLayer("labels-anchor") || !m.getSource("footprints")) return;
    if (swipe) {
      syncRasters(m, layers, layerState, layerOrder, "earlier_db");
      if (afterReady.current && a.getLayer("labels-anchor")) syncRasters(a, layers, layerState, layerOrder, "later_db");
    } else {
      syncRasters(m, layers, layerState, layerOrder);
    }
  }, [layers, layerState, layerOrder, swipe, ready]);

  // pixel inspection
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const onClick = async (ev: maplibregl.MapMouseEvent) => {
      const { analysisId: aid, drawing: isDrawing } = latest.current;
      if (!aid || isDrawing) return;
      const { lng, lat } = ev.lngLat;
      popup.current?.remove();
      const p = new maplibregl.Popup({ closeButton: true, maxWidth: "300px" })
        .setLngLat(ev.lngLat)
        .setHTML(`<div class="strip">Reading pixel…</div>`)
        .addTo(m);
      popup.current = p;
      try {
        const r = await api.pixel(aid, lng, lat);
        const v = r.values;
        const cls = v.change_class ? CLASS_NAMES[v.change_class] ?? "—" : "No data";
        const inu = v.inundation ? INUND_NAMES[v.inundation] ?? "—" : "No data";
        p.setHTML(`
          <div class="strip" style="margin-bottom:6px">${lat.toFixed(5)}°N  ${lng.toFixed(5)}°E</div>
          <table class="num" style="font-size:12px;border-collapse:collapse;width:100%">
            <tr><td style="color:var(--ink-3);padding:2px 10px 2px 0">Earlier</td><td style="text-align:right">${fmt(v.earlier_db, " dB")}</td></tr>
            <tr><td style="color:var(--ink-3);padding:2px 10px 2px 0">Later</td><td style="text-align:right">${fmt(v.later_db, " dB")}</td></tr>
            <tr><td style="color:var(--ink-3);padding:2px 10px 2px 0">ΔB</td><td style="text-align:right;font-weight:600">${fmt(v.delta_db, " dB")}</td></tr>
            ${v.jrc_occurrence !== undefined ? `<tr><td style="color:var(--ink-3);padding:2px 10px 2px 0">JRC water</td><td style="text-align:right">${v.jrc_occurrence === null ? "no data" : v.jrc_occurrence + "%"}</td></tr>` : ""}
          </table>
          <div style="margin-top:8px;font-size:12px;line-height:1.4">${cls}<br/><span style="color:var(--ink-2)">${inu}</span></div>`);
      } catch (e) {
        p.setHTML(`<div style="color:var(--error);font-size:12px">${(e as Error).message}</div>`);
      }
    };
    m.on("click", onClick);
    return () => {
      m.off("click", onClick);
    };
  }, [ready]);

  // rectangle drawing
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!drawing) {
      m.dragPan.enable();
      m.getCanvas().style.cursor = "";
      return;
    }
    m.dragPan.disable();
    m.getCanvas().style.cursor = "crosshair";
    let start: maplibregl.LngLat | null = null;
    const rect = (a: maplibregl.LngLat, b: maplibregl.LngLat): Polygon => {
      const [w, e] = [Math.min(a.lng, b.lng), Math.max(a.lng, b.lng)];
      const [s, n] = [Math.min(a.lat, b.lat), Math.max(a.lat, b.lat)];
      return { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] };
    };
    const down = (e: maplibregl.MapMouseEvent) => {
      start = e.lngLat;
    };
    const move = (e: maplibregl.MapMouseEvent) => {
      if (start) (m.getSource("drawn") as maplibregl.GeoJSONSource)?.setData({ type: "Feature", geometry: rect(start, e.lngLat), properties: {} });
    };
    const up = (e: maplibregl.MapMouseEvent) => {
      if (!start) return;
      const p = rect(start, e.lngLat);
      start = null;
      const ring = p.coordinates[0];
      const tiny = Math.abs(ring[1][0] - ring[0][0]) < 1e-4 || Math.abs(ring[2][1] - ring[1][1]) < 1e-4;
      onDrawn(tiny ? null : p);
    };
    m.on("mousedown", down);
    m.on("mousemove", move);
    m.on("mouseup", up);
    return () => {
      m.off("mousedown", down);
      m.off("mousemove", move);
      m.off("mouseup", up);
      m.dragPan.enable();
      m.getCanvas().style.cursor = "";
    };
  }, [drawing, onDrawn]);

  // swipe divider drag
  const dragging = useRef(false);
  const onPointer = useCallback((e: React.PointerEvent) => {
    if (!dragging.current || !wrapRef.current) return;
    const r = wrapRef.current.getBoundingClientRect();
    setSplit(Math.min(97, Math.max(3, ((e.clientX - r.left) / r.width) * 100)));
  }, []);

  return (
    <div className="relative flex h-full w-full flex-col">
      <FrameStrip captions={captions} swipe={swipe} split={split} position="top" />
      <div ref={wrapRef} className="lighttable relative min-h-0 flex-1 overflow-hidden rounded-[2px]" onPointerMove={onPointer} onPointerUp={() => (dragging.current = false)}>
        <div ref={mainRef} style={{ position: "absolute", inset: 0 }} aria-label="Interactive map" />
        <div
          ref={afterRef}
          style={{ position: "absolute", inset: 0, pointerEvents: "none", clipPath: swipe ? `inset(0 0 0 ${split}%)` : "inset(0 0 0 100%)", visibility: swipe ? "visible" : "hidden" }}
          aria-hidden
        />
        {swipe && (
          <div className="absolute inset-y-0 z-10" style={{ left: `${split}%` }}>
            <div className="absolute inset-y-0 -left-px w-[2px] bg-marker shadow-[0_0_10px_rgba(0,0,0,0.6)]" />
            <button
              type="button"
              aria-label="Drag to compare earlier and later observations"
              role="slider"
              aria-valuenow={Math.round(split)}
              aria-valuemin={0}
              aria-valuemax={100}
              onPointerDown={(e) => {
                dragging.current = true;
                (e.target as HTMLElement).setPointerCapture(e.pointerId);
              }}
              onPointerMove={onPointer}
              onPointerUp={() => (dragging.current = false)}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft") setSplit((s) => Math.max(3, s - 2));
                if (e.key === "ArrowRight") setSplit((s) => Math.min(97, s + 2));
              }}
              className="absolute top-1/2 -left-[17px] flex h-[34px] w-[34px] -translate-y-1/2 cursor-ew-resize items-center justify-center rounded-full border-2 border-marker bg-housing-1 shadow-[0_4px_14px_rgba(0,0,0,0.55)]"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="var(--marker)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5.5 4 2 8l3.5 4M10.5 4 14 8l-3.5 4" />
              </svg>
            </button>
          </div>
        )}
        <Fiducials />
        {bounds && <Graticule bounds={bounds} />}
      </div>
      <FrameStrip captions={captions} swipe={swipe} split={split} position="bottom" />
    </div>
  );
}

function Fiducials() {
  const mark = (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="rgba(232,230,225,0.75)" strokeWidth="1">
      <circle cx="11" cy="11" r="6" />
      <path d="M11 0v8M11 14v8M0 11h8M14 11h8" />
      <circle cx="11" cy="11" r="1" fill="rgba(232,230,225,0.9)" stroke="none" />
    </svg>
  );
  return (
    <div className="pointer-events-none absolute inset-0 z-[5]" aria-hidden>
      <div className="absolute top-3 left-3">{mark}</div>
      <div className="absolute top-3 right-3">{mark}</div>
      <div className="absolute bottom-10 left-3">{mark}</div>
      <div className="absolute right-3 bottom-10">{mark}</div>
    </div>
  );
}

function captionText(c: FrameCaption) {
  const o = c.obs;
  if (!o) return [`${c.side === "earlier" ? "Earlier" : "Later"} frame`, "not selected"];
  return [
    `${c.side === "earlier" ? "Earlier" : "Later"} · ${o.date}`,
    `${o.sensor} ${o.band}-band ${o.product_type} · ${c.pol}`,
    `Track ${String(o.track).padStart(3, "0")} ${o.pass_direction?.[0] ?? ""} · Frame ${String(o.frame).padStart(3, "0")}`,
    `${o.start_time.slice(11, 19)} UTC`,
  ];
}

function FrameStrip({ captions, swipe, split, position }: { captions: [FrameCaption, FrameCaption]; swipe: boolean; split: number; position: "top" | "bottom" }) {
  const c = position === "top" ? captions[0] : captions[1];
  if (swipe && position === "top") {
    return (
      <div className="strip relative flex h-7 items-center" aria-label="Frame captions">
        <span className="absolute truncate pr-3 text-right" style={{ right: `${100 - split}%`, maxWidth: `${split}%` }}>
          {captionText(captions[0]).slice(0, 2).join("  ·  ")}
        </span>
        <span className="absolute truncate pl-3 text-marker" style={{ left: `${split}%`, maxWidth: `${100 - split}%` }}>
          {captionText(captions[1]).slice(0, 2).join("  ·  ")}
        </span>
      </div>
    );
  }
  const parts = captionText(c);
  return (
    <div className="strip flex h-7 items-center gap-5 overflow-hidden whitespace-nowrap" aria-label={`${c.side} frame data strip`}>
      <span className={c.side === "later" ? "text-marker" : "text-ink"}>{parts[0]}</span>
      {parts.slice(1).map((p) => (
        <span key={p}>{p}</span>
      ))}
    </div>
  );
}
