"use client";

import { CircleDot, RefreshCw } from "lucide-react";
import type { CompetitionFilter, SyncStatus } from "@/lib/api";

interface TopBarProps {
  competition: CompetitionFilter;
  onCompetitionChange: (value: CompetitionFilter) => void;
  onSync: () => void;
  syncing: boolean;
  syncStatus: SyncStatus | null;
}

const COMPETITION_OPTIONS: { value: CompetitionFilter; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "WINNER_LEAGUE", label: "Winner League" },
  { value: "EUROCUP", label: "EuroCup" },
];

export function TopBar({ competition, onCompetitionChange, onSync, syncing, syncStatus }: TopBarProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent">
            <CircleDot className="h-5 w-5 text-foreground" strokeWidth={2.5} />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight text-foreground">RedPulse Analytics</p>
            <p className="text-xs text-muted">Hapoel Jerusalem</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-lg border border-border bg-card p-1">
            {COMPETITION_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => onCompetitionChange(opt.value)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  competition === opt.value
                    ? "bg-accent text-foreground"
                    : "text-muted hover:text-foreground"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <span className="rounded-md border border-border bg-card px-3 py-1.5 text-xs text-muted">
            2025-2026
          </span>

          <button
            onClick={onSync}
            disabled={syncing}
            className="flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Syncing…" : "Sync Latest Data"}
          </button>
        </div>
      </div>
      {syncStatus?.last_sync_at && (
        <div className="mx-auto max-w-6xl px-6 pb-2 text-right text-[11px] text-muted">
          Last synced {new Date(syncStatus.last_sync_at).toLocaleString()} · {syncStatus.games_in_db} games in DB
        </div>
      )}
    </header>
  );
}
