import type { TeamOverview, TeamSplits } from "@/lib/api";

function SplitCard({ title, overview }: { title: string; overview: TeamOverview }) {
  if (!overview.games_played) {
    return (
      <div className="flex-1 rounded-xl border border-border bg-card p-4">
        <p className="mb-3 text-sm font-semibold text-foreground">{title}</p>
        <p className="text-sm text-muted">No synced games yet.</p>
      </div>
    );
  }

  const rows: { label: string; value: string }[] = [
    { label: "Record", value: `${overview.wins}-${overview.losses}` },
    { label: "Net Rating", value: `${(overview.net_rating ?? 0) > 0 ? "+" : ""}${overview.net_rating?.toFixed(1)}` },
    { label: "Off / Def Rating", value: `${overview.ortg!.toFixed(1)} / ${overview.drtg!.toFixed(1)}` },
    { label: "eFG%", value: `${(overview.four_factors!.efg_pct * 100).toFixed(1)}%` },
    { label: "Off Reb %", value: `${(overview.four_factors!.orb_pct * 100).toFixed(1)}%` },
    { label: "Turnover Rate", value: `${(overview.four_factors!.tov_pct * 100).toFixed(1)}%` },
  ];

  return (
    <div className="flex-1 rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-sm font-semibold text-foreground">{title}</p>
      <div className="flex flex-col gap-2">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between text-sm">
            <span className="text-muted">{r.label}</span>
            <span className="font-mono text-foreground">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SplitMatrix({ splits }: { splits: TeamSplits }) {
  return (
    <div>
      <p className="mb-3 text-sm font-semibold text-foreground">Competition Split</p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <SplitCard title="Winner League" overview={splits.winner_league} />
        <SplitCard title="EuroCup" overview={splits.eurocup} />
      </div>
    </div>
  );
}
