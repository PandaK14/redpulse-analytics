"""Dean Oliver's Four Factors, computed from a team's own raw totals plus
its opponent's (ORB% needs the opponent's defensive rebounds to know how
many of the team's misses were actually recoverable)."""


def four_factors(team: dict, opp: dict) -> dict:
    fga = team["fga"] or 1
    return {
        "efg_pct": round((team["fgm"] + 0.5 * team["fg3m"]) / fga, 4),
        "tov_pct": round(team["turnovers"] / (fga + 0.44 * team["fta"] + team["turnovers"] or 1), 4),
        "orb_pct": round(team["oreb"] / ((team["oreb"] + opp["dreb"]) or 1), 4),
        "ftr": round(team["fta"] / fga, 4),
    }
