"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { LoadingNotice } from "@/components/layout/LoadingNotice";
import { KpiStrip } from "@/components/team/KpiStrip";
import { FourFactorsCard } from "@/components/team/FourFactorsCard";
import { RosterTable } from "@/components/team/RosterTable";
import { GamesList } from "@/components/team/GamesList";
import { SplitMatrix } from "@/components/team/SplitMatrix";
import { LineupTable } from "@/components/team/LineupTable";
import { OnOffTable } from "@/components/team/OnOffTable";
import { ShotChart } from "@/components/visual/ShotChart";
import {
  HAPOEL_JERUSALEM_TEAM_ID,
  getSeasons,
  getSyncStatus,
  getTeamGames,
  getTeamOnOff,
  getTeamOverview,
  getTeamRoster,
  getTeamShots,
  getTeamSplits,
  triggerSync,
  type CompetitionFilter,
  type OnOffRow,
  type RosterPlayer,
  type SeasonInfo,
  type ShotChartResponse,
  type SyncStatus,
  type TeamGame,
  type TeamOverview,
  type TeamSplits,
} from "@/lib/api";

type TabId = "overview" | "lineups" | "shots" | "roster";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "lineups", label: "Lineups & On/Off" },
  { id: "shots", label: "Shot Chart" },
  { id: "roster", label: "Roster" },
];

// The complete season is the better first impression while the current one
// is only a few rounds in; the picker's "Current" badge marks the live one.
const DEFAULT_SEASON = "2025-26";

