"""Generates a fully synthetic Hapoel Jerusalem season (Winner League + EuroCup):
competitions, teams, rosters, a schedule, and for every game a box score,
play-by-play event stream, and shot chart — all internally consistent (e.g. a
team's FGA/FGM/assists/turnovers sum exactly across its players and PBP events).

This exists purely so the API/UI can be built and tested before the real
basket.co.il / euroleaguebasketball.net scrapers are wired up. Player identities
are invented; only competition and club names are real.
"""

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.mock_data import constants as C
from app.models import Competition, Game, PlayByPlayEvent, Player, PlayerGameStats, ShotEvent, Team

RNG_SEED = 42

BLOCKS_PER_PERIOD = 8
PERIODS = 4
BLOCK_SECONDS = 75  # 10-minute FIBA period / 8 blocks
TOTAL_BLOCKS = BLOCKS_PER_PERIOD * PERIODS


# ---------------------------------------------------------------------------
# Static data: competitions, teams, rosters
# ---------------------------------------------------------------------------

def _make_roster(team_id: str, size: int = 13) -> list[Player]:
    roster = []
    for i in range(size):
        position = C.POSITIONS[i % len(C.POSITIONS)]
        height = {
            "PG": random.randint(183, 193),
            "SG": random.randint(190, 198),
            "SF": random.randint(198, 205),
            "PF": random.randint(203, 210),
            "C": random.randint(208, 218),
        }[position]
        roster.append(
            Player(
                id=f"{team_id}_P{i + 1:02d}",
                team_id=team_id,
                name=f"{random.choice(C.FIRST_NAMES)} {random.choice(C.LAST_NAMES)}",
                jersey_number=i + 1,
                position=position,
                height_cm=height,
                birth_date=None,
                nationality=None,
                image_url=None,
            )
        )
    return roster


def seed_static_data(db: Session) -> dict[str, list[Player]]:
    """Idempotent: creates competitions/teams/players only if missing. Returns
    {team_id: roster}. Hapoel Jerusalem gets a single team row/roster shared
    across both competitions (its games in EuroCup reference the same team id
    even though the team row's own competition_id is Winner League)."""
    rosters: dict[str, list[Player]] = {}

    existing_competitions = {c.id for c in db.query(Competition).all()}
    for comp_id, comp_name in (("WINNER_LEAGUE", "Winner League"), ("EUROCUP", "EuroCup")):
        if comp_id not in existing_competitions:
            db.add(Competition(id=comp_id, name=comp_name, season=C.SEASON))
    db.flush()

    existing_teams = {t.id for t in db.query(Team).all()}

    def ensure_team_and_roster(comp_id: str, team_dict: dict, is_primary: bool = False):
        if team_dict["id"] not in existing_teams:
            db.add(
                Team(
                    id=team_dict["id"],
                    competition_id=comp_id,
                    name=team_dict["name"],
                    short_name=team_dict["short_name"],
                    logo_url=None,
                    is_primary_team=is_primary,
                )
            )
            db.flush()
            roster = _make_roster(team_dict["id"])
            db.add_all(roster)
            db.flush()
            rosters[team_dict["id"]] = roster
        else:
            rosters[team_dict["id"]] = db.query(Player).filter(Player.team_id == team_dict["id"]).all()

    ensure_team_and_roster("WINNER_LEAGUE", C.HAPOEL_JERUSALEM, is_primary=True)
    for opp in C.WINNER_LEAGUE_OPPONENTS:
        ensure_team_and_roster("WINNER_LEAGUE", opp)
    for opp in C.EUROCUP_OPPONENTS:
        ensure_team_and_roster("EUROCUP", opp)

    db.commit()
    return rosters


def _build_schedule() -> list[dict]:
    games = []
    cursor = datetime(2025, 10, 5, 19, 0)
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"GAME_{counter:04d}"

    for opp in C.WINNER_LEAGUE_OPPONENTS:
        for round_no, hapoel_home in enumerate((True, False), start=1):
            home_id = C.HAPOEL_JERUSALEM["id"] if hapoel_home else opp["id"]
            away_id = opp["id"] if hapoel_home else C.HAPOEL_JERUSALEM["id"]
            games.append(
                {
                    "id": next_id(),
                    "competition_id": "WINNER_LEAGUE",
                    "round": f"Round Robin {round_no}",
                    "game_date": cursor,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                }
            )
            cursor += timedelta(days=4)

    for opp in C.EUROCUP_OPPONENTS:
        hapoel_home = random.choice([True, False])
        home_id = C.HAPOEL_JERUSALEM["id"] if hapoel_home else opp["id"]
        away_id = opp["id"] if hapoel_home else C.HAPOEL_JERUSALEM["id"]
        games.append(
            {
                "id": next_id(),
                "competition_id": "EUROCUP",
                "round": "Regular Season",
                "game_date": cursor,
                "home_team_id": home_id,
                "away_team_id": away_id,
            }
        )
        cursor += timedelta(days=7)

    games.sort(key=lambda g: g["game_date"])
    return games


