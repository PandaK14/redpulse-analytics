"use client";

import { useEffect, useState } from "react";
import { getTeamLineups, type LineupRow, type LineupSize } from "@/lib/api";

const SIZE_OPTIONS: LineupSize[] = [5, 3, 2];

export function LineupTable({ teamId }: { teamId: string }) {
  const [size, setSize] = useState<LineupSize>(5);
  const [minMinutes, setMinMinutes] = useState(10);
  const [rows, setRows] = useState<LineupRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getTeamLineups(teamId, size, minMinutes)
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [teamId, size, minMinutes]);

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-foreground">Lineup Analyzer</p>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-border bg-background p-1">
            {SIZE_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => setSize(opt)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  size === opt ? "bg-accent text-foreground" : "text-muted hover:text-foreground"
                }`}
              >
                {opt}-man
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-xs text-muted">
            Min minutes
            <input
              type="number"
              min={0}
              value={minMinutes}
              onChange={(e) => setMinMinutes(Number(e.target.value) || 0)}
              className="w-14 rounded-md border border-border bg-background px-2 py-1 text-foreground"
            />
          </label>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">No lineups meet this minutes threshold.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted">
                <th className="px-2 py-2 font-medium">Lineup</th>
                <th className="px-2 py-2 font-medium">Min</th>
                <th className="px-2 py-2 font-medium">Poss</th>
                <th className="px-2 py-2 font-medium">ORtg</th>
                <th className="px-2 py-2 font-medium">DRtg</th>
                <th className="px-2 py-2 font-medium">Net</th>
                <th className="px-2 py-2 font-medium">+/-</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.player_ids.join(",")} className="border-b border-border/60 last:border-0 hover:bg-white/[0.02]">
                  <td className="px-2 py-2.5 text-foreground">{r.player_names.join(" · ")}</td>
                  <td className="px-2 py-2.5 text-muted">{r.minutes.toFixed(1)}</td>
                  <td className="px-2 py-2.5 text-muted">{r.possessions.toFixed(1)}</td>
                  <td className="px-2 py-2.5 text-foreground">{r.ortg.toFixed(1)}</td>
                  <td className="px-2 py-2.5 text-foreground">{r.drtg.toFixed(1)}</td>
                  <td className={`px-2 py-2.5 font-medium ${r.net_rating >= 0 ? "text-win" : "text-accent-glow"}`}>
                    {r.net_rating > 0 ? "+" : ""}
                    {r.net_rating.toFixed(1)}
                  </td>
                  <td className={`px-2 py-2.5 font-mono ${r.plus_minus >= 0 ? "text-win" : "text-accent-glow"}`}>
                    {r.plus_minus > 0 ? "+" : ""}
                    {r.plus_minus}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
