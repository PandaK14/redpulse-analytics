import type { TeamOverview } from "@/lib/api";

interface KpiStripProps {
  overview: TeamOverview;
}

function Kpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex-1 min-w-[120px] rounded-xl border border-border bg-card px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${accent ? "text-accent-glow" : "text-foreground"}`}>
        {value}
      </p>
    </div>
  );
}

export function KpiStrip({ overview }: KpiStripProps) {
  if (!overview.games_played) {
    return (
      <div className="rounded-xl border border-border bg-card px-4 py-6 text-center text-sm text-muted">
        No synced games yet for this competition filter.
      </div>
    );
  }

  const netRating = overview.net_rating ?? 0;

  return (
    <div className="flex flex-wrap gap-3">
      <Kpi label="Record" value={`${overview.wins}-${overview.losses}`} />
      <Kpi
        label="Net Rating"
        value={`${netRating > 0 ? "+" : ""}${netRating.toFixed(1)}`}
        accent={netRating >= 0}
      />
      <Kpi label="ORtg" value={overview.ortg!.toFixed(1)} />
      <Kpi label="DRtg" value={overview.drtg!.toFixed(1)} />
      <Kpi label="Pace" value={overview.pace!.toFixed(1)} />
      <Kpi label="PPG" value={overview.points_for_avg!.toFixed(1)} />
      <Kpi label="Opp PPG" value={overview.points_against_avg!.toFixed(1)} />
    </div>
  );
}
