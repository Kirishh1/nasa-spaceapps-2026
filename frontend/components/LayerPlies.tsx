"use client";

import { ChevronDown, ChevronUp, Eye, EyeOff } from "lucide-react";

import type { LayerState } from "@/maps/LightTableMap";
import type { MapLayer } from "@/services/api";

const RAMP: Record<string, string> = {
  greys_r: "linear-gradient(90deg,#000,#fff)",
  rdbu_r: "linear-gradient(90deg,#053061,#2166ac,#4393c3,#92c5de,#f7f7f7,#f4a582,#d6604d,#b2182b,#67001f)",
  blues: "linear-gradient(90deg,#f7fbff,#c6dbef,#6baed6,#2171b5,#08306b)",
};

function Ramp({ l }: { l: MapLayer }) {
  if (!l.rescale || !l.colormap) return null;
  return (
    <div className="mt-1.5">
      <div className="h-2 rounded-[1px]" style={{ background: RAMP[l.colormap] ?? "#555" }} />
      <div className="num mt-0.5 flex justify-between text-[10px] text-ink-3">
        <span>{l.rescale[0]} {l.units}</span>
        {l.id === "delta_db" && <span>0</span>}
        <span>{l.rescale[1]} {l.units}</span>
      </div>
      {l.id === "delta_db" && (
        <div className="flex justify-between text-[10.5px] text-ink-2">
          <span>Decrease</span>
          <span>Increase</span>
        </div>
      )}
    </div>
  );
}

function Swatches({ l }: { l: MapLayer }) {
  if (!l.legend) return null;
  return (
    <ul className="mt-1.5 flex flex-col gap-1">
      {l.legend.map((i) => (
        <li key={i.value} className="flex items-start gap-2 text-[11.5px] leading-tight text-ink-2">
          <span
            className="mt-[2px] inline-block h-2.5 w-2.5 shrink-0 rounded-[1px]"
            style={i.color === "transparent" ? { border: "1px dashed var(--ink-3)" } : { background: i.color }}
            aria-hidden
          />
          <span>
            <span className="text-ink">{i.label}</span>
            {i.description && <span className="text-ink-3"> · {i.description}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function LayerPlies({ layers, order, state, onState, onOrder, swipe }: {
  layers: MapLayer[];
  order: string[];
  state: Record<string, LayerState>;
  onState: (id: string, s: LayerState) => void;
  onOrder: (o: string[]) => void;
  swipe: boolean;
}) {
  const move = (id: string, d: -1 | 1) => {
    const i = order.indexOf(id);
    const j = i + d;
    if (j < 0 || j >= order.length) return;
    const o = [...order];
    [o[i], o[j]] = [o[j], o[i]];
    onOrder(o);
  };
  const byId = Object.fromEntries(layers.map((l) => [l.id, l]));
  return (
    <div>
      {swipe && <p className="mb-2 text-[11.5px] leading-snug text-ink-3">Swipe mode shows the earlier frame left of the divider and the later frame right of it. The other plies are hidden.</p>}
      <ol className="flex flex-col" aria-label="Map layers, top first">
        {order.map((id, idx) => {
          const l = byId[id];
          if (!l) return null;
          const s = state[id] ?? { visible: false, opacity: 1 };
          return (
            <li key={id} className={`relative border-t border-rule-soft py-2.5 ${swipe ? "opacity-50" : ""}`}>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  aria-pressed={s.visible}
                  aria-label={`${s.visible ? "Hide" : "Show"} ${l.title}`}
                  disabled={swipe}
                  onClick={() => onState(id, { ...s, visible: !s.visible })}
                  className={`flex h-6 w-6 items-center justify-center rounded-[3px] border ${s.visible ? "border-marker text-marker" : "border-dashed border-ink-3 text-ink-3"}`}
                >
                  {s.visible ? <Eye size={13} /> : <EyeOff size={13} />}
                </button>
                <span className={`min-w-0 flex-1 truncate text-[12.5px] ${s.visible ? "text-ink" : "text-ink-3"}`}>{l.title}</span>
                <span className="flex">
                  <button type="button" aria-label={`Move ${l.title} up`} disabled={idx === 0} onClick={() => move(id, -1)} className="p-0.5 text-ink-3 hover:text-ink disabled:opacity-30"><ChevronUp size={14} /></button>
                  <button type="button" aria-label={`Move ${l.title} down`} disabled={idx === order.length - 1} onClick={() => move(id, 1)} className="p-0.5 text-ink-3 hover:text-ink disabled:opacity-30"><ChevronDown size={14} /></button>
                </span>
              </div>
              {s.visible && !swipe && (
                <div className="mt-1.5 pl-8">
                  <label className="flex items-center gap-2 text-[11px] text-ink-3">
                    <span className="sr-only">{l.title} opacity</span>
                    <input type="range" min={0} max={1} step={0.05} value={s.opacity} onChange={(e) => onState(id, { ...s, opacity: Number(e.target.value) })} className="flex-1" aria-label={`${l.title} opacity`} />
                    <span className="num w-8 text-right">{Math.round(s.opacity * 100)}%</span>
                  </label>
                  <Ramp l={l} />
                  <Swatches l={l} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
