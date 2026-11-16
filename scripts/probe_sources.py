"""Test wykonalności źródeł EventManagera.

Dla każdego źródła z sources/sources.csv sprawdza, w uprzejmy sposób
(kilka żądań na stronę, odstępy, poszanowanie robots.txt):
  * czy robots.txt pozwala odczytać stronę główną,
  * czy strona odpowiada i ile ma czytelnego tekstu (strony renderowane
    w JavaScripcie mają go bardzo mało),
  * czy są kanały maszynowe: RSS/Atom, iCal (.ics), dane strukturalne
    schema.org Event (JSON-LD), API wtyczki The Events Calendar (WordPress).

Wynik: reports/source-probe.json i reports/source-probe.md
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources" / "sources.csv"
OUT_DIR = ROOT / "reports"
UA = "EventManagerBot/0.1 (+https://github.com/SztukaUniku/EventManager; prywatny kalendarz wydarzen)"
TIMEOUT = 25
PAUSE = 1.5  # sekundy między żądaniami do tej samej strony


class PageScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.feeds: list[str] = []
        self.ics: list[str] = []
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript"):
            if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._in_jsonld = True
            else:
                self._skip += 1
        if tag == "link" and (a.get("type") or "").lower() in (
            "application/rss+xml",
            "application/atom+xml",
            "text/calendar",
        ):
            href = a.get("href")
            if href:
                (self.ics if "calendar" in a["type"].lower() else self.feeds).append(href)
        if tag == "a":
            href = a.get("href") or ""
            low = href.lower()
            if low.endswith(".ics") or "ical" in low or "webcal:" in low or "outlook-ical" in low:
                self.ics.append(href)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
        elif tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld.append(data)
        elif not self._skip:
            t = data.strip()
            if t:
                self.text_parts.append(t)


DATE_RX = re.compile(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b|\b\d{1,2}\s+(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|wrze[sś]nia|pa[zź]dziernika|listopada|grudnia)\b", re.I)
TIME_RX = re.compile(r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d\b")


def count_jsonld_events(blobs: list[str]) -> int:
    n = 0
    def walk(o):
        nonlocal n
        if isinstance(o, dict):
            t = o.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(isinstance(x, str) and x.endswith("Event") for x in types):
                n += 1
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    for b in blobs:
        try:
            walk(json.loads(b))
        except Exception:
            continue
    return n


def get(session: requests.Session, url: str):
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        return r, None
    except requests.RequestException as e:
        return None, type(e).__name__ + ": " + str(e)[:160]


def probe(row: dict) -> dict:
    url = row["url"]
    res = {**row, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "pl,en;q=0.5"})

    # robots.txt
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    rp = urllib.robotparser.RobotFileParser()
    r, err = get(s, base + "/robots.txt")
    if r is not None and r.status_code == 200:
        rp.parse(r.text.splitlines())
        res["robots"] = "allow" if rp.can_fetch(UA, url) else "disallow"
    elif r is not None and r.status_code in (401, 403):
        res["robots"] = "blocked-robots-file"
    else:
        rp = None
        res["robots"] = "none"
    if res["robots"] in ("disallow", "blocked-robots-file"):
        res["verdict"] = "zakaz w robots.txt"
        return res
    time.sleep(PAUSE)

    r, err = get(s, url)
    if r is None:
        res.update(status=None, error=err, verdict="brak odpowiedzi")
        return res
    res["status"] = r.status_code
    res["final_url"] = r.url
    if r.status_code >= 400:
        res["verdict"] = f"błąd HTTP {r.status_code}"
        body = r.text[:3000].lower()
        if "cloudflare" in body or "captcha" in body or "challenge" in body:
            res["verdict"] += " (ochrona antybotowa)"
        return res

    html = r.text
    scan = PageScan()
    try:
        scan.feed(html)
    except Exception:
        pass
    text = " ".join(scan.text_parts)
    res["text_chars"] = len(text)
    res["dates_found"] = len(DATE_RX.findall(text))
    res["times_found"] = len(TIME_RX.findall(text))
    res["jsonld_events"] = count_jsonld_events(scan.jsonld)
    res["feeds"] = sorted({urljoin(r.url, f) for f in scan.feeds})[:5]
    res["ics"] = sorted({urljoin(r.url, f) for f in scan.ics})[:5]
    res["wordpress"] = "wp-content" in html or "wp-json" in html

    # API wtyczki The Events Calendar (częsta w domach kultury na WordPressie)
    res["tribe_api_events"] = None
    if res["wordpress"]:
        api = base + "/wp-json/tribe/events/v1/events?per_page=5"
        if rp is None or rp.can_fetch(UA, api):
            time.sleep(PAUSE)
            ra, _ = get(s, api)
            if ra is not None and ra.status_code == 200:
                try:
                    res["tribe_api_events"] = len(ra.json().get("events", []))
                except Exception:
                    pass

    # Werdykt
    if res["tribe_api_events"]:
        v = "API kalendarza (najlepiej)"
    elif res["jsonld_events"]:
        v = "dane strukturalne Event (bardzo dobrze)"
    elif res["ics"]:
        v = "kalendarz iCal (dobrze)"
    elif res["text_chars"] < 800:
        v = "mało tekstu, prawdopodobnie JavaScript (wymaga przeglądarki)"
    elif res["dates_found"] >= 5:
        v = "zwykła strona z datami (czytelna, potrzebny parser lub AI)"
    else:
        v = "czytelna, ale mało dat na stronie głównej (program głębiej)"
    if res["feeds"] and "API" not in v:
        v += "; ma RSS"
    res["verdict"] = v
    return res


def main() -> None:
    rows = list(csv.DictReader(SOURCES.open(encoding="utf-8")))
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(probe, rows))
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "source-probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Test wykonalności źródeł",
        "",
        f"Wykonano: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC z serwera GitHub Actions.",
        "",
        "| Źródło | Grupa | Werdykt | robots | HTTP | znaki tekstu | daty | godziny | Event JSON-LD |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for x in results:
        lines.append(
            f"| [{x['name']}]({x['url']}) | {x['group']} | {x.get('verdict','')} | {x.get('robots','')} | "
            f"{x.get('status','')} | {x.get('text_chars','')} | {x.get('dates_found','')} | "
            f"{x.get('times_found','')} | {x.get('jsonld_events','')} |"
        )
    (OUT_DIR / "source-probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
