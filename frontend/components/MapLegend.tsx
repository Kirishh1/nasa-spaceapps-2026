"use client";

import type { LayerState } from "@/maps/LightTableMap";
import type { MapLayer } from "@/services/api";

const RAMP: Record<string, string> = {
  greys_r: "linear-gradient(90deg,#000,#fff)",
  rdbu_r: "linear-gradient(90deg,#053061,#2166ac,#4393c3,#92c5de,#f7f7f7,#f4a582,#d6604d,#b2182b,#67001f)",
  blues: "linear-gradient(90deg,#f7fbff,#c6dbef,#6baed6,#2171b5,#08306b)",
};

/** Legend pinned on the transparency for the top-most visible data ply, so the map reads on its own. */
export function MapLegend({ layers, state, order, swipe, captions }: {
  layers: MapLayer[];
  state: Record<string, LayerState>;
  order: string[];
  swipe: boolean;
  captions: [string | undefined, string | undefined];
}) {
  const box = "pointer-events-auto absolute bottom-[64px] left-4 z-20 max-w-[270px] rounded-[3px] border border-rule bg-housing-1/92 px-3 py-2.5 shadow-[0_6px_18px_rgba(0,0,0,0.45)] backdrop-blur-[2px]";
  if (swipe) {
    return (
      <div className={box} aria-label="Map legend">
        <p className="mb-1.5 text-[12px] font-semibold text-ink">Radar backscatter, HH</p>
        <div className="h-2 rounded-[1px]" style={{ background: RAMP.greys_r }} />
        <div className="num mt-0.5 flex justify-between text-[10.5px] text-ink-3"><span>−25 dB</span><span>0 dB</span></div>
        <p className="mt-1.5 text-[11.5px] leading-snug text-ink-2">
          Left of the divider: {captions[0]}. Right: <span className="text-marker">{captions[1]}</span>. Dark = smooth surface such as calm water; bright = rough ground, vegetation or buildings.
        </p>
      </div>
    );
  }
  const top = order.map((id) => layers.find((l) => l.id === id)).find((l) => l && state[l.id]?.visible && !["earlier_db", "later_db"].includes(l.id))
    ?? order.map((id) => layers.find((l) => l.id === id)).find((l) => l && state[l.id]?.visible);
  if (!top) return null;
  if (top.kind === "rgb") {
    return (
      <div className={box} aria-label="Map legend">
        <p className="mb-1 text-[12px] font-semibold text-ink">{top.title}</p>
        <p className="text-[11.5px] leading-snug text-ink-2">Natural colour from Landsat/Sentinel-2 (NASA HLS). Open water appears dark or blue-grey; vegetation green; wet soil brown. Haze and thin cloud are possible.</p>
      </div>
    );
  }
  return (
    <div className={box} aria-label="Map legend">
      <p className="mb-1.5 text-[12px] font-semibold text-ink">{top.title}</p>
      {top.legend ? (
        <ul className="flex flex-col gap-1">
          {top.legend.filter((i) => i.color !== "transparent").map((i) => (
            <li key={i.value} className="flex items-center gap-2 text-[11.5px] text-ink-2">
              <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-[1px]" style={{ background: i.color }} aria-hidden />
              {i.label}
            </li>
          ))}
        </ul>
      ) : (
        top.rescale && top.colormap && (
          <>
            <div className="h-2 rounded-[1px]" style={{ background: RAMP[top.colormap] ?? "#555" }} />
            <div className="num mt-0.5 flex justify-between text-[10.5px] text-ink-3"><span>{top.rescale[0]} {top.units}</span><span>{top.rescale[1]} {top.units}</span></div>
            {top.id === "delta_db" && <div className="flex justify-between text-[11px] text-ink-2"><span>Got darker</span><span>Got brighter</span></div>}
          </>
        )
      )}
      <p className="mt-1.5 text-[11px] leading-snug text-ink-3">Click any pixel to read its values.</p>
    </div>
  );
}
