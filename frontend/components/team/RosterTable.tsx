"use client";

import { useMemo, useState } from "react";
import type { RosterPlayer } from "@/lib/api";

type SortKey = keyof Pick<
  RosterPlayer,
  "ppg" | "rpg" | "apg" | "ts_pct" | "usg_pct" | "ast_to" | "mpg"
>;

const COLUMNS: { key: SortKey; label: string; format: (v: number) => string }[] = [
  { key: "mpg", label: "MPG", format: (v) => v.toFixed(1) },
  { key: "ppg", label: "PPG", format: (v) => v.toFixed(1) },
  { key: "rpg", label: "RPG", format: (v) => v.toFixed(1) },
  { key: "apg", label: "APG", format: (v) => v.toFixed(1) },
  { key: "ts_pct", label: "TS%", format: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "usg_pct", label: "USG%", format: (v) => `${v.toFixed(1)}%` },
  { key: "ast_to", label: "AST/TO", format: (v) => v.toFixed(2) },
];

export function RosterTable({ roster }: { roster: RosterPlayer[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("ppg");

  const sorted = useMemo(
    () => [...roster].sort((a, b) => b[sortKey] - a[sortKey]),
    [roster, sortKey]
  );

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted">
            <th className="px-4 py-3 font-medium">Player</th>
            <th className="px-2 py-3 font-medium">Pos</th>
            <th className="px-2 py-3 font-medium">GP</th>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => setSortKey(col.key)}
                className={`cursor-pointer px-2 py-3 font-medium hover:text-foreground ${
                  sortKey === col.key ? "text-accent-glow" : ""
                }`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((p) => (
            <tr key={p.player_id} className="border-b border-border/60 last:border-0 hover:bg-white/[0.02]">
              <td className="px-4 py-2.5 font-medium text-foreground">
                {p.jersey_number != null && (
                  <span className="mr-2 text-muted">#{p.jersey_number}</span>
                )}
                {p.name}
              </td>
              <td className="px-2 py-2.5 text-muted">{p.position ?? "-"}</td>
              <td className="px-2 py-2.5 text-muted">{p.games_played}</td>
              {COLUMNS.map((col) => (
                <td key={col.key} className="px-2 py-2.5 text-foreground">
                  {col.format(p[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
