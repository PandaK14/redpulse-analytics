SEASON = "2025-2026"

POSITIONS = ["PG", "SG", "SF", "PF", "C"]

# Player identities here are synthetic (not real athletes) — only real, public
# club names are used so mock standings/schedules read realistically.
FIRST_NAMES = [
    "Omri", "Yovel", "Nadav", "Itay", "Daniel", "Roy", "Tomer", "Idan",
    "Yam", "Ariel", "Marcus", "Devon", "Jalen", "Trey", "Cameron",
    "Xavier", "Malik", "Deshawn", "Luka", "Filip", "Marko", "Nikola",
    "Stefan", "Bogdan", "Ivan", "Petar", "Andrija", "Rok",
]
LAST_NAMES = [
    "Cohen", "Levi", "Mizrahi", "Peretz", "Azulay", "Biton", "Dahan",
    "Avraham", "Shalom", "Ben-David", "Johnson", "Williams", "Carter",
    "Brooks", "Reed", "Simic", "Kovac", "Novak", "Horvat", "Petrovic",
    "Jovanovic", "Vidal", "Ilic", "Rankovic", "Kuzmic", "Babic",
]

HAPOEL_JERUSALEM = {"id": "HAPOEL_JLM", "name": "Hapoel Jerusalem", "short_name": "HAP JLM"}

WINNER_LEAGUE_OPPONENTS = [
    {"id": "MACCABI_TA", "name": "Maccabi Tel Aviv", "short_name": "MAC TA"},
    {"id": "HAPOEL_TA", "name": "Hapoel Tel Aviv", "short_name": "HAP TA"},
    {"id": "MACCABI_RL", "name": "Maccabi Rishon LeZion", "short_name": "MAC RL"},
    {"id": "IRONI_NS", "name": "Ironi Nes Ziona", "short_name": "IRO NS"},
    {"id": "HAPOEL_HOLON", "name": "Hapoel Holon", "short_name": "HAP HOL"},
    {"id": "BNEI_HERZLIYA", "name": "Bnei Herzliya", "short_name": "BNEI HRZ"},
    {"id": "IRONI_NAHARIYA", "name": "Ironi Nahariya", "short_name": "IRO NAH"},
    {"id": "HAPOEL_EILAT", "name": "Hapoel Eilat", "short_name": "HAP EIL"},
    {"id": "MACCABI_RG", "name": "Maccabi Ramat Gan", "short_name": "MAC RG"},
]

EUROCUP_OPPONENTS = [
    {"id": "VALENCIA", "name": "Valencia Basket", "short_name": "VAL"},
    {"id": "TURK_TELEKOM", "name": "Turk Telekom", "short_name": "TT"},
    {"id": "CEDEVITA_OLI", "name": "Cedevita Olimpija", "short_name": "COL"},
    {"id": "HAMBURG_TOWERS", "name": "Hamburg Towers", "short_name": "HAM"},
    {"id": "JOVENTUT", "name": "Joventut Badalona", "short_name": "JOV"},
    {"id": "ARIS_MIDEA", "name": "Aris Midea", "short_name": "ARIS"},
    {"id": "CLUJ_NAPOCA", "name": "U-BT Cluj Napoca", "short_name": "CLUJ"},
    {"id": "PERISTERI", "name": "Peristeri", "short_name": "PER"},
    {"id": "TRENTO", "name": "Trento", "short_name": "TRE"},
]

# Half-court shot zones: approximate (x, y) bounding boxes on a 0-100 x 0-100
# grid (basket at x=50, y=0), used to sample coordinates and label shot_type.
SHOT_ZONES = [
    {"shot_type": "Rim", "fg_kind": "2PT", "x_range": (35, 65), "y_range": (0, 8), "weight": 0.32, "make_pct": 0.62},
    {"shot_type": "Paint", "fg_kind": "2PT", "x_range": (25, 75), "y_range": (8, 19), "weight": 0.14, "make_pct": 0.44},
    {"shot_type": "Mid-Range", "fg_kind": "2PT", "x_range": (15, 85), "y_range": (19, 23), "weight": 0.16, "make_pct": 0.40},
    {"shot_type": "Corner-3", "fg_kind": "3PT", "x_range": (3, 15), "y_range": (0, 14), "weight": 0.10, "make_pct": 0.38},
    {"shot_type": "Above-the-Break-3", "fg_kind": "3PT", "x_range": (15, 85), "y_range": (23, 30), "weight": 0.28, "make_pct": 0.35},
]

FT_PCT = 0.75