# ---------------------------------------------------------------------------
# Box score simulation
# ---------------------------------------------------------------------------

def _split_weighted(total: int, weights: list[float]) -> list[int]:
    if total <= 0 or not weights or sum(weights) <= 0:
        return [0] * len(weights)
    raw = [total * w / sum(weights) for w in weights]
    floors = [int(x) for x in raw]
    remainder = total - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return floors


def _distribute_makes(attempts: list[int], total_makes: int) -> list[int]:
    total_makes = max(0, min(total_makes, sum(attempts)))
    pool = [i for i, a in enumerate(attempts) for _ in range(a)]
    random.shuffle(pool)
    makes = [0] * len(attempts)
    for i in pool[:total_makes]:
        makes[i] += 1
    return makes


def _simulate_team_totals() -> dict:
    fga = random.randint(58, 72)
    fg3a = round(fga * random.uniform(0.32, 0.45))
    fg2a = fga - fg3a
    fg2m = round(fg2a * random.uniform(0.46, 0.56))
    fg3m = round(fg3a * random.uniform(0.30, 0.40))
    fta = round(fga * random.uniform(0.18, 0.32))
    ftm = round(fta * random.uniform(0.70, 0.82))
    turnovers = random.randint(9, 16)
    points = 2 * fg2m + 3 * fg3m + ftm
    return {
        "fga": fga, "fg2a": fg2a, "fg2m": fg2m, "fg3a": fg3a, "fg3m": fg3m,
        "fta": fta, "ftm": ftm, "turnovers": turnovers, "points": points,
    }


def _break_tie(home: dict, away: dict) -> None:
    """Basketball games can't end level; nudge one team's FT total by one make."""
    if home["points"] != away["points"]:
        return
    winner = random.choice([home, away])
    if winner["ftm"] < winner["fta"]:
        winner["ftm"] += 1
    else:
        winner["fta"] += 1
        winner["ftm"] += 1
    winner["points"] = 2 * winner["fg2m"] + 3 * winner["fg3m"] + winner["ftm"]


def _reconcile_rebounds(home: dict, away: dict) -> None:
    missed_home = (home["fg2a"] - home["fg2m"]) + (home["fg3a"] - home["fg3m"])
    missed_away = (away["fg2a"] - away["fg2m"]) + (away["fg3a"] - away["fg3m"])

    home["oreb"] = round(missed_home * random.uniform(0.22, 0.34))
    away["dreb"] = missed_home - home["oreb"]

    away["oreb"] = round(missed_away * random.uniform(0.22, 0.34))
    home["dreb"] = missed_away - away["oreb"]

    home["reb"] = home["oreb"] + home["dreb"]
    away["reb"] = away["oreb"] + away["dreb"]


def _fill_secondary_stats(home: dict, away: dict) -> None:
    for team in (home, away):
        fgm = team["fg2m"] + team["fg3m"]
        team["assists"] = round(fgm * random.uniform(0.48, 0.62))
        team["steals"] = random.randint(4, 9)
        team["blocks"] = random.randint(2, 7)
        team["personal_fouls"] = random.randint(14, 20)

    home["fouls_drawn"] = max(0, away["personal_fouls"] + random.choice([-1, 0, 0, 1]))
    away["fouls_drawn"] = max(0, home["personal_fouls"] + random.choice([-1, 0, 0, 1]))


def _select_active_and_minutes(roster: list[Player], n: int = 9) -> tuple[list[Player], list[float]]:
    active = random.sample(roster, min(n, len(roster)))
    weights = [random.uniform(24, 34) if i < 5 else random.uniform(6, 16) for i in range(len(active))]
    total_w = sum(weights)
    minutes = [round(w * 200 / total_w, 1) for w in weights]
    return active, minutes


