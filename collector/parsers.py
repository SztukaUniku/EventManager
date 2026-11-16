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
            t = t.zfill(5) if t else None
            ev = {**cur, "date": d, "time": None if t == "00:00" else t, "area": area}
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


# ---------------------------------------------------------------- pomocnicze

def _pages(text: str) -> list[tuple[str, list[str]]]:
    """Dzieli migawkę na (adres strony, linie)."""
    res = []
    for blk in text.split("=== STRONA: ")[1:]:
        url, _, body = blk.partition("\n")
        res.append((url.strip(), [l.strip() for l in body.splitlines() if l.strip()]))
    return res


def _year_for(month: int, collected: date) -> int:
    """Rok dla daty bez roku: jeśli miesiąc jest dużo wcześniej niż teraz, to przyszły rok."""
    return collected.year + 1 if month < collected.month - 3 else collected.year


DOW_RX = r"(?:poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela)"


# ---------------------------------------------------------------- Filharmonia Narodowa

def filharmonia(text: str, collected: date) -> list[dict]:
    events = []
    for _, lines in _pages(text):
        for i, l in enumerate(lines[:-2]):
            m = LINK.match(l)
            if not m or "/repertuar/" not in m.group(2):
                continue
            dm = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", lines[i + 1])
            tm = re.fullmatch(DOW_RX + r"\s*/\s*(\d{1,2}:\d{2})", lines[i + 2])
            if not (dm and tm):
                continue
            d, mo = int(dm.group(1)), int(dm.group(2))
            label = m.group(1)
            title = None
            for k in range(i + 3, min(i + 6, len(lines))):
                km = re.match(r"Kup bilet : (.+), \d{1,2}\.\d{1,2} \d{1,2}:\d{2}", lines[k])
                if km:
                    title = km.group(1)
                    break
            if not title:
                title = re.split(r"(?<=[a-ząćęłńóśźż])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„])", label, maxsplit=1)[0][:80]
            hall = lines[i + 3] if i + 3 < len(lines) and not lines[i + 3].startswith(("Kup", "[")) else ""
            events.append({
                "title": title, "date": date(_year_for(mo, collected), mo, d).isoformat(), "time": tm.group(1).zfill(5),
                "venue": "Filharmonia Narodowa" + (f", {hall}" if hall and "Filharmon" not in hall else ""),
                "description": label[len(title):].strip()[:300] if label.startswith(title) else label[:300],
                "url": m.group(2), "how": "Bilety na stronie Filharmonii.",
            })
    return events


# ---------------------------------------------------------------- Nowy Teatr

def nowyteatr(text: str, collected: date) -> list[dict]:
    events = []
    for url, lines in _pages(text):
        mm = re.search(r"date_from=(\d{4})-(\d{2})", url)
        if not mm:
            continue
        y, mo = int(mm.group(1)), int(mm.group(2))
        day = None
        i = 0
        while i < len(lines):
            l = lines[i]
            dh = re.fullmatch(r"(\d{2})\s*" + DOW_RX, l)
            if dh:
                day = int(dh.group(1))
                i += 1
                continue
            if l.startswith("!!!") and day:
                block = []
                j = i + 1
                while j < len(lines) and not lines[j].startswith("!!!") and lines[j] != "empty slot" and not re.fullmatch(r"(\d{2})\s*" + DOW_RX, lines[j]) and not lines[j].startswith("[Następny"):
                    block.append(lines[j])
                    j += 1
                i = j
                if not block or not re.fullmatch(r"\d{1,2}\.\d{2}", block[0]):
                    continue  # brak godziny = gościnny występ poza Warszawą
                t = block[0].replace(".", ":").zfill(5)
                ticket, sold_out, free, rest = "", False, False, []
                for b in block[1:]:
                    tl = LINK.match(b)
                    if tl and "bilet" in tl.group(1).lower():
                        ticket = tl.group(2)
                    elif b == "Brak biletów":
                        sold_out = True
                    elif b == "Wstęp wolny":
                        free = True
                    elif b != "params list":
                        rest.append(b)
                if not rest:
                    continue
                title = rest[0]
                tags = next((r for r in rest[1:] if re.match(r"^(Teatr|Muzyka|Literatura|Spotkania|Warsztaty|Akcje|Taniec|Film|Dla|Wiek)", r)), "")
                people = " ".join(r for r in rest[1:] if r != tags)
                events.append({
                    "title": title, "date": date(y, mo, day).isoformat(), "time": t,
                    "venue": "Nowy Teatr, ul. Madalińskiego 10/16", "description": people[:200],
                    "categories": [x.strip() for x in tags.split("/")] if tags else [],
                    "price": "wstęp wolny" if free else "", "url": url, "ticket_url": ticket,
                    "how": "Brak biletów (stan z dnia zebrania)." if sold_out else ("Wstęp wolny." if free else "Bilety na stronie Nowego Teatru."),
                })
                continue
            i += 1
    return events


