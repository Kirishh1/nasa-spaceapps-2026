"use client";

import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";

import { api, type DataResource, type SourcesResponse } from "@/services/api";

const STATUS: Record<DataResource["status"], { label: string; cls: string }> = {
  used: { label: "Used", cls: "bg-marker text-marker-ink" },
  integrated: { label: "Integrated · no data returned", cls: "border border-dashed border-ink-3 text-ink-3" },
  not_used: { label: "Not used", cls: "border border-ink-3/60 text-ink-3 line-through" },
};

function Badge({ status }: { status: DataResource["status"] }) {
  const s = STATUS[status];
  return <span className={`inline-block rounded-[2px] px-1.5 py-px text-[10.5px] font-semibold tracking-wide uppercase ${s.cls}`}>{s.label}</span>;
}

/** Lists every data resource the app uses, NASA first, from the backend's single source of truth. */
export function DataSources({ analysisId, compact = false }: { analysisId?: string; compact?: boolean }) {
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    api.sources(analysisId).then(setData).catch(() => setErr(true));
  }, [analysisId]);

  if (err) return <p className="text-[12px] text-ink-3">Data-source list unavailable.</p>;
  if (!data) return null;

  const nasaUsed = data.nasa.filter((r) => r.status === "used");
  if (compact) {
    return (
      <div className="rounded-[3px] border border-rule px-3 py-2.5" aria-label="NASA data used">
        <p className="mb-1.5 text-[12px] font-semibold text-ink [font-stretch:108%]">NASA data used</p>
        <ul className="flex flex-col gap-1 text-[12px] leading-snug text-ink-2">
          {nasaUsed.map((r) => (
            <li key={r.id}>
              <span className="text-ink">{r.short_name}</span> · {r.name.split(",")[0]}
            </li>
          ))}
        </ul>
        <p className="mt-1.5 text-[11px] text-ink-3">Full list with identifiers and links under “Data sources”.</p>
      </div>
    );
  }

  const Row = ({ r }: { r: DataResource }) => (
    <li className="border-t border-rule-soft py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-[12.5px] font-semibold text-ink">{r.name}</span>
        <Badge status={r.status} />
      </div>
      <p className="mt-0.5 text-[11.5px] text-ink-3">{r.provider}</p>
      {r.identifier && <p className="num mt-0.5 text-[11px] break-all text-ink-2">{r.identifier}</p>}
      <p className="mt-1 text-[12px] leading-snug text-ink-2">{r.role}</p>
      {r.status_note && <p className="mt-1 text-[11.5px] leading-snug text-warn">{r.status_note}</p>}
      {r.links.length > 0 && (
        <p className="mt-1 flex flex-wrap gap-x-3 text-[11.5px]">
          {r.links.map((l) => (
            <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink-2 underline underline-offset-2 hover:text-ink">
              {l.label} <ExternalLink size={10} />
            </a>
          ))}
        </p>
      )}
    </li>
  );

  return (
    <div>
      <p className="label mb-1">NASA resources</p>
      <ul>{data.nasa.map((r) => <Row key={r.id} r={r} />)}</ul>
      {data.granules && (
        <div className="mt-2 mb-4">
          <p className="label mb-1">NISAR granules behind this result</p>
          <ul className="flex flex-col gap-1.5">
            {data.granules.map((g) => (
              <li key={g.id} className="text-[11px] leading-snug">
                <span className="num text-ink">{g.date}</span>{" "}
                <span className="num break-all text-ink-2">{g.id}</span>{" "}
                {g.download_url && <a href={g.download_url} target="_blank" rel="noreferrer" className="text-ink-2 underline underline-offset-2 hover:text-ink">NASA ASF download</a>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="label mt-3 mb-1">Other resources</p>
      <ul>{data.other.map((r) => <Row key={r.id} r={r} />)}</ul>
    </div>
  );
}
