"""Odległości drogowe od dwóch punktów odniesienia (bez AI, bez kosztów).

Adresy punktów są tajne: czytane ze zmiennych środowiskowych REF_A i REF_B (GitHub Secrets),
nigdy nie zapisywane w repozytorium. Do danych trafiają tylko liczby kilometrów (zaokrąglone).
Współrzędne miejsc wydarzeń są zapisywane w data/geocache.json (to publiczne miejsca).
Geokodowanie: Nominatim (OpenStreetMap), trasy: OSRM — oba darmowe, tempo 1 zapytanie/s.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path

import requests

UA = "EventManagerBot (prywatny przewodnik po wydarzeniach)"
CACHE = Path(__file__).resolve().parent.parent / "data" / "geocache.json"
VIEWBOX = "20.60,52.45,21.50,51.85"   # lewy-górny / prawy-dolny róg: Warszawa i okolice
REFS = {"a": ("REF_A", "D"), "b": ("REF_B", "P")}   # D = dom, P = praca; adresy tajne, w aplikacji tylko litery


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("ł", "l")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _get(url: str, **kw):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30, **kw)
    r.raise_for_status()
    return r.json()


def geocode(query: str, must: str = "") -> tuple[float, float] | None:
    """Pierwszy wynik z Nominatim; gdy podano `must` (miejscowość z adresu), wynik musi ją zawierać."""
    j = None
    for attempt in range(2):          # jedno powtórzenie po chwili, gdy usługa odmówi
        time.sleep(1.1 if attempt == 0 else 6)
        try:
            j = _get("https://nominatim.openstreetmap.org/search", params={
                "q": query, "format": "json", "limit": 3, "viewbox": VIEWBOX, "bounded": 1, "countrycodes": "pl"})
            break
        except Exception:
            j = None
    for r in j or []:
        if not must or _fold(must) in _fold(r.get("display_name", "")):
            return float(r["lat"]), float(r["lon"])
    return None


# angielskie nazwy z muzea.waw.pl -> polskie, które zna OpenStreetMap
ALIAS = {
    "museum of modern art in warsaw": "Muzeum Sztuki Nowoczesnej, Warszawa",
    "royal lazienki museum": "Łazienki Królewskie, Warszawa",
    "polish history museum in warsaw": "Muzeum Historii Polski, Warszawa",
    "the royal castle in warsaw": "Zamek Królewski, Warszawa",
    "the praga museum of warsaw": "Muzeum Warszawskiej Pragi, Warszawa",
    "adam mickiewicz museum of literature": "Muzeum Literatury im. Adama Mickiewicza, Warszawa",
    "andrzej wawrzyniak asia and pacific museum": "Muzeum Azji i Pacyfiku, Warszawa",
    "state ethnographic museum": "Państwowe Muzeum Etnograficzne, Warszawa",
    "emanuel ringelblum jewish historical institute": "Żydowski Instytut Historyczny, Warszawa",
    "zydowski instytut historyczny im emanuela ringelbluma": "Żydowski Instytut Historyczny, Warszawa",
    "warsaw university of life sciences museum": "Muzeum SGGW, Warszawa",
    "academy of fine arts museum": "Muzeum Akademii Sztuk Pięknych, Warszawa",
    "museum of the tenth pavilion of the warsaw citadel": "Muzeum X Pawilonu Cytadeli Warszawskiej",
    "fort institute of photography": "Instytut Fotografii Fort, Warszawa",
    "history meeting house": "Dom Spotkań z Historią, Warszawa",
    "central history stop ipn": "Centralny Przystanek Historia, Warszawa",
    "uck alternatywy": "Ursynowskie Centrum Kultury Alternatywy, Warszawa",
}


def _distances(origins: list[tuple[float, float]], dests: list[tuple[float, float]]) -> list[list[float | None]]:
    """km po drogach: wiersz = punkt odniesienia, kolumna = miejsce. Porcjami po 40 miejsc."""
    out = [[None] * len(dests) for _ in origins]
    for i in range(0, len(dests), 40):
        chunk = dests[i:i + 40]
        pts = origins + chunk
        coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in pts)
        src = ";".join(str(k) for k in range(len(origins)))
        dst = ";".join(str(len(origins) + k) for k in range(len(chunk)))
        time.sleep(1.1)
        try:
            j = _get(f"https://router.project-osrm.org/table/v1/driving/{coords}",
                     params={"sources": src, "destinations": dst, "annotations": "distance"})
            for a in range(len(origins)):
                for b in range(len(chunk)):
                    d = j["distances"][a][b]
                    out[a][i + b] = None if d is None else d / 1000
        except Exception:
            continue
    return out


def annotate(events: list[dict]) -> dict:
    """Dopisuje dist_a / dist_b (km, liczby całkowite) i dist_approx. Zwraca meta o punktach."""
    refs = {k: os.environ.get(env, "").strip() for k, (env, _) in REFS.items()}
    refs = {k: v for k, v in refs.items() if v}
    if not refs:
        return {}
    cache = {}
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass

    ref_pts = {}
    for k, addr in refs.items():
        p = geocode(addr)          # współrzędne punktów NIE trafiają do cache ani do repozytorium
        if p:
            ref_pts[k] = p
    if not ref_pts:
        return {}

    # miejsca: klucz = miejsce + adres; kilka prób od najdokładniejszej
    places: dict[str, list[tuple[str, str, bool]]] = {}
    for e in events:
        key = _fold(e.get("venue", "")) + "|" + _fold(e.get("address", ""))
        if key == "|" or key in places:
            continue
        venue, addr, area = e.get("venue", ""), e.get("address", ""), e.get("area", "")
        town = (re.search(r"\d{2}-\d{3}\s+([^\d,]+)", addr) or [None, ""])[1].strip()
        tries: list[tuple[str, str, bool]] = []
        if addr:
            tries.append((addr, town, False))
            if venue:
                tries.append((f"{venue}, {addr}", town, False))
        alias = next((v for k, v in ALIAS.items() if _fold(venue).startswith(k)), "")
        if alias:
            tries.append((alias, "", False))
        if venue:
            short = re.split(r"\s+ul\.|,|\s+\(", venue)[0].strip()    # „Nowy Teatr ul. Madalińskiego…” -> „Nowy Teatr”
            tries.append((f"{venue}, {area}", "", False))
            if short and short != venue:
                tries.append((f"{short}, Warszawa", "", False))
            tries.append((f"{venue}, Warszawa", "", True))   # szersze dopasowanie = przybliżone
        places[key] = tries
    for key, tries in places.items():
        if cache.get(key):
            continue
        res = None
        for q, must, approx in tries:
            p = geocode(q, must)
            if p:
                res = [p[0], p[1], approx]
                break
        if res:
            cache[key] = res          # porażek nie zapamiętujemy: następny tydzień spróbuje ponownie
        else:
            cache.pop(key, None)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")

    keys = [k for k in places if cache.get(k) and cache[k] != "retry"]
    dests = [(cache[k][0], cache[k][1]) for k in keys]
    names = list(ref_pts)
    table = _distances([ref_pts[n] for n in names], dests) if dests else []
    by_key = {k: {n: table[i][j] for i, n in enumerate(names)} for j, k in enumerate(keys)}
    for e in events:
        key = _fold(e.get("venue", "")) + "|" + _fold(e.get("address", ""))
        d = by_key.get(key)
        if not d:
            continue
        for n, km in d.items():
            if km is not None:
                e[f"dist_{n}"] = max(1, round(km))
        if cache[key][2]:
            e["dist_approx"] = True
    return {n: REFS[n][1] for n in names}
# uruchomienie z sekretami REF_A/REF_B
# v2
# v3
# v4
