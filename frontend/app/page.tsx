"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
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
  type ShotChartResponse,
  type SyncStatus,
  type TeamGame,
  type TeamOverview,
  type TeamSplits,
} from "@/lib/api";

export default function TeamHubPage() {
  const [competition, setCompetition] = useState<CompetitionFilter>("ALL");
  const [overview, setOverview] = useState<TeamOverview | null>(null);
  const [splits, setSplits] = useState<TeamSplits | null>(null);
  const [roster, setRoster] = useState<RosterPlayer[]>([]);
  const [games, setGames] = useState<TeamGame[]>([]);
  const [onOff, setOnOff] = useState<OnOffRow[]>([]);
  const [shots, setShots] = useState<ShotChartResponse | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Some of these queries take several seconds against the full season of
  // data. React StrictMode double-invokes effects in dev, so without this
  // guard a slow first call can resolve *after* a newer one and stomp its
  // (successful) state with a stale error or stale data.
  const requestIdRef = useRef(0);

  const loadData = useCallback(async (comp: CompetitionFilter) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const [overviewData, splitsData, rosterData, gamesData, onOffData, shotsData, status] = await Promise.all([
        getTeamOverview(HAPOEL_JERUSALEM_TEAM_ID, comp),
        getTeamSplits(HAPOEL_JERUSALEM_TEAM_ID),
        getTeamRoster(HAPOEL_JERUSALEM_TEAM_ID),
        getTeamGames(HAPOEL_JERUSALEM_TEAM_ID),
        getTeamOnOff(HAPOEL_JERUSALEM_TEAM_ID),
        getTeamShots(HAPOEL_JERUSALEM_TEAM_ID, comp === "ALL" ? "WINNER_LEAGUE" : comp),
        getSyncStatus(),
      ]);
      if (requestIdRef.current !== requestId) return;
      setOverview(overviewData);
      setSplits(splitsData);
      setRoster(rosterData);
      setGames(comp === "ALL" ? gamesData : gamesData.filter((g) => g.competition_id === comp));
      setOnOff(onOffData);
      setShots(shotsData);
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
    loadData(competition);
  }, [competition, loadData]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await triggerSync();
      await loadData(competition);
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
      />

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <h1 className="mb-1 text-xl font-semibold text-foreground">Team Hub</h1>
        <p className="mb-6 text-sm text-muted">
          Hapoel Jerusalem season overview across {competition === "ALL" ? "all competitions" : competition === "WINNER_LEAGUE" ? "the Winner League" : "the EuroCup"}.
        </p>

        {error && (
          <div className="mb-6 rounded-lg border border-accent/40 bg-accent-deep/20 px-4 py-3 text-sm text-accent-glow">
            {error}
          </div>
        )}

        {loading && !overview ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          overview && (
            <div className="flex flex-col gap-6">
              <KpiStrip overview={overview} />

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <FourFactorsCard overview={overview} />
                </div>
                <GamesList games={games} />
              </div>

              {splits && <SplitMatrix splits={splits} />}

              <LineupTable teamId={HAPOEL_JERUSALEM_TEAM_ID} />

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <OnOffTable rows={onOff} />
                {shots && <ShotChart zones={shots.zones} leagueZones={shots.league_avg_zones} />}
              </div>

              <div>
                <p className="mb-3 text-sm font-semibold text-foreground">Player Performance Hub</p>
                <RosterTable roster={roster} />
              </div>
            </div>
          )
        )}
      </main>
    </>
  );
}