def _distribute_team_box(team_totals: dict, active: list[Player], minutes: list[float]) -> list[dict]:
    fg2a_split = _split_weighted(team_totals["fg2a"], minutes)
    fg2m_split = _distribute_makes(fg2a_split, team_totals["fg2m"])
    fg3a_split = _split_weighted(team_totals["fg3a"], minutes)
    fg3m_split = _distribute_makes(fg3a_split, team_totals["fg3m"])
    fta_split = _split_weighted(team_totals["fta"], minutes)
    ftm_split = _distribute_makes(fta_split, team_totals["ftm"])

    big_w = [m * (1.6 if p.position in ("C", "PF") else 1.0) for m, p in zip(minutes, active)]
    oreb_split = _split_weighted(team_totals["oreb"], big_w)
    dreb_split = _split_weighted(team_totals["dreb"], big_w)

    guard_w = [m * (1.4 if p.position in ("PG", "SG") else 1.0) for m, p in zip(minutes, active)]
    assists_split = _split_weighted(team_totals["assists"], guard_w)

    pg_w = [m * (1.3 if p.position == "PG" else 1.0) for m, p in zip(minutes, active)]
    turnovers_split = _split_weighted(team_totals["turnovers"], pg_w)

    perimeter_w = [m * (1.3 if p.position in ("PG", "SG") else 1.0) for m, p in zip(minutes, active)]
    steals_split = _split_weighted(team_totals["steals"], perimeter_w)

    rim_w = [m * (1.6 if p.position in ("C", "PF") else 0.6) for m, p in zip(minutes, active)]
    blocks_split = _split_weighted(team_totals["blocks"], rim_w)

    foul_w = [m * (1.2 if p.position in ("C", "PF") else 1.0) for m, p in zip(minutes, active)]
    fouls_split = _split_weighted(team_totals["personal_fouls"], foul_w)
    fouls_drawn_split = _split_weighted(team_totals["fouls_drawn"], minutes)

    rows = []
    for i, player in enumerate(active):
        fg2a, fg2m = fg2a_split[i], fg2m_split[i]
        fg3a, fg3m = fg3a_split[i], fg3m_split[i]
        fta, ftm = fta_split[i], ftm_split[i]
        rows.append(
            {
                "player": player,
                "minutes_played": minutes[i],
                "points": 2 * fg2m + 3 * fg3m + ftm,
                "fgm": fg2m + fg3m,
                "fga": fg2a + fg3a,
                "fg2m": fg2m, "fg2a": fg2a,
                "fg3m": fg3m, "fg3a": fg3a,
                "ftm": ftm, "fta": fta,
                "oreb": oreb_split[i], "dreb": dreb_split[i], "reb": oreb_split[i] + dreb_split[i],
                "assists": assists_split[i],
                "steals": steals_split[i],
                "turnovers": turnovers_split[i],
                "blocks": blocks_split[i],
                "personal_fouls": fouls_split[i],
                "fouls_drawn": fouls_drawn_split[i],
            }
        )
    return rows


def _finalize_valuation_and_plus_minus(rows: list[dict], team_margin: int) -> None:
    for r in rows:
        missed_fg = r["fga"] - r["fgm"]
        missed_ft = r["fta"] - r["ftm"]
        r["valuation"] = (
            r["points"] + r["reb"] + r["assists"] + r["steals"] + r["blocks"] + r["fouls_drawn"]
            - missed_fg - missed_ft - r["turnovers"] - r["personal_fouls"]
        )
        r["plus_minus"] = round(team_margin * (r["minutes_played"] / 40) + random.uniform(-4, 4))


# ---------------------------------------------------------------------------
# Play-by-play + shot chart simulation
# ---------------------------------------------------------------------------

def _build_lineup_blocks(rows: list[dict]) -> list[list[int]]:
    remaining = {i: r["minutes_played"] * 60 / BLOCK_SECONDS for i, r in enumerate(rows)}
    blocks = []
    for _ in range(TOTAL_BLOCKS):
        order = sorted(remaining, key=lambda i: remaining[i], reverse=True)
        on_court = order[:5]
        for i in on_court:
            remaining[i] -= 1
        blocks.append(on_court)
    return blocks


