"use client";

import type { LngLatBounds } from "maplibre-gl";

function step(span: number) {
  const target = span / 5;
  const candidates = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 30];
  return candidates.find((c) => c >= target) ?? 30;
}

function ticks(lo: number, hi: number) {
  const s = step(hi - lo);
  const out: number[] = [];
  for (let v = Math.ceil(lo / s) * s; v <= hi; v += s) out.push(Number(v.toFixed(4)));
  return { values: out, step: s };
}

function label(v: number, axis: "lon" | "lat", s: number) {
  const d = s < 0.1 ? 2 : s < 1 ? 1 : 0;
  const hemi = axis === "lon" ? (v < 0 ? "W" : "E") : v < 0 ? "S" : "N";
  return `${Math.abs(v).toFixed(d)}°${hemi}`;
}

/** Edge ticks registering the transparency to geographic coordinates (Web Mercator ⇒ linear in lon, approximately in lat at these scales). */
export function Graticule({ bounds }: { bounds: LngLatBounds }) {
  const w = bounds.getWest(), e = bounds.getEast(), s = bounds.getSouth(), n = bounds.getNorth();
  const lon = ticks(w, e);
  const lat = ticks(s, n);
  const mercY = (la: number) => Math.log(Math.tan(Math.PI / 4 + (la * Math.PI) / 360));
  const yFrac = (la: number) => (mercY(n) - mercY(la)) / (mercY(n) - mercY(s));
  return (
    <div className="pointer-events-none absolute inset-0 z-[4]" aria-hidden>
      {lon.values.map((v) => {
        const x = ((v - w) / (e - w)) * 100;
        return (
          <div key={`x${v}`} className="absolute top-0" style={{ left: `${x}%` }}>
            <div className="h-2 w-px bg-ink/70" />
            <div className="strip mt-0.5 -translate-x-1/2 text-[10.5px] text-ink/80 [text-shadow:0_1px_2px_#000]">{label(v, "lon", lon.step)}</div>
          </div>
        );
      })}
      {lat.values.map((v) => {
        const y = yFrac(v) * 100;
        return (
          <div key={`y${v}`} className="absolute right-0 flex items-center" style={{ top: `${y}%` }}>
            <div className="strip mr-1 -translate-y-px text-[10.5px] text-ink/80 [text-shadow:0_1px_2px_#000]">{label(v, "lat", lat.step)}</div>
            <div className="h-px w-2 bg-ink/70" />
          </div>
        );
      })}
    </div>
  );
}