# ---------------------------------------------------------------- Dom Kultury Kadr

def kadr(text: str, collected: date) -> list[dict]:
    events = []
    rx = re.compile(r"^(?P<kind>.*?)\s+(?:pn|wt|śr|czw|pt|sb|ndz)\s+(?P<dates>\d[\d., i]*?\d{4}|\d{1,2}\.\d{1,2})(?:\s*-\s*(?:pn|wt|śr|czw|pt|sb|ndz)\s+(?P<to>\d{1,2}\.\d{1,2}\.\d{4}))?\s+(?:(?P<time>\d{1,2}\.\d{2})(?:[, ]+(?:i\s+)?\d{1,2}\.\d{2})*\s+)?(?P<title>.+)$")
    for _, lines in _pages(text):
        for l in lines:
            m = LINK.match(l)
            if not m or "/repertuar/" not in m.group(2):
                continue
            label = m.group(1)
            half = label[: len(label) // 2 + 1].strip()  # etykieta jest zdublowana
            if label.startswith(half.strip()) and label[len(half):].strip() and half.strip() == label[len(half):].strip():
                label = half.strip()
            else:
                n = len(label)
                label = label[: (n + 1) // 2].strip() if label[: n // 2].strip() == label[(n + 1) // 2:].strip() else label
            r = rx.match(label)
            if not r:
                continue
            ds = r.group("dates")
            years = re.findall(r"(20\d{2})", ds)
            y = int(years[-1]) if years else None
            dates = []
            for dd, mo in re.findall(r"(\d{1,2})\.(\d{1,2})\.?", ds):
                dates.append(date(y or _year_for(int(mo), collected), int(mo), int(dd)))
            if not dates:
                continue
            base = {"title": r.group("title").strip(), "venue": "Dom Kultury „Kadr”", "url": m.group(2),
                    "description": r.group("kind").strip(), "categories": [r.group("kind").strip()],
                    "how": "Bilety i zapisy: sprawdź na stronie wydarzenia."}
            if r.group("to"):
                dt = r.group("to").split(".")
                events.append({**base, "date_from": dates[0].isoformat(), "date_to": date(int(dt[2]), int(dt[1]), int(dt[0])).isoformat()})
                continue
            t = r.group("time").replace(".", ":").zfill(5) if r.group("time") else None
            for d in dates:
                events.append({**base, "date": d.isoformat(), "time": t})
    return events


# ---------------------------------------------------------------- Służewski Dom Kultury

def sdk(text: str, collected: date) -> list[dict]:
    events = []
    for _, lines in _pages(text):
        for i, l in enumerate(lines):
            dm = re.match(r"^Dni:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*/\s*" + DOW_RX + r"\s*/\s*(\d{1,2})[.:](\d{2})", l)
            if not dm:
                continue
            d, mo, y, hh, mi = (int(x) for x in dm.groups())
            link, cats, price, desc = None, [], "", ""
            for k in range(i + 1, min(i + 14, len(lines))):
                if lines[k].startswith("Dni:"):
                    break
                lm = LINK.match(lines[k])
                if lm and "/wydarzenia/rodzaj-wydarzenia/" in lm.group(2) and not link:
                    link = lm
                elif lm and "/dla-kogo/" in lm.group(2):
                    cats.append(lm.group(1))
                elif lines[k] in ("Dorośli", "Młodzież", "Dzieci", "Seniorzy"):
                    cats.append(lines[k])
                elif lm and lm.group(1) in ("Bezpłatne", "Płatne"):
                    price = "bezpłatne" if lm.group(1) == "Bezpłatne" else "płatne"
                elif link and not desc and not lines[k].startswith("[") and len(lines[k]) > 40:
                    desc = lines[k]
            if not link:
                continue
            events.append({
                "title": link.group(1), "date": date(y, mo, d).isoformat(), "time": f"{hh:02d}:{mi:02d}",
                "venue": "Służewski Dom Kultury, ul. Bacha 15", "url": link.group(2), "price": price,
                "description": desc[:300], "categories": [c for c in cats if c != "Dorośli"],
                "how": "Szczegóły i bilety na stronie wydarzenia.",
            })
    return events


# ---------------------------------------------------------------- Muzeum Sztuki Nowoczesnej

def msn(text: str, collected: date) -> list[dict]:
    events, seen_ex = [], set()
    for _, lines in _pages(text):
        cur = None
        for i, l in enumerate(lines):
            dm = re.fullmatch(r"(\d{1,2}) (" + "|".join(MONTHS) + r")", l)
            if dm and i and lines[i - 1].rstrip(",") in ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"):
                mo = MONTHS[dm.group(2)]
                cur = date(_year_for(mo, collected), mo, int(dm.group(1)))
                continue
            m = LINK.match(l)
            if not m:
                continue
            label, url = m.group(1), m.group(2)
            ex = re.search(r"(\d{2}\.\d{2}\.\d{4})–(\d{2}\.\d{2}\.\d{4})", label)
            if "/wystawy/" in url and ex:
                if url not in seen_ex:
                    seen_ex.add(url)
                    title = re.sub(r"^(Wystawa\s+)?\d{2}\.\d{2}\.\d{4}–\d{2}\.\d{2}\.\d{4}\s*", "", label).strip() or label.split(" 2")[0]
                    title = re.sub(r"\s*\d{2}\.\d{2}\.\d{4}–\d{2}\.\d{2}\.\d{4}$", "", title)
                    if title.isupper():  # „JESTEŚ W SERCU ZMIAN. SURREALIZM” -> „Jesteś w sercu zmian. Surrealizm”
                        title = re.sub(r"(^|[.!?]\s+)(\w)", lambda x: x.group(1) + x.group(2).upper(), title.lower())
                    events.append({"title": title, "date_from": _dmy(ex.group(1)), "date_to": _dmy(ex.group(2)),
                                   "venue": "Muzeum Sztuki Nowoczesnej", "url": url, "categories": ["wystawa"],
                                   "how": "Godziny otwarcia i bilety: sprawdź na stronie muzeum."})
                continue
            if "/wydarzenia/" in url and cur:
                tm = re.match(r"^(?P<kind>.*?)\s*(?P<t>\d{1,2}:\d{2})(?:\s*-\s*\d{1,2}:\d{2})?\s+(?P<title>.+)$", label)
                if not tm:
                    continue
                events.append({"title": tm.group("title"), "date": cur.isoformat(), "time": tm.group("t").zfill(5),
                               "venue": "Muzeum Sztuki Nowoczesnej", "url": url, "categories": [tm.group("kind")] if tm.group("kind") else [],
                               "description": tm.group("kind"), "how": "Szczegóły i zapisy na stronie wydarzenia."})
    return events


# ---------------------------------------------------------------- Teatr Studio

def teatrstudio(text: str, collected: date) -> list[dict]:
    events = []
    for url, lines in _pages(text):
        if "/repertuar" not in url:
            continue
        mm = re.search(r"month=(\d{1,2})-(\d{4})", url)
        mo, y = (int(mm.group(1)), int(mm.group(2))) if mm else (collected.month, collected.year)
        day, i = None, 0
        while i < len(lines):
            l = lines[i]
            if l.lower() in ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela") and i + 1 < len(lines) and re.fullmatch(r"\d{2}", lines[i + 1]):
                day = int(lines[i + 1])
                i += 2
                continue
            tm = re.match(r"^G\. (\d{1,2}:\d{2})", l)
            if tm and day and i + 1 < len(lines):
                lm = LINK.match(lines[i + 1])
                extra = lines[i + 2: i + 5]
                if lm and "/galeria/wystawy/" not in lm.group(2) and not any("ODWOŁAN" in x or "ZAMKNIĘT" in x for x in extra):
                    kind = extra[0] if extra and not extra[0].startswith("[") else ""
                    note = next((x for x in extra[1:] if x.lower().startswith(("wstęp", "→"))), "")
                    events.append({
                        "title": lm.group(1), "date": date(y, mo, day).isoformat(), "time": tm.group(1).zfill(5),
                        "venue": "Teatr Studio, Pałac Kultury i Nauki", "url": lm.group(2),
                        "categories": [kind] if kind else [], "description": kind.capitalize() if kind else "",
                        "price": "wstęp wolny" if "wstęp wolny" in note.lower() else "",
                        "how": note.capitalize() if note else "Bilety na stronie Teatru Studio.",
                    })
                i += 2
                continue
            i += 1
    return events


# ---------------------------------------------------------------- Dom Sztuki SMB Jary (kino i wydarzenia)

def domsztuki(text: str, collected: date) -> list[dict]:
    events, seen = [], set()
    short = {"sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6, "lip": 7, "sie": 8, "wrz": 9, "paź": 10, "lis": 11, "gru": 12}
    for _, lines in _pages(text):
        for l in lines:
            m = LINK.match(l)
            if not m:
                continue
            r = re.match(r"^(" + "|".join(short) + r") (\d{1,2}) \S+ (\d{1,2}:\d{2}) (.+)$", m.group(1))
            if not r:
                continue
            mo = short[r.group(1)]
            d = date(_year_for(mo, collected), mo, int(r.group(2)))
            rest = r.group(4)
            cut = re.split(r"\s\d{1,2} [a-ząćęłńóśźż]+, godz\.", rest)[0].strip()
            key = (m.group(2), d)
            if key in seen:
                continue
            seen.add(key)
            free = "Wstęp wolny" in rest
            events.append({
                "title": cut[:120], "date": d.isoformat(), "time": r.group(3).zfill(5),
                "venue": "Dom Sztuki SMB „Jary”, ul. Wiolinowa 14", "url": m.group(2),
                "price": "wstęp wolny" if free else "", "description": rest[len(cut):].split("Wstęp wolny")[0].strip(" ,")[:200],
                "how": "Wstęp wolny." if free else "Bilety na stronie Domu Sztuki.",
            })
    return events


# ---------------------------------------------------------------- muzea.waw.pl (wystawy czasowe)

EN_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                          "september", "october", "november", "december"], 1)}


