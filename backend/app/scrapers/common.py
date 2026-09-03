"""Shared helpers for the real scrapers: team/player identity resolution.

Both basket.co.il and the Euroleague API mint their own numeric team/player
ids that are NOT stable across seasons (basket.co.il especially — team ids
reset every year). We instead key our own `teams`/`players` rows on a
source-independent slug so re-syncing a later season lands on the same rows.
"""

import re
import unicodedata
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Player, Team

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
    return f"WL_{abs(hash(name)) % 100000}", name


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
    also checks for a name match against an existing row from the *other*
    competition's scraper (e.g. an EL_ id vs a WL_ id for the same human) so
    the roster doesn't end up with duplicate rows for one player."""
    player = db.get(Player, external_id)
    if player is not None:
        return player

    if team_id == "HAPOEL_JLM":
        # Only meaningful when both names are Latin-script (e.g. matching a
        # segevstats "WL_" id against an "EL_" one) — a Hebrew name ASCII-folds
        # to near-nothing via NFKD, which would collapse distinct players.
        normalized = normalize_person_name(name)
        if len(normalized) >= 4:
            for candidate in db.query(Player).filter(Player.team_id == team_id).all():
                if normalize_person_name(candidate.name) == normalized:
                    return candidate

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
