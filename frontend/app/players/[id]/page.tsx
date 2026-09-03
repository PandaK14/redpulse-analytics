"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { ShotChart } from "@/components/visual/ShotChart";
import { getPlayerProfile, getPlayerShots, type PlayerProfile, type ShotZoneStat } from "@/lib/api";

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex-1 min-w-[90px] rounded-xl border border-border bg-card px-3 py-2.5">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

export default function PlayerDetailPage() {
  const params = useParams<{ id: string }>();
  const playerId = decodeURIComponent(params.id);

  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [shots, setShots] = useState<ShotZoneStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([getPlayerProfile(playerId), getPlayerShots(playerId)])
      .then(([p, s]) => {
        if (cancelled) return;
        setProfile(p);
        setShots(s);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load player");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [playerId]);

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
      <Link href="/" className="mb-4 inline-block text-sm text-muted hover:text-foreground">
        ← Team Hub
      </Link>

      {error && (
        <div className="mb-6 rounded-lg border border-accent/40 bg-accent-deep/20 px-4 py-3 text-sm text-accent-glow">
          {error}
        </div>
      )}

      {loading && !profile ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        profile && (
          <div className="flex flex-col gap-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">
                {profile.jersey_number != null && <span className="mr-2 text-muted">#{profile.jersey_number}</span>}
                {profile.name}
              </h1>
              <p className="text-sm text-muted">
                {profile.position ?? "Position N/A"}
                {profile.height_cm ? ` · ${profile.height_cm}cm` : ""} · {profile.games_played} games played
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Kpi label="MPG" value={profile.mpg.toFixed(1)} />
              <Kpi label="PPG" value={profile.ppg.toFixed(1)} />
              <Kpi label="RPG" value={profile.rpg.toFixed(1)} />
              <Kpi label="APG" value={profile.apg.toFixed(1)} />
              <Kpi label="TS%" value={`${(profile.ts_pct * 100).toFixed(1)}%`} />
              <Kpi label="USG%" value={`${profile.usg_pct.toFixed(1)}%`} />
              <Kpi label="AST/TO" value={profile.ast_to.toFixed(2)} />
            </div>

            <div className="rounded-xl border border-border bg-card p-4">
              <p className="mb-3 text-sm font-semibold text-foreground">Rolling Form (5-game)</p>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={profile.rolling_form}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis
                      dataKey="game_date"
                      stroke="#a1a1aa"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v: string) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                    />
                    <YAxis stroke="#a1a1aa" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "#fafafa" }}
                      labelFormatter={(v: string) => new Date(v).toLocaleDateString()}
                    />
                    <Line type="monotone" dataKey="rolling_ppg" name="Rolling PPG" stroke="#e2231a" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {shots.length > 0 && <ShotChart zones={shots} title="Shot Chart" />}

            <div>
              <p className="mb-3 text-sm font-semibold text-foreground">Game Log</p>
              <div className="overflow-x-auto rounded-xl border border-border bg-card">
                <table className="w-full min-w-[820px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted">
                      <th className="px-3 py-2.5 font-medium">Date</th>
                      <th className="px-2 py-2.5 font-medium">Opponent</th>
                      <th className="px-2 py-2.5 font-medium">Res</th>
                      <th className="px-2 py-2.5 font-medium">Min</th>
                      <th className="px-2 py-2.5 font-medium">Pts</th>
                      <th className="px-2 py-2.5 font-medium">Reb</th>
                      <th className="px-2 py-2.5 font-medium">Ast</th>
                      <th className="px-2 py-2.5 font-medium">2PT</th>
                      <th className="px-2 py-2.5 font-medium">3PT</th>
                      <th className="px-2 py-2.5 font-medium">FT</th>
                      <th className="px-2 py-2.5 font-medium">Stl</th>
                      <th className="px-2 py-2.5 font-medium">Blk</th>
                      <th className="px-2 py-2.5 font-medium">TOV</th>
                      <th className="px-2 py-2.5 font-medium">Val</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...profile.game_log].reverse().map((g) => (
                      <tr key={g.game_id} className="border-b border-border/60 last:border-0 hover:bg-white/[0.02]">
                        <td className="px-3 py-2 text-muted">{new Date(g.game_date).toLocaleDateString()}</td>
                        <td className="px-2 py-2 text-foreground">{g.opponent_name}</td>
                        <td className={`px-2 py-2 font-medium ${g.result === "W" ? "text-win" : "text-loss"}`}>{g.result}</td>
                        <td className="px-2 py-2 text-muted">{g.minutes_played.toFixed(1)}</td>
                        <td className="px-2 py-2 font-medium text-foreground">{g.points}</td>
                        <td className="px-2 py-2 text-muted">{g.reb}</td>
                        <td className="px-2 py-2 text-muted">{g.assists}</td>
                        <td className="px-2 py-2 text-muted">{g.fg2m}/{g.fg2a}</td>
                        <td className="px-2 py-2 text-muted">{g.fg3m}/{g.fg3a}</td>
                        <td className="px-2 py-2 text-muted">{g.ftm}/{g.fta}</td>
                        <td className="px-2 py-2 text-muted">{g.steals}</td>
                        <td className="px-2 py-2 text-muted">{g.blocks}</td>
                        <td className="px-2 py-2 text-muted">{g.turnovers}</td>
                        <td className="px-2 py-2 text-muted">{g.valuation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )
      )}
    </main>
  );
}