def _events_for_team(rows: list[dict], lineup_blocks: list[list[int]]) -> list[dict]:
    events = []

    def a_block_for(idx: int) -> int:
        opts = [b for b, on_court in enumerate(lineup_blocks) if idx in on_court]
        return random.choice(opts) if opts else random.randrange(TOTAL_BLOCKS)

    counts_by_kind = {
        "2PT_made": lambda r: r["fg2m"],
        "2PT_miss": lambda r: r["fg2a"] - r["fg2m"],
        "3PT_made": lambda r: r["fg3m"],
        "3PT_miss": lambda r: r["fg3a"] - r["fg3m"],
        "FT_made": lambda r: r["ftm"],
        "FT_miss": lambda r: r["fta"] - r["ftm"],
        "TURNOVER": lambda r: r["turnovers"],
        "OREB": lambda r: r["oreb"],
        "DREB": lambda r: r["dreb"],
        "FOUL": lambda r: r["personal_fouls"],
        "STEAL": lambda r: r["steals"],
        "BLOCK": lambda r: r["blocks"],
    }

    for idx, r in enumerate(rows):
        for label, count_fn in counts_by_kind.items():
            kind, _, outcome = label.partition("_")
            for _ in range(count_fn(r)):
                events.append(
                    {
                        "kind": kind,
                        "made": outcome == "made" if outcome else None,
                        "player_idx": idx,
                        "block": a_block_for(idx),
                    }
                )

    total_assists = sum(r["assists"] for r in rows)
    assist_weights = [r["assists"] + 0.1 for r in rows]
    made_field_goals = [e for e in events if e["kind"] in ("2PT", "3PT") and e["made"]]
    random.shuffle(made_field_goals)
    for e in made_field_goals[:total_assists]:
        candidates = [i for i in range(len(rows)) if i != e["player_idx"]]
        weights = [assist_weights[i] for i in candidates]
        e["assister_idx"] = random.choices(candidates, weights=weights, k=1)[0]

    for e in events:
        e["offset"] = random.uniform(0, BLOCK_SECONDS - 1)

    return events


_EVENT_TYPE_MAP = {
    "2PT": "SHOT", "3PT": "SHOT", "FT": "FREE_THROW", "TURNOVER": "TURNOVER",
    "OREB": "REBOUND", "DREB": "REBOUND", "FOUL": "FOUL", "STEAL": "STEAL", "BLOCK": "BLOCK",
}
_POINTS_BY_KIND = {"2PT": 2, "3PT": 3, "FT": 1}


def _add_player_stats(db: Session, game: Game, team_id: str, rows: list[dict]) -> None:
    for r in rows:
        player = r["player"]
        db.add(
            PlayerGameStats(
                id=f"{game.id}_STAT_{player.id}",
                game_id=game.id,
                player_id=player.id,
                team_id=team_id,
                minutes_played=r["minutes_played"],
                points=r["points"], fgm=r["fgm"], fga=r["fga"],
                fg2m=r["fg2m"], fg2a=r["fg2a"], fg3m=r["fg3m"], fg3a=r["fg3a"],
                ftm=r["ftm"], fta=r["fta"],
                oreb=r["oreb"], dreb=r["dreb"], reb=r["reb"],
                assists=r["assists"], steals=r["steals"], turnovers=r["turnovers"],
                blocks=r["blocks"], personal_fouls=r["personal_fouls"], fouls_drawn=r["fouls_drawn"],
                plus_minus=r["plus_minus"], valuation=r["valuation"],
            )
        )


