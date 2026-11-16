"""Reguły użytkowniczki: dni wolne, godziny, wykluczenia, tagi i kategorie.

Wszystkie słowa kluczowe są tu, w jednym miejscu, żeby łatwo je poprawiać.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

# ---------------------------------------------------------------- dni wolne


def easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(y, month, day)


def pl_holidays(y: int) -> dict[date, str]:
    e = easter(y)
    h = {
        date(y, 1, 1): "Nowy Rok",
        date(y, 1, 6): "Trzech Króli",
        e: "Wielkanoc",
        e + timedelta(days=1): "Poniedziałek Wielkanocny",
        date(y, 5, 1): "Święto Pracy",
        date(y, 5, 3): "Święto Konstytucji 3 Maja",
        e + timedelta(days=49): "Zielone Świątki",
        e + timedelta(days=60): "Boże Ciało",
        date(y, 8, 15): "Wniebowzięcie NMP",
        date(y, 11, 1): "Wszystkich Świętych",
        date(y, 11, 11): "Święto Niepodległości",
        date(y, 12, 25): "Boże Narodzenie",
        date(y, 12, 26): "Drugi dzień Bożego Narodzenia",
    }
    if y >= 2025:
        h[date(y, 12, 24)] = "Wigilia"
    return h


def day_off(d: date) -> str | None:
    """Nazwa dnia wolnego albo None dla dnia roboczego."""
    hol = pl_holidays(d.year).get(d)
    if hol:
        return hol
    if d.weekday() == 5:
        return "sobota"
    if d.weekday() == 6:
        return "niedziela"
    return None


EARLIEST_WEEKDAY = "17:00"
LATEST_WEEKDAY = "23:00"


def time_ok(d: date, t: str | None) -> tuple[bool, str]:
    """(czy pokazać, powód). W dzień roboczy start 17:00–23:00, w dni wolne bez ograniczeń."""
    if day_off(d):
        return True, ""
    if t is None:
        return False, "dzień roboczy bez podanej godziny"
    if t < EARLIEST_WEEKDAY:
        return False, f"dzień roboczy, start {t} (przed 17:00)"
    if t > LATEST_WEEKDAY:
        return False, f"dzień roboczy, start {t} (po 23:00)"
    return True, ""


# ---------------------------------------------------------------- słowa kluczowe


def _rx(words: list[str]) -> re.Pattern:
    return re.compile(r"(?<![\wąćęłńóśźż])(?:" + "|".join(words) + r")(?![\wąćęłńóśźż])", re.I)


# Twarde wykluczenia: (nazwa reguły, wzorzec)
EXCLUDE = [
    ("dla dzieci / rodzin", _rx([
        r"dla dzieci", r"dzieci(?:ęc|ec)\w*", r"dla rodzin", r"rodzinn\w*", r"familijn\w*", r"przedszkol\w*",
        r"maluch\w*", r"niemowl\w*", r"bobas\w*", r"dla najmłodszych", r"bajk[aię]\b", r"mikołajk\w*",
        r"rodzic(?:e|ów)? z dzie\w*", r"\d{1,2}\s*[-–]\s*1?\d\s*lat", r"od [2-9] lat", r"dla uczni\w*", r"półkolon\w*",
        r"ferie", r"dla szkół", r"dla młodzieży(?! i dorosł)", r"teatrzyk\w*", r"kids", r"dzieciństw\w*",
        r"brzdąc\w*", r"baśń", r"baśni\w*", r"bajecz\w*", r"bajkow\w*", r"niedzielank\w*", r"GUD", r"uniwersytet dzieci",
        r"mama i córka", r"z mamą", r"z tatą", r"wychowawcz\w*", r"młode horyzonty", r"wielkie kino dla małych",
        r"junior\w*", r"\((?:[0-9]|1[0-2])\+\)", r"\((?:[0-9]|1[0-2])\s*[-–]\s*\d{1,2} lat\)", r"[0-9]\+ lat",
    ])),
    ("dla seniorów", _rx([r"senior\w*", r"60\+", r"65\+", r"uniwersytet\w* trzeciego wieku", r"UTW"])),
    ("karaoke", _rx([r"karaoke"])),
    ("patriotyczne / polityczne", _rx([
        r"patriotyczn\w*", r"(?<!muzeum )(?<!muzeum )niepodległ\w*", r"11 listopada", r"żołnier\w*", r"wyklęt\w*",
        r"powsta\w* warszawsk\w*", r"powstańc\w*", r"marsz(?:u|em|e|ów)?", r"kombatan\w*",
    ])),
    ("heavy metal", _rx([r"heavy metal\w*", r"metal\w*", r"thrash", r"death metal", r"black metal", r"metalcore"])),
    ("disco polo", _rx([r"disco polo", r"disco-polo", r"discopolo"])),
    ("kabaret", _rx([r"kabaret\w*"])),
    ("taniec towarzyski / swing / salsa", _rx([
        r"swing\w*", r"salsa\w*", r"bachat\w*", r"tang[oa]\w*", r"kizomb\w*", r"lindy hop", r"potańców\w*",
        r"dancing\w*", r"zumba\w*", r"taniec towarzysk\w*", r"folk\w* taneczn\w*", r"jive", r"walc\w*",
        r"wieczór taneczn\w*", r"wieczorek taneczn\w*",
    ])),
    ("hard techno", _rx([r"hard techno", r"hardstyle", r"hardcore techno", r"gabber"])),
    ("sport, kursy i porady (nie kultura)", _rx([
        r"toastmaster\w*", r"public speaking", r"autoprezentacj\w*", r"mentoring\w*", r"linkedin", r"mark\w* osobist\w*",
        r"biznes\w*", r"trening\w*", r"treningi", r"fitness", r"pilates", r"joga", r"jogi", r"jogą", r"yoga", r"aikido", r"cross ?training",
        r"gimnastyk\w*", r"sport", r"mecz\w*", r"bieg\w*", r"nordic walking", r"rodzicielstw\w*", r"wspierać dziecko", r"dla rodziców",
        r"meet & speak", r"speaking club", r"language exchange", r"online", r"webinar\w*", r"porad\w*", r"zakwaszeni\w*",
    ])),
    ("multipleks", _rx([r"cinema city", r"multikino", r"helios"])),
]

# Wydarzenia komercyjne: nie trafiają do NISZOWYCH (mogą wrócić w zakładce KOMERCYJNE)
COMMERCIAL_VENUE = _rx([
    r"capitol\w*", r"teatr\w* kamienica", r"palladium", r"scena relax", r"teatr\w* polonia", r"och[- ]teatr\w*",
    r"teatr\w* kwadrat", r"teatr\w* komedia", r"teatr\w* 6\. piętro", r"teatr\w* syrena", r"teatr\w* roma",
    r"teatr\w* polski", r"klub komediowy", r"torwar", r"pge narodowy", r"stodoła", r"progresja", r"hulakula",
    r"sala koncertowa fryderyk", r"muzeum archidiecezji\w*", r"chopin point", r"explosion club", r"osir\w*",
    r"simair\w*", r"hala expo", r"ptak", r"wedel\w*", r"centrum nauki kopernik", r"copernicus science\w*",
])
COMMERCIAL_TITLE = _rx([
    r"koncert\w* chopinowsk\w*", r"przy świecach", r"candlelight", r"boxing", r"zooegzotyka", r"lot demonstracyjny",
    r"teściow\w*", r"capitol by night", r"dreamlive", r"mecz\w*",
])


def commercial(title: str, venue: str) -> bool:
    return bool(COMMERCIAL_VENUE.search(venue or "") or COMMERCIAL_TITLE.search(title or ""))


# Tagi gatunkowe i tematyczne (do uczenia gustu w aplikacji)
TAGS = [
    ("elektro", _rx([r"elektro\w*", r"electro\w*", r"electronic", r"elektroniczn\w*", r"dj", r"dj-\w*", r"dj set", r"rave"])),
    ("house", _rx([r"house"])),
    ("techno", _rx([r"techno"])),
    ("jazz", _rx([r"jazz\w*", r"jam session"])),
    ("klasyka", _rx([r"filharmoni\w*", r"symfoni\w*", r"kameraln\w*", r"recital\w*", r"fortepian\w*", r"orkiestr\w*", r"chopin\w*", r"kwartet\w*", r"klasyczn\w*", r"opera\w*"])),
    ("rock / alternatywa", _rx([r"rock\w*", r"punk\w*", r"indie", r"alternatyw\w* (?:rock|muzyk)\w*", r"post-rock"])),
    ("folk / world", _rx([r"folk\w*", r"ludow\w*", r"world music", r"etno\w*"])),
    ("hip-hop", _rx([r"hip[ -]?hop\w*", r"rap\w*"])),
    ("stand-up", _rx([r"stand[- ]?up\w*", r"open mic"])),
    ("film", _rx([r"film\w*", r"kino\w*", r"seans\w*", r"projekcj\w*", r"dkf"])),
    ("teatr", _rx([r"spektakl\w*", r"teatr\w*", r"monodram\w*", r"premiera"])),
    ("performans / taniec", _rx([r"performans\w*", r"performance", r"taniec współczesn\w*", r"choreograf\w*"])),
    ("wystawa", _rx([r"wystaw\w*", r"wernisaż\w*", r"finisaż\w*", r"ekspozycj\w*"])),
    ("wykład / spotkanie", _rx([r"wykład\w*", r"spotkani\w*", r"rozmow\w*", r"dyskusj\w*", r"debat\w*", r"prelekcj\w*", r"autorsk\w*", r"książk\w*", r"reading party", r"literack\w*"])),
    ("warsztaty", _rx([r"warsztat\w*", r"kurs\w*", r"zajęci\w*", r"pracowni\w*"])),
    ("oprowadzanie", _rx([r"oprowadzani\w*", r"zwiedzani\w*", r"spacer\w*"])),
    ("LGBT+", _rx([r"lgbt\w*", r"queer\w*", r"lesbij\w*", r"tęczow\w*", r"drag", r"pride (?:month|parade|week)", r"parad\w* równości", r"nieheteronormatywn\w*", r"sapphic"])),
    ("dla singli", _rx([r"singl\w*"])),
    ("impreza", _rx([r"impreza\w*", r"impreź\w*", r"party", r"klubow\w*", r"noc\w* klubow\w*"])),
    ("fotografia", _rx([r"fotograf\w*", r"zdjęci\w*"])),
    ("malarstwo", _rx([r"malarstw\w*", r"obraz\w*", r"malarz\w*", r"malarsk\w*"])),
    ("rzeźba", _rx([r"rzeźb\w*", r"rzeźbiar\w*"])),
    ("instalacja / sztuka nowych mediów", _rx([r"instalacj\w*", r"nowych mediów", r"wideo", r"video"])),
]

CATEGORY_ORDER = [
    ("Wystawy", {"wystawa"}),
    ("Stand-up", {"stand-up"}),
    ("Imprezy i taniec", {"elektro", "house", "techno"}),   # tylko elektro / house / techno
    ("Koncerty", {"jazz", "klasyka", "rock / alternatywa", "folk / world", "hip-hop"}),
    ("Teatr i performans", {"teatr", "performans / taniec"}),
    ("Film", {"film"}),
    ("Warsztaty", {"warsztaty"}),
    ("Spotkania i wykłady", {"wykład / spotkanie", "oprowadzanie"}),
]


def classify(text: str, title: str = "") -> tuple[list[str], str]:
    tags = [name for name, rx in TAGS if rx.search(text)]
    if re.search(r"koncert\w*", text, re.I) and not any(t in tags for t in ("jazz", "klasyka", "rock / alternatywa", "folk / world", "hip-hop", "elektro", "house", "techno")):
        cat = "Koncerty"
    else:
        cat = "Inne"
    # tytuł waży najbardziej: pierwsza kategoria, której tag pada w tekście
    for name, needs in CATEGORY_ORDER:
        if needs & set(tags):
            cat = name if cat == "Inne" else cat
            break
    if re.search(r"koncert\w*", text, re.I):
        cat = "Koncerty" if cat in ("Inne", "Spotkania i wykłady") else cat
    # koncert (także improwizowany / ambientowy) to nie impreza taneczna, chyba że jest DJ, rave albo „impreza”
    if cat == "Imprezy i taniec" and re.search(r"koncert\w*", text, re.I) and not re.search(r"(?<!\w)dj(?!\w)|dj-|rave|impreza|impreź|party|klubow", text, re.I):
        cat = "Koncerty"
    # tytuł rozstrzyga: „warsztaty” to warsztaty, pokazy tańca amatorskiego to performans
    if re.search(r"warsztat\w*", title, re.I):
        cat = "Warsztaty"
    elif re.search(r"spotkania taneczn\w*|choreograf\w*|taniec współczesn\w*", title, re.I) and not any(t in tags for t in ("elektro", "house", "techno")):
        cat = "Teatr i performans"
    return tags, cat


def exclusion(text: str) -> str | None:
    for name, rx in EXCLUDE:
        if rx.search(text):
            return name
    return None
