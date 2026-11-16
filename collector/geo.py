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
REFS = {"a": ("REF_A", "Józefosław"), "b": ("REF_B", "Domaniewska")}   # nazwy publiczne, adresy tajne


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("ł", "l")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _get(url: str, **kw):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30, **kw)
    r.raise_for_status()
    return r.json()


def geocode(query: str) -> tuple[float, float] | None:
    time.sleep(1.1)
    try:
        j = _get("https://nominatim.openstreetmap.org/search", params={
            "q": query, "format": "json", "limit": 1, "viewbox": VIEWBOX, "bounded": 1, "countrycodes": "pl"})
    except Exception:
        return None
    return (float(j[0]["lat"]), float(j[0]["lon"])) if j else None


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

    # miejsca: klucz = miejsce + adres
    places: dict[str, tuple[str, bool]] = {}
    for e in events:
        key = _fold(e.get("venue", "")) + "|" + _fold(e.get("address", ""))
        if key == "|":
            continue
        approx = not e.get("address")
        q = e["address"] if e.get("address") else f'{e.get("venue", "")}, {e.get("area", "")}'
        if e.get("address") and e.get("venue"):
            q = f'{e["address"]}'
        places.setdefault(key, (q, approx))
    for key, (q, _) in places.items():
        if key not in cache:
            p = geocode(q)
            if not p and "," in q:
                p = geocode(q.split(",")[0] + ", Warszawa")
            cache[key] = list(p) if p else None
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")

    keys = [k for k in places if cache.get(k)]
    dests = [tuple(cache[k]) for k in keys]
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
        e["dist_approx"] = places[key][1]
    return {n: REFS[n][1] for n in names}
