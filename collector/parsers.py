"""Parsery migawek dla stron o stałym układzie — odczyt bez AI (bez kosztu).

Każda funkcja dostaje tekst migawki i datę zebrania, zwraca listę wydarzeń
w formacie: title, date, time, date_from/date_to (wystawy), venue, address,
area, price, how, url, note, categories.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
    "sierpnia": 8, "września": 9, "wrzesnia": 9, "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}
LINK = re.compile(r"^\[(.+?)\]\((https?://[^)\s]+)\)$")


def _dmy(s: str) -> str:
    d, m, y = (int(x) for x in s.split("."))
    return date(y, m, d).isoformat()


def waw4free(text: str, collected: date) -> list[dict]:
    lines = [l.strip() for l in text.splitlines()]
    events: list[dict] = []
    seen: set = set()
    cur: dict | None = None
    date_rx = re.compile(r"^\[(\d{1,2}\.\d{1,2}\.\d{4})\]\([^)]*\)\s*\([^)]*\)\s*,\s*(?:(\d{1,2}:\d{2})\s*,\s*)?\[([^\]]+)\]")
    rel_rx = re.compile(r"^\[(dzisiaj|jutro)\]\([^)]*\)\s*,\s*(?:(\d{1,2}:\d{2})\s*,\s*)?\[([^\]]+)\]")
    ong_rx = re.compile(r"wydarzenie trwające \(do \[(\d{1,2}\.\d{1,2}\.\d{4})\]\([^)]*\)\s*,[^)]*\)\s*,\s*\[([^\]]+)\]")
    for l in lines:
        m = LINK.match(l)
        if m and "/wydarzenie-" in m.group(2):
            cur = {"title": m.group(1), "url": m.group(2), "categories": [], "price": "bezpłatne (wg waw4free)",
                   "how": "Zasady wejścia: sprawdź na stronie wydarzenia."}
            continue
        if cur is None:
            continue
        if l.startswith("(wydarzenie płatne"):
            cur["price"] = "płatne (wg waw4free)"
            continue
        if l.startswith("(dobrowolna zrzutka"):
            cur["price"] = "dobrowolna zrzutka"
            continue
        lab = LINK.match(l)
        label = lab.group(1) if lab else l
        if len(label) < 20 and re.fullmatch(r"[a-ząćęłńóśźż \-]+", label) and not l.startswith("wydarzenie"):
            cur["categories"].append(label)
            continue
        dm, rm, om = date_rx.match(l), rel_rx.match(l), ong_rx.search(l)
        if dm or rm:
            if dm:
                d = _dmy(dm.group(1)); t, area = dm.group(2), dm.group(3)
            else:
                d = (collected + timedelta(days=0 if rm.group(1) == "dzisiaj" else 1)).isoformat()
                t, area = rm.group(2), rm.group(3)
            ev = {**cur, "date": d, "time": (t.zfill(5) if t else None), "area": area}
        elif om:
            ev = {**cur, "date_from": collected.isoformat(), "date_to": _dmy(om.group(1)), "area": om.group(2)}
        else:
            continue
        if ev["area"].lower().startswith("okolice"):
            ev["note"] = "Okolice Warszawy: miejscowość i odległość sprawdź na stronie wydarzenia."
        key = (ev["url"], ev.get("date") or ev.get("date_to"), ev.get("time"))
        if key not in seen:  # to samo wydarzenie bywa w kilku kategoriach
            seen.add(key)
            events.append(ev)
        cur = None
    return events


def alternatywy(text: str, collected: date) -> list[dict]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    events, seen = [], set()
    i = 0
    while i < len(lines) - 3:
        # wzorzec: [dzień] / [miesiąc słownie] / [rok] / [godzina], poprzedzony linkami tytułu
        if re.fullmatch(r"\d{1,2}", lines[i]) and lines[i + 1].lower() in MONTHS and re.fullmatch(r"20\d{2}", lines[i + 2]):
            t = lines[i + 3] if re.fullmatch(r"\d{1,2}:\d{2}", lines[i + 3]) else None
            # szukamy wstecz linków do tego samego wydarzenia
            j, links = i - 1, []
            while j >= 0 and LINK.match(lines[j]) and len(links) < 2:
                links.insert(0, LINK.match(lines[j]).groups())
                j -= 1
            if links:
                url = links[-1][1]
                title = links[0][0]
                sub = links[1][0] if len(links) > 1 and links[1][1] == links[0][1] else ""
                d = date(int(lines[i + 2]), MONTHS[lines[i + 1].lower()], int(lines[i])).isoformat()
                key = (url, d, t)
                if key not in seen and "alternatywy.art" in url:
                    seen.add(key)
                    events.append({
                        "title": title,
                        "description": sub if sub and sub.lower() not in title.lower() else "",
                        "date": d, "time": t.zfill(5) if t else None,
                        "venue": "UCK „Alternatywy”", "url": url,
                        "how": "Bilety i zapisy: sprawdź na stronie wydarzenia.",
                    })
            i += 4 if t else 3
            continue
        i += 1
    return events
