import type { ShotZoneStat } from "@/lib/api";

interface ShotChartProps {
  zones: ShotZoneStat[];
  leagueZones?: ShotZoneStat[] | null;
  title?: string;
}

function zoneColor(diff: number | null): string {
  if (diff === null) return "#52525b";
  if (diff > 0.15) return "#dc2626";
  if (diff > 0.05) return "#f87171";
  if (diff > -0.05) return "#71717a";
  if (diff > -0.15) return "#60a5fa";
  return "#2563eb";
}

export function ShotChart({ zones, leagueZones, title }: ShotChartProps) {
  const byZone = Object.fromEntries(zones.map((z) => [z.zone, z]));
  const leagueByZone = Object.fromEntries((leagueZones ?? []).map((z) => [z.zone, z]));

  const diffFor = (zoneName: string): number | null => {
    const league = leagueByZone[zoneName];
    const zone = byZone[zoneName];
    if (!league || !zone || zone.attempts === 0) return null;
    return zone.points_per_shot - league.points_per_shot;
  };

  const colors = {
    rim: zoneColor(diffFor("Rim")),
    paint: zoneColor(diffFor("Paint")),
    midRange: zoneColor(diffFor("Mid-Range")),
    cornerLeft: zoneColor(diffFor("Corner-3")),
    cornerRight: zoneColor(diffFor("Corner-3")),
    aboveBreak: zoneColor(diffFor("Above-the-Break-3")),
  };

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-sm font-semibold text-foreground">{title ?? "Shot Chart"}</p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,260px)_1fr]">
        <svg viewBox="0 0 500 470" className="mx-auto w-full max-w-[260px]">
          {/* base layer: above-the-break-3 covers the whole court */}
          <rect x="10" y="10" width="480" height="440" fill={colors.aboveBreak} opacity="0.5" />
          {/* corner-3 strips */}
          <rect x="10" y="10" width="30" height="185" fill={colors.cornerLeft} opacity="0.55" />
          <rect x="460" y="10" width="30" height="185" fill={colors.cornerRight} opacity="0.55" />
          {/* mid-range band */}
          <rect x="40" y="10" width="420" height="200" fill={colors.midRange} opacity="0.55" />
          {/* paint */}
          <rect x="170" y="10" width="160" height="170" fill={colors.paint} opacity="0.6" />
          {/* rim */}
          <circle cx="250" cy="60" r="45" fill={colors.rim} opacity="0.65" />

          {/* court line overlay (drawn on top, stroke only) */}
          <rect x="10" y="10" width="480" height="440" fill="none" stroke="#3f3f46" strokeWidth="2" />
          <rect x="170" y="10" width="160" height="170" fill="none" stroke="#3f3f46" strokeWidth="2" />
          <circle cx="250" cy="180" r="60" fill="none" stroke="#3f3f46" strokeWidth="2" />
          <path d="M 40 10 L 40 195 A 250 250 0 0 0 460 195 L 460 10" fill="none" stroke="#3f3f46" strokeWidth="2" />
          <line x1="220" y1="30" x2="280" y2="30" stroke="#a1a1aa" strokeWidth="3" />
          <circle cx="250" cy="40" r="8" fill="none" stroke="#a1a1aa" strokeWidth="2" />
        </svg>

        <div className="flex flex-col justify-center gap-1.5">
          {zones.map((z) => (
            <div key={z.zone} className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-1.5 text-sm">
              <span className="flex items-center gap-2 text-foreground">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: zoneColor(diffFor(z.zone)) }} />
                {z.zone}
              </span>
              <span className="font-mono text-xs text-muted">
                {z.attempts} att · {(z.volume_pct * 100).toFixed(0)}% vol · {(z.fg_pct * 100).toFixed(1)}% FG · {z.points_per_shot.toFixed(2)} PPS
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