def _any_date(s: str) -> date | None:
    m = re.match(r"(\d{1,2}) ([A-Za-ząćęłńóśźż]+) (\d{4})", s.strip())
    if not m:
        return None
    name = m.group(2).lower()
    mo = EN_MONTHS.get(name) or MONTHS.get(name)
    return date(int(m.group(3)), mo, int(m.group(1))) if mo else None


def muzea(text: str, collected: date) -> list[dict]:
    events, seen = [], set()
    for _, lines in _pages(text):
        for i, l in enumerate(lines):
            m = LINK.match(l)
            if not m or "/exhibitions/" not in m.group(2) and "/wystawy/" not in m.group(2):
                continue
            if m.group(2).endswith(("/exhibitions/", "/wystawy/")) or m.group(2) in seen:
                continue
            nxt = lines[i + 1: i + 4]
            d_from = d_to = None
            venue, desc = "", ""
            for x in nxt:
                rng = re.match(r"^(\d{1,2} \S+ \d{4})\s*[-–]\s*(\d{1,2} \S+ \d{4})", x)
                vm = LINK.match(x)
                if vm and ("/exhibitions/" in vm.group(2) or "/wystawy/" in vm.group(2)) and "#" not in vm.group(2):
                    break  # następna wystawa
                if rng:
                    d_from, d_to = _any_date(rng.group(1)), _any_date(rng.group(2))
                elif vm and not venue and ("#exhibitions" in vm.group(2) or "/museums/" in vm.group(2) or "/muzea/" in vm.group(2)):
                    venue = vm.group(1)
                elif not x.startswith("[") and len(x) > 30 and not desc:
                    desc = x
            if not d_to:
                um = re.search(r"(?:until|do dnia|do)\s+(\d{1,2} \S+ \d{4})", desc)
                d_to = _any_date(um.group(1)) if um else None
            if not d_to or not venue:
                continue
            seen.add(m.group(2))
            events.append({
                "title": m.group(1), "date_from": (d_from or collected).isoformat(), "date_to": d_to.isoformat(),
                "venue": venue, "url": m.group(2), "description": desc[:280], "categories": ["wystawa"],
                "how": "Godziny otwarcia i bilety: sprawdź na stronie wystawy.",
            })
    return events
