import type { OnOffRow } from "@/lib/api";

function fmt(v: number | null): string {
  if (v === null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
}

export function OnOffTable({ rows }: { rows: OnOffRow[] }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-sm font-semibold text-foreground">On/Off Impact</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted">
              <th className="px-2 py-2 font-medium">Player</th>
              <th className="px-2 py-2 font-medium">Min On</th>
              <th className="px-2 py-2 font-medium">Min Off</th>
              <th className="px-2 py-2 font-medium">Net On</th>
              <th className="px-2 py-2 font-medium">Net Off</th>
              <th className="px-2 py-2 font-medium">Diff</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.player_id} className="border-b border-border/60 last:border-0 hover:bg-white/[0.02]">
                <td className="px-2 py-2.5 text-foreground">{r.name}</td>
                <td className="px-2 py-2.5 text-muted">{r.minutes_on.toFixed(1)}</td>
                <td className="px-2 py-2.5 text-muted">{r.minutes_off.toFixed(1)}</td>
                <td className="px-2 py-2.5 text-foreground">{fmt(r.net_rating_on)}</td>
                <td className="px-2 py-2.5 text-foreground">{fmt(r.net_rating_off)}</td>
                <td
                  className={`px-2 py-2.5 font-medium ${
                    r.on_off_diff === null ? "text-muted" : r.on_off_diff >= 0 ? "text-win" : "text-accent-glow"
                  }`}
                >
                  {fmt(r.on_off_diff)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
