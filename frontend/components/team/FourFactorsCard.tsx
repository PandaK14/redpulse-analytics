"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TeamOverview } from "@/lib/api";

interface FourFactorsCardProps {
  overview: TeamOverview;
}

const FACTOR_LABELS: { key: keyof NonNullable<TeamOverview["four_factors"]>; label: string }[] = [
  { key: "efg_pct", label: "eFG%" },
  { key: "tov_pct", label: "TOV%" },
  { key: "orb_pct", label: "ORB%" },
  { key: "ftr", label: "FTR" },
];

export function FourFactorsCard({ overview }: FourFactorsCardProps) {
  if (!overview.four_factors) return null;

  const data = FACTOR_LABELS.map(({ key, label }) => ({
    factor: label,
    "Hapoel Jerusalem": Number((overview.four_factors![key] * 100).toFixed(1)),
    "League Avg": Number((overview.league_avg_four_factors[key] * 100).toFixed(1)),
    "EuroCup Avg": Number((overview.eurocup_avg_four_factors[key] * 100).toFixed(1)),
  }));

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="mb-4 text-sm font-semibold text-foreground">Four Factors Comparison</p>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={4}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis dataKey="factor" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} unit="%" />
            <Tooltip
              contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#fafafa" }}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }} />
            <Bar dataKey="Hapoel Jerusalem" fill="#e2231a" radius={[4, 4, 0, 0]} />
            <Bar dataKey="League Avg" fill="#a1a1aa" radius={[4, 4, 0, 0]} />
            <Bar dataKey="EuroCup Avg" fill="#ff4d4d" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
