"""Shared helpers for the real scrapers: team/player identity resolution.

Both basket.co.il and the Euroleague API mint their own numeric team/player
ids that are NOT stable across seasons (basket.co.il especially — team ids
reset every year). We instead key our own `teams`/`players` rows on a
source-independent slug so re-syncing a later season lands on the same rows.
"""

import difflib
import hashlib
import re
import unicodedata
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Competition, PlayByPlayEvent, Player, ShotEvent, Team


def discard_pbp_if_score_mismatch(
    db: Session, game_id: str,
    computed_home: float, computed_away: float,
    actual_home: int, actual_away: int,
    tolerance: int = 2,
) -> bool:
    """Some source games are missing one or more players from the live
    tracking feed entirely (a genuine third-party data gap, not a parsing
    bug — their stats never appear anywhere in the action log). That leaves
    play-by-play/shot data self-consistent in shape but silently short on
    points, which would corrupt lineup/on-off analytics. Cross-checking the
    reconstructed running score against the box-score-confirmed final score
    catches it: on mismatch, discard the PBP/shot rows just added for this
    game rather than keep a plausible-looking but wrong dataset.

    Returns True if discarded (caller should treat PBP as unavailable).
    """
    if abs(computed_home - actual_home) <= tolerance and abs(computed_away - actual_away) <= tolerance:
        return False
    db.execute(delete(PlayByPlayEvent).where(PlayByPlayEvent.game_id == game_id))
    db.execute(delete(ShotEvent).where(ShotEvent.game_id == game_id))
    return True


def find_or_create_competition(db: Session, competition_id: str, name: str, season: str) -> Competition:
    competition = db.get(Competition, competition_id)
    if competition is None:
        competition = Competition(id=competition_id, name=name, season=season)
        db.add(competition)
        db.flush()
    elif competition.season != season:
        competition.season = season
    return competition