def _simulate_and_persist_game(db: Session, game: Game, home_roster: list[Player], away_roster: list[Player]) -> None:
    home_active, home_minutes = _select_active_and_minutes(home_roster)
    away_active, away_minutes = _select_active_and_minutes(away_roster)

    home_totals = _simulate_team_totals()
    away_totals = _simulate_team_totals()
    _break_tie(home_totals, away_totals)
    _reconcile_rebounds(home_totals, away_totals)
    _fill_secondary_stats(home_totals, away_totals)

    home_rows = _distribute_team_box(home_totals, home_active, home_minutes)
    away_rows = _distribute_team_box(away_totals, away_active, away_minutes)

    margin = home_totals["points"] - away_totals["points"]
    _finalize_valuation_and_plus_minus(home_rows, margin)
    _finalize_valuation_and_plus_minus(away_rows, -margin)

    game.home_score = home_totals["points"]
    game.away_score = away_totals["points"]
    game.is_synced = True
    game.raw_pbp_available = True

    _add_player_stats(db, game, game.home_team_id, home_rows)
    _add_player_stats(db, game, game.away_team_id, away_rows)

    home_lineup_blocks = _build_lineup_blocks(home_rows)
    away_lineup_blocks = _build_lineup_blocks(away_rows)

    home_events = [{**e, "team": "home"} for e in _events_for_team(home_rows, home_lineup_blocks)]
    away_events = [{**e, "team": "away"} for e in _events_for_team(away_rows, away_lineup_blocks)]
    all_events = home_events + away_events
    for e in all_events:
        e["elapsed"] = e["block"] * BLOCK_SECONDS + e["offset"]
    all_events.sort(key=lambda e: e["elapsed"])

    running_home_score = 0
    running_away_score = 0
    pbp_counter = 0
    shot_counter = 0

    for e in all_events:
        is_home = e["team"] == "home"
        rows = home_rows if is_home else away_rows
        lineup_blocks = home_lineup_blocks if is_home else away_lineup_blocks
        team_id = game.home_team_id if is_home else game.away_team_id
        player = rows[e["player_idx"]]["player"]

        block_idx = min(int(e["elapsed"] // BLOCK_SECONDS), TOTAL_BLOCKS - 1)
        period = block_idx // BLOCKS_PER_PERIOD + 1
        elapsed_in_period = e["elapsed"] % (BLOCKS_PER_PERIOD * BLOCK_SECONDS)
        clock_remaining = max(0, 600 - int(elapsed_in_period))
        game_clock = f"{clock_remaining // 60:02d}:{clock_remaining % 60:02d}"

        lineup_home_ids = [home_rows[i]["player"].id for i in home_lineup_blocks[block_idx]]
        lineup_away_ids = [away_rows[i]["player"].id for i in away_lineup_blocks[block_idx]]

        secondary_player_id = None
        if e["kind"] in ("2PT", "3PT") and e.get("made") and "assister_idx" in e:
            secondary_player_id = rows[e["assister_idx"]]["player"].id

        if e.get("made"):
            delta = _POINTS_BY_KIND[e["kind"]]
            if is_home:
                running_home_score += delta
            else:
                running_away_score += delta

        pbp_counter += 1
        db.add(
            PlayByPlayEvent(
                id=f"{game.id}_PBP_{pbp_counter:04d}",
                game_id=game.id,
                period=period,
                game_clock=game_clock,
                event_type=_EVENT_TYPE_MAP[e["kind"]],
                acting_team_id=team_id,
                primary_player_id=player.id,
                secondary_player_id=secondary_player_id,
                home_score=running_home_score,
                away_score=running_away_score,
                current_lineup_home=lineup_home_ids,
                current_lineup_away=lineup_away_ids,
            )
        )

        if e["kind"] in ("2PT", "3PT"):
            zones = [z for z in C.SHOT_ZONES if z["fg_kind"] == e["kind"]]
            zone = random.choices(zones, weights=[z["weight"] for z in zones], k=1)[0]
            shot_counter += 1
            db.add(
                ShotEvent(
                    id=f"{game.id}_SHOT_{shot_counter:04d}",
                    game_id=game.id,
                    player_id=player.id,
                    team_id=team_id,
                    period=period,
                    game_clock=game_clock,
                    x_coord=round(random.uniform(*zone["x_range"]), 2),
                    y_coord=round(random.uniform(*zone["y_range"]), 2),
                    shot_type=zone["shot_type"],
                    is_made=bool(e["made"]),
                    is_assisted=secondary_player_id is not None,
                    assister_id=secondary_player_id,
                )
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_mock_season(db: Session) -> int:
    """Seeds static reference data and simulates the full season on first run.
    Returns the number of games created (0 if already synced)."""
    if db.query(Game).count() > 0:
        return 0

    random.seed(RNG_SEED)
    rosters = seed_static_data(db)
    schedule = _build_schedule()

    games_created = 0
    for g in schedule:
        game = Game(
            id=g["id"],
            competition_id=g["competition_id"],
            season=C.SEASON,
            round=g["round"],
            game_date=g["game_date"],
            home_team_id=g["home_team_id"],
            away_team_id=g["away_team_id"],
            home_score=None,
            away_score=None,
            is_synced=False,
            raw_pbp_available=False,
        )
        db.add(game)
        db.flush()

        _simulate_and_persist_game(db, game, rosters[g["home_team_id"]], rosters[g["away_team_id"]])
        games_created += 1

    db.commit()
    return games_created
