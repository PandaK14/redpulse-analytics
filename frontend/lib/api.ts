const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const HAPOEL_JERUSALEM_TEAM_ID = "HAPOEL_JLM";

export type CompetitionFilter = "ALL" | "WINNER_LEAGUE" | "EUROCUP";

export interface FourFactors {
  efg_pct: number;
  tov_pct: number;
  orb_pct: number;
  ftr: number;
}

export interface TeamOverview {
  games_played: number;
  wins?: number;
  losses?: number;
  points_for_avg?: number;
  points_against_avg?: number;
  ortg?: number;
  drtg?: number;
  net_rating?: number;
  pace?: number;
  four_factors?: FourFactors;
  league_avg_four_factors: FourFactors;
  eurocup_avg_four_factors: FourFactors;
}

export interface RosterPlayer {
  player_id: string;
  name: string;
  position: string | null;
  jersey_number: number | null;
  games_played: number;
  mpg: number;
  ppg: number;
  rpg: number;
  apg: number;
  ts_pct: number;
  usg_pct: number;
  ast_to: number;
}

export interface TeamGame {
  game_id: string;
  competition_id: string;
  round: string;
  game_date: string;
  opponent_name: string;
  is_home: boolean;
  team_score: number;
  opponent_score: number;
  result: "W" | "L";
}

export interface TeamSplits {
  winner_league: TeamOverview;
  eurocup: TeamOverview;
}

export interface LineupRow {
  player_ids: string[];
  player_names: string[];
  minutes: number;
  possessions: number;
  ortg: number;
  drtg: number;
  net_rating: number;
  plus_minus: number;
}

export interface OnOffRow {
  player_id: string;
  name: string;
  minutes_on: number;
  minutes_off: number;
  net_rating_on: number | null;
  net_rating_off: number | null;
  on_off_diff: number | null;
}

export interface ShotZoneStat {
  zone: string;
  attempts: number;
  makes: number;
  fg_pct: number;
  volume_pct: number;
  points_per_shot: number;
}

export interface ShotChartResponse {
  zones: ShotZoneStat[];
  league_avg_zones: ShotZoneStat[] | null;
}

export interface GameLogEntry {
  game_id: string;
  game_date: string;
  opponent_name: string;
  result: "W" | "L";
  minutes_played: number;
  points: number;
  reb: number;
  assists: number;
  fg2m: number;
  fg2a: number;
  fg3m: number;
  fg3a: number;
  ftm: number;
  fta: number;
  steals: number;
  turnovers: number;
  blocks: number;
  valuation: number;
}

export interface RollingFormPoint {
  game_date: string;
  points: number;
  rolling_ppg: number;
  rolling_ts_pct: number;
}

export interface PlayerProfile {
  player_id: string;
  name: string;
  position: string | null;
  jersey_number: number | null;
  height_cm: number | null;
  team_id: string;
  games_played: number;
  mpg: number;
  ppg: number;
  rpg: number;
  apg: number;
  ts_pct: number;
  usg_pct: number;
  ast_to: number;
  game_log: GameLogEntry[];
  rolling_form: RollingFormPoint[];
}

export interface SyncStatus {
  last_sync_at: string | null;
  last_sync_status: string;
  last_sync_source: string;
  games_in_db: number;
}

export interface SyncTriggerResult {
  status: string;
  games_synced: number;
  source: string;
  message: string;
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

export function getTeamOverview(teamId: string, competition: CompetitionFilter) {
  return apiFetch<TeamOverview>(`/api/teams/${teamId}/overview?competition=${competition}`);
}

export function getTeamRoster(teamId: string) {
  return apiFetch<RosterPlayer[]>(`/api/teams/${teamId}/roster`);
}

export function getTeamGames(teamId: string) {
  return apiFetch<TeamGame[]>(`/api/teams/${teamId}/games`);
}

export function getTeamSplits(teamId: string) {
  return apiFetch<TeamSplits>(`/api/teams/${teamId}/splits`);
}

export type LineupSize = 5 | 3 | 2;

export function getTeamLineups(teamId: string, size: LineupSize, minMinutes: number) {
  return apiFetch<LineupRow[]>(`/api/teams/${teamId}/lineups?size=${size}&min_minutes=${minMinutes}`);
}

export function getTeamOnOff(teamId: string) {
  return apiFetch<OnOffRow[]>(`/api/teams/${teamId}/onoff`);
}

export function getTeamShots(teamId: string, competition: CompetitionFilter) {
  return apiFetch<ShotChartResponse>(`/api/teams/${teamId}/shots?competition=${competition}`);
}

export function getPlayerProfile(playerId: string) {
  return apiFetch<PlayerProfile>(`/api/players/${playerId}`);
}

export function getPlayerShots(playerId: string) {
  return apiFetch<ShotZoneStat[]>(`/api/players/${playerId}/shots`);
}

export function getSyncStatus() {
  return apiFetch<SyncStatus>("/api/sync/status");
}

export async function triggerSync(): Promise<SyncTriggerResult> {
  const res = await fetch(`${API_BASE_URL}/api/sync/trigger`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Sync failed: ${res.status}`);
  }
  return res.json() as Promise<SyncTriggerResult>;
}