def stable_hash(text: str, length: int = 8) -> str:
    """Deterministic short hash (Python's built-in hash() is randomized per
    process via PYTHONHASHSEED, so it can't be used for ids that must stay
    stable across scraper runs)."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:length]

# (required substrings, our team_id, canonical English name). Sponsor
# prefixes change season to season (e.g. "הפועל בנק יהב ירושלים" vs
# "הפועל מידטאון י-ם"), so we match on the stable core tokens rather than
# the full name.
HEBREW_TEAM_SLUGS: list[tuple[tuple[str, ...], str, str]] = [
    (("הפועל", "ירושלים"), "HAPOEL_JLM", "Hapoel Jerusalem"),
    (("הפועל", "י-ם"), "HAPOEL_JLM", "Hapoel Jerusalem"),
    (("מכבי", 'ת"א'), "MACCABI_TA", "Maccabi Tel Aviv"),
    (("מכבי", "תל אביב"), "MACCABI_TA", "Maccabi Tel Aviv"),
    (("הפועל", 'ת"א'), "HAPOEL_TA", "Hapoel Tel Aviv"),
    (("הפועל", "תל אביב"), "HAPOEL_TA", "Hapoel Tel Aviv"),
    (("הרצליה",), "BNEI_HERZLIYA", "Bnei Herzliya"),
    (("הפועל", "חולון"), "HAPOEL_HOLON", "Hapoel Holon"),
    (("הפועל", "העמק"), "HAPOEL_HAEMEK", "Hapoel Haemek"),
    (("ראשון לציון",), "RISHON_LEZION", "Rishon LeZion"),
    (("הפועל", 'ב"ש'), "HAPOEL_BEER_SHEVA", "Hapoel Beer Sheva"),
    (("הפועל", "באר שבע"), "HAPOEL_BEER_SHEVA", "Hapoel Beer Sheva"),
    (("מכבי", "רמת גן"), "MACCABI_RAMAT_GAN", "Maccabi Ramat Gan"),
    (("קריית אתא",), "KIRYAT_ATA", "Ironi Kiryat Ata"),
    (("נס ציונה",), "NESS_ZIONA", "Ness Ziona"),
    (("גליל עליון",), "GALIL_ELYON", "Galil Elyon"),
    (("הפועל", "אילת"), "HAPOEL_EILAT", "Hapoel Eilat"),
    (("מכבי", "אשדוד"), "MACCABI_ASHDOD", "Maccabi Ashdod"),
    (("אליצור", "נתניה"), "ELITZUR_NETANYA", "Elitzur Netanya"),
    (("מכבי", "רעננה"), "MACCABI_RAANANA", "Maccabi Raanana"),
]


def slug_for_hebrew_team(name: str) -> tuple[str, str]:
    """Returns (team_id, canonical_english_name) for a Hebrew team name.
    Falls back to a deterministic generated id for names we don't recognize
    (a newly promoted club, a renamed sponsor entity, etc.)."""
    for required, slug, english in HEBREW_TEAM_SLUGS:
        if all(token in name for token in required):
            return slug, english
    return f"WL_{stable_hash(name)}", name


def normalize_person_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z]", "", ascii_name.upper())


def find_or_create_team(
    db: Session,
    team_id: str,
    name: str,
    short_name: str,
    competition_id: str,
    is_primary: bool = False,
) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        team = Team(
            id=team_id,
            competition_id=competition_id,
            name=name,
            short_name=short_name[:20],
            is_primary_team=is_primary,
        )
        db.add(team)
        db.flush()
    return team


def find_or_create_player(
    db: Session,
    team_id: str,
    external_id: str,
    name: str,
    jersey: Optional[int] = None,
    position: Optional[str] = None,
    height_cm: Optional[int] = None,
) -> Player:
    """Upserts a player by external_id. For Hapoel Jerusalem specifically,
    also tries to match an existing row from a *different* source/script for
    the same human — e.g. a Hebrew box-score-only "WL_" row, a segevstats
    "WL_" row with a Latin name, and an "EL_" EuroCup row would otherwise all
    become separate players for e.g. Jared Harper."""
    player = db.get(Player, external_id)
    if player is not None:
        return player

    if team_id == "HAPOEL_JLM":
        existing = db.query(Player).filter(Player.team_id == team_id).all()
        match = None

        # Latin-script name match (segevstats WL_ <-> EuroCup EL_). A Hebrew
        # name ASCII-folds to near-nothing via NFKD, so this only fires when
        # both sides are already Latin.
        normalized = normalize_person_name(name)
        if len(normalized) >= 4:
            for candidate in existing:
                if normalize_person_name(candidate.name) == normalized:
                    match = candidate
                    break

        # Jersey-number match: bridges a Hebrew box-score-only row to its
        # Latin-named counterpart from segevstats/EuroCup. Scoped to our own
        # roster only, where jersey reuse mid-season hasn't been observed
        # (unlike e.g. a merged franchise on another team).
        if match is None and jersey is not None:
            for candidate in existing:
                if candidate.jersey_number == jersey:
                    match = candidate
                    break

        # Fuzzy fallback: one source can simply misspell a name (e.g. the
        # EuroCup feed's "Isaiah Mobley" vs. box-score-sourced "Isahiah
        # Mobley" — a single-letter transposition/insertion), which fails
        # both the exact-name and jersey match above and would otherwise
        # mint a second, silently duplicate identity for the same person.
        # A small roster (~20 players) makes near-identical names extremely
        # unlikely to refer to two different people, so a high similarity
        # ratio is safe here.
        if match is None and len(normalized) >= 4:
            best_ratio, best_candidate = 0.0, None
            for candidate in existing:
                candidate_normalized = normalize_person_name(candidate.name)
                if len(candidate_normalized) < 4:
                    continue
                ratio = difflib.SequenceMatcher(None, normalized, candidate_normalized).ratio()
                if ratio > best_ratio:
                    best_ratio, best_candidate = ratio, candidate
            if best_ratio >= 0.85:
                match = best_candidate

        if match is not None:
            # Prefer a Latin name/enrichment over whatever's already stored
            # (a Hebrew box-score row created before its segevstats/EuroCup
            # counterpart synced would otherwise keep the Hebrew name forever).
            if len(normalized) >= 4 and len(normalize_person_name(match.name)) < 4:
                match.name = name
            if position and not match.position:
                match.position = position
            if height_cm and not match.height_cm:
                match.height_cm = height_cm
            return match

    player = Player(
        id=external_id,
        team_id=team_id,
        name=name,
        jersey_number=jersey,
        position=position,
        height_cm=height_cm,
    )
    db.add(player)
    db.flush()
    return player
