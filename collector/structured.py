"""Źródła z gotowymi danymi: schema.org Event (JSON-LD) i API The Events Calendar."""

from __future__ import annotations

import html as htmllib
import json
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from .net import Fetcher


def _txt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        v = v[0] if v else ""
    if isinstance(v, dict):
        v = v.get("name") or v.get("@id") or ""
    s = htmllib.unescape(str(v))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _location(loc) -> tuple[str, str]:
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if isinstance(loc, str):
        return loc, ""
    if not isinstance(loc, dict):
        return "", ""
    name = _txt(loc.get("name"))
    addr = loc.get("address")
    if isinstance(addr, dict):
        parts = [addr.get("streetAddress"), addr.get("postalCode"), addr.get("addressLocality")]
        addr = ", ".join(_txt(p) for p in parts if p)
    else:
        addr = _txt(addr)
    return name, addr


def _price(offers) -> str:
    if not offers:
        return ""
    if isinstance(offers, dict):
        offers = [offers]
    prices = []
    for o in offers if isinstance(offers, list) else []:
        if not isinstance(o, dict):
            continue
        p = o.get("price") or o.get("lowPrice")
        cur = o.get("priceCurrency") or "zł"
        if p not in (None, ""):
            try:
                pv = float(str(p).replace(",", "."))
                prices.append("bezpłatne" if pv == 0 else f"{pv:g} {'zł' if cur in ('PLN', 'zł') else cur}")
            except ValueError:
                prices.append(_txt(p))
    return ", ".join(dict.fromkeys(prices))


def jsonld_events(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(isinstance(x, str) and x.endswith("Event") for x in types):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for s in soup.find_all("script", type=lambda v: v and "ld+json" in v.lower()):
        try:
            walk(json.loads(s.string or s.get_text()))
        except Exception:
            continue
    res = []
    for e in found:
        venue, addr = _location(e.get("location"))
        res.append(
            {
                "title": _txt(e.get("name")),
                "start": _txt(e.get("startDate")),
                "end": _txt(e.get("endDate")),
                "venue": venue,
                "address": addr,
                "price": _price(e.get("offers")),
                "url": _txt(e.get("url")) or page_url,
                "description": _txt(e.get("description"))[:400],
            }
        )
    return res


def tribe_events(f: Fetcher, base: str, start: date, end: date) -> list[dict]:
    """WordPress The Events Calendar REST API."""
    res = []
    page = 1
    while page <= 10:
        url = (
            f"{base.rstrip('/')}/wp-json/tribe/events/v1/events?per_page=50&page={page}"
            f"&start_date={start.isoformat()}&end_date={end.isoformat()} 23:59:59"
        )
        r = f.get(url)
        if r is None:
            break
        try:
            data = r.json()
        except ValueError:
            break
        for e in data.get("events", []):
            v = e.get("venue") or {}
            if isinstance(v, list):
                v = v[0] if v else {}
            addr = ", ".join(x for x in [v.get("address"), v.get("zip"), v.get("city")] if x)
            cost = _txt(e.get("cost"))
            if not cost and e.get("cost_details", {}).get("values") == ["0"]:
                cost = "bezpłatne"
            res.append(
                {
                    "title": _txt(e.get("title")),
                    "start": (e.get("start_date") or "").replace(" ", "T")[:16],
                    "end": (e.get("end_date") or "").replace(" ", "T")[:16],
                    "all_day": bool(e.get("all_day")),
                    "venue": _txt(v.get("venue")),
                    "address": addr,
                    "price": cost,
                    "url": e.get("url") or "",
                    "ticket_url": e.get("website") or "",
                    "description": _txt(e.get("excerpt") or e.get("description"))[:400],
                    "categories": [_txt(c.get("name")) for c in e.get("categories", []) if isinstance(c, dict)],
                }
            )
        if not data.get("next_rest_url"):
            break
        page += 1
    return res


def norm_dt(s: str) -> tuple[str, str | None]:
    """Zwraca (data YYYY-MM-DD, godzina HH:MM lub None) z napisu ISO."""
    s = (s or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", s)
    if not m:
        return "", None
    d, t = m.group(1), m.group(2)
    # JSON-LD w UTC (końcówka Z) przeliczamy na czas warszawski
    if t and s.endswith("Z"):
        try:
            from zoneinfo import ZoneInfo

            dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Warsaw"))
            d, t = dt.date().isoformat(), dt.strftime("%H:%M")
        except Exception:
            pass
    if t == "00:00":  # północ zwykle oznacza „godzina nieznana”
        t = None
    return d, t
