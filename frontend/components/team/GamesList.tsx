import type { TeamGame } from "@/lib/api";

export function GamesList({ games }: { games: TeamGame[] }) {
  const recent = [...games].reverse().slice(0, 8);

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-sm font-semibold text-foreground">Recent Games</p>
      <div className="flex flex-col gap-1.5">
        {recent.map((g) => (
          <div
            key={g.game_id}
            className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-3">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-md text-[11px] font-bold ${
                  g.result === "W" ? "bg-win/20 text-win" : "bg-loss/30 text-loss"
                }`}
              >
                {g.result}
              </span>
              <div>
                <p className="text-foreground">
                  {g.is_home ? "vs" : "@"} {g.opponent_name}
                </p>
                <p className="text-[11px] text-muted">
                  {g.competition_id === "WINNER_LEAGUE" ? "Winner League" : "EuroCup"} ·{" "}
                  {new Date(g.game_date).toLocaleDateString()}
                </p>
              </div>
            </div>
            <p className="font-mono text-foreground">
              {g.team_score}-{g.opponent_score}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
