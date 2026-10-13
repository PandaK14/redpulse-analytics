"use client";

import { Check, ChevronDown, CircleDot, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { CompetitionFilter, SeasonInfo, SyncStatus } from "@/lib/api";

interface TopBarProps {
  competition: CompetitionFilter;
  onCompetitionChange: (value: CompetitionFilter) => void;
  onSync: () => void;
  syncing: boolean;
  syncStatus: SyncStatus | null;
  seasons: SeasonInfo[];
  season: string | null;
  onSeasonChange: (value: string) => void;
}

const COMPETITION_OPTIONS: { value: CompetitionFilter; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "WINNER_LEAGUE", label: "Winner League" },
  { value: "EUROCUP", label: "EuroCup" },
];

function SeasonPicker({
  seasons,
  season,
  onChange,
}: {
  seasons: SeasonInfo[];
  season: string | null;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = seasons.find((s) => s.id === season);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent) {
        if (e.key === "Escape") setOpen(false);
      } else if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={seasons.length === 0}
        className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs text-foreground transition-colors hover:border-muted disabled:text-muted"
      >
        {selected?.label ?? "Season"}
        <ChevronDown className={`h-3.5 w-3.5 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute right-0 z-20 mt-1.5 min-w-[11rem] overflow-hidden rounded-lg border border-border bg-card py-1 shadow-xl"
        >
          {seasons.map((s) => (
            <li key={s.id} role="option" aria-selected={s.id === season}>
              <button
                onClick={() => {
                  setOpen(false);
                  onChange(s.id);
                }}
                className="flex w-full items-center justify-between gap-4 px-3 py-2 text-left text-xs text-foreground hover:bg-white/[0.04]"
              >
                <span className="flex items-center gap-2">
                  {s.label}
                  {s.is_current && (
                    <span className="rounded bg-accent/20 px-1.5 py-0.5 text-[10px] font-medium text-accent-glow">
                      Current
                    </span>
                  )}
                </span>
                {s.id === season && <Check className="h-3.5 w-3.5 text-accent-glow" />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function TopBar({
  competition,
  onCompetitionChange,
  onSync,
  syncing,
  syncStatus,
  seasons,
  season,
  onSeasonChange,
}: TopBarProps) {
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

          <SeasonPicker seasons={seasons} season={season} onChange={onSeasonChange} />

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
