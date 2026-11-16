"use client";

import { useEffect, useState } from "react";

import { api } from "@/services/api";

type Row = Awaited<ReturnType<typeof api.summary>>[number];

const day = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

/** Headline of every study area's featured analysis; a row switches the workspace to that area. */
export function AreaOverview({ current, onPick }: { current: string | null; onPick: (id: string) => void }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  useEffect(() => {
    api.summary().then(setRows).catch(() => setRows([]));
  }, []);
  if (!rows || rows.length < 2) return null;
  return (
    <details className="mt-2.5 rounded-[3px] border border-rule-soft" open>
      <summary className="flex cursor-pointer list-none items-center justify-between px-2.5 py-2 text-[12px] text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
        <span>All study areas</span>
        <span className="num text-[11px] text-ink-3">{rows.length} cases</span>
      </summary>
      <ul className="border-t border-rule-soft">
        {rows.map((r) => {
          const net = (r.water_later_km2 ?? 0) - (r.water_earlier_km2 ?? 0);
          return (
            <li key={r.area_id}>
              <button type="button" onClick={() => onPick(r.area_id)} aria-current={r.area_id === current}
                className={`block w-full border-b border-rule-soft px-2.5 py-1.5 text-left last:border-b-0 hover:bg-housing-2 ${r.area_id === current ? "bg-marker/10" : ""}`}>
                <span className={`block truncate text-[12px] ${r.area_id === current ? "text-marker" : "text-ink"}`}>{r.name}</span>
                <span className="num block text-[10.5px] text-ink-3">
                  {day(r.earlier_date)}→{day(r.later_date)} · water {net >= 0 ? "+" : "−"}{Math.abs(net).toFixed(0)} km²
                  {r.best_f1 != null ? ` · F1 ${r.best_f1.toFixed(2)} ${r.f1_reference === "optical" ? "opt" : "C"}` : ""}
                </span>
                {r.category && <span className="block text-[10.5px] text-ink-3">{r.category}</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </details>
  );
}