export default function TeamHubPage() {
  const [tab, setTab] = useState<TabId>("overview");
  const [seasons, setSeasons] = useState<SeasonInfo[]>([]);
  const [season, setSeason] = useState<string | null>(null);
  const [competition, setCompetition] = useState<CompetitionFilter>("ALL");
  const [overview, setOverview] = useState<TeamOverview | null>(null);
  const [splits, setSplits] = useState<TeamSplits | null>(null);
  const [roster, setRoster] = useState<RosterPlayer[]>([]);
  const [games, setGames] = useState<TeamGame[]>([]);
  const [onOff, setOnOff] = useState<OnOffRow[]>([]);
  const [shots, setShots] = useState<ShotChartResponse | null>(null);
  const [shotCompetition, setShotCompetition] = useState<CompetitionFilter>("WINNER_LEAGUE");
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Some of these queries take several seconds against the full season of
  // data. React StrictMode double-invokes effects in dev, so without this
  // guard a slow first call can resolve *after* a newer one and stomp its
  // (successful) state with a stale error or stale data.
  const requestIdRef = useRef(0);

  const loadData = useCallback(async (comp: CompetitionFilter, seasonId: string) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const [overviewData, splitsData, rosterData, gamesData, onOffData, status] = await Promise.all([
        getTeamOverview(HAPOEL_JERUSALEM_TEAM_ID, comp, seasonId),
        getTeamSplits(HAPOEL_JERUSALEM_TEAM_ID, seasonId),
        getTeamRoster(HAPOEL_JERUSALEM_TEAM_ID, seasonId),
        getTeamGames(HAPOEL_JERUSALEM_TEAM_ID, seasonId),
        getTeamOnOff(HAPOEL_JERUSALEM_TEAM_ID, seasonId),
        getSyncStatus(),
      ]);
      // "All" shows one competition's zones (league averages only exist per
      // competition): the Winner League, unless it has no games this season.
      const shotCompetition =
        comp !== "ALL" ? comp : splitsData.winner_league.games_played ? "WINNER_LEAGUE" : "EUROCUP";
      const shotsData = await getTeamShots(HAPOEL_JERUSALEM_TEAM_ID, shotCompetition, seasonId);
      if (requestIdRef.current !== requestId) return;
      setOverview(overviewData);
      setSplits(splitsData);
      setRoster(rosterData);
      setGames(comp === "ALL" ? gamesData : gamesData.filter((g) => g.competition_id === comp));
      setOnOff(onOffData);
      setShots(shotsData);
      setShotCompetition(shotCompetition);
      setSyncStatus(status);
    } catch (err) {
      if (requestIdRef.current !== requestId) return;
      setError(
        err instanceof Error
          ? `${err.message} — is the backend running at ${process.env.NEXT_PUBLIC_API_BASE_URL}?`
          : "Failed to load data"
      );
    } finally {
      if (requestIdRef.current === requestId) setLoading(false);
    }
  }, []);

  useEffect(() => {
    getSeasons()
      .then((list) => {
        setSeasons(list);
        const fromUrl = new URLSearchParams(window.location.search).get("season");
        const initial =
          list.find((s) => s.id === fromUrl) ?? list.find((s) => s.id === DEFAULT_SEASON) ?? list[0];
        setSeason(initial?.id ?? null);
        if (!initial) setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load seasons");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (season) loadData(competition, season);
  }, [competition, season, loadData]);

  const handleSeasonChange = (next: string) => {
    if (next === season) return;
    setOverview(null);
    setSeason(next);
    const url = new URL(window.location.href);
    url.searchParams.set("season", next);
    window.history.replaceState(null, "", url);
  };

  const handleSync = async () => {
    if (!season) return;
    setSyncing(true);
    try {
      await triggerSync(season);
      setSeasons(await getSeasons());
      await loadData(competition, season);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <>
      <TopBar
        competition={competition}
        onCompetitionChange={setCompetition}
        onSync={handleSync}
        syncing={syncing}
        syncStatus={syncStatus}
        seasons={seasons}
        season={season}
        onSeasonChange={handleSeasonChange}
      />

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <h1 className="mb-1 text-xl font-semibold text-foreground">Team Hub</h1>
        <p className="mb-6 text-sm text-muted">
          Hapoel Jerusalem {seasons.find((s) => s.id === season)?.label} season overview across {competition === "ALL" ? "all competitions" : competition === "WINNER_LEAGUE" ? "the Winner League" : "the EuroCup"}.
        </p>

        {error && (
          <div className="mb-6 rounded-lg border border-accent/40 bg-accent-deep/20 px-4 py-3 text-sm text-accent-glow">
            {error}
          </div>
        )}

        {loading && !overview ? (
          <LoadingNotice />
        ) : (
          overview && (
            <div className="flex flex-col gap-6">
              <KpiStrip overview={overview} />

              <div className="flex gap-1 rounded-lg border border-border bg-card p-1 self-start">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                      tab === t.id ? "bg-accent text-foreground" : "text-muted hover:text-foreground"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {tab === "overview" && (
                <div className="flex flex-col gap-6">
                  {(overview.four_factors || games.length > 0) && (
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                      {overview.four_factors && (
                        <div className="lg:col-span-2">
                          <FourFactorsCard overview={overview} />
                        </div>
                      )}
                      {games.length > 0 && <GamesList games={games} />}
                    </div>
                  )}
                  {splits && <SplitMatrix splits={splits} />}
                </div>
              )}

              {tab === "lineups" && (
                <div className="flex flex-col gap-6">
                  <LineupTable teamId={HAPOEL_JERUSALEM_TEAM_ID} season={season!} />
                  <OnOffTable rows={onOff} />
                </div>
              )}

              {tab === "shots" && shots && (
                <ShotChart
                  zones={shots.zones}
                  leagueZones={shots.league_avg_zones}
                  title={`Shot Chart · ${shotCompetition === "EUROCUP" ? "EuroCup" : "Winner League"}`}
                />
              )}

              {tab === "roster" && (
                <div>
                  <p className="mb-3 text-sm font-semibold text-foreground">Player Performance Hub</p>
                  <RosterTable roster={roster} season={season!} />
                </div>
              )}
            </div>
          )
        )}
      </main>
    </>
  );
}
