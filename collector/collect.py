"""Krok 1 (na serwerze GitHub): pobierz źródła.

- jsonld / tribe  -> data/raw/<id>.json         (gotowe wydarzenia)
- snapshot        -> data/snapshots/<id>.md      (oczyszczony tekst dla AI)
- stan źródeł     -> data/collect-status.json

Migawka zmienia się tylko wtedy, gdy zmieni się treść strony, więc AI czyta
wyłącznie to, co nowe (oszczędność limitu Claude).
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .clean import html_to_text, internal_links
from .net import Fetcher
from .sources import SOURCES
from .structured import jsonld_events, tribe_events

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ = ZoneInfo("Europe/Warsaw")
MAX_PAGE_CHARS = 30000
MAX_DISCOVERED = 3


def discover(f: Fetcher, src: dict, html: str, base: str) -> list[str]:
    words = src.get("discover") or []
    if not words:
        return []
    found = []
    for label, href in internal_links(html, base):
        path = href.split("//", 1)[-1].split("/", 1)[-1].lower()
        hay = (path + " " + label.lower())
        if any(w in hay for w in words) and path.count("/") <= 2 and not re.search(r"\.(jpg|png|pdf)$", path):
            found.append(href)
    # krótsze adresy to zwykle listy, dłuższe to pojedyncze wydarzenia
    found = sorted(dict.fromkeys(found), key=lambda u: (u.count("/"), len(u)))
    return [u for u in found if u.rstrip("/") not in [p.rstrip("/") for p in src["pages"]]][:MAX_DISCOVERED]


def expand(url: str, today) -> str:
    """Podstawia pierwszy/ostatni dzień bieżącego ({m0_*}) i następnego ({m1_*}) miesiąca."""
    m0 = today.replace(day=1)
    m1 = (m0 + timedelta(days=32)).replace(day=1)
    m2 = (m1 + timedelta(days=32)).replace(day=1)
    return url.format(
        m0_start=m0.isoformat(), m0_end=(m1 - timedelta(days=1)).isoformat(),
        m1_start=m1.isoformat(), m1_end=(m2 - timedelta(days=1)).isoformat(),
        m0_mm=m0.month, m0_yyyy=m0.year, m1_mm=m1.month, m1_yyyy=m1.year,
    )


def run_source(src: dict, f: Fetcher) -> dict:
    today = datetime.now(TZ).date()
    status = {"id": src["id"], "name": src["name"], "adapter": src["adapter"], "pages": [], "ok": False}
    try:
        if src["adapter"] == "tribe":
            evs = tribe_events(f, src["pages"][0], today, today + timedelta(days=31))
            status.update(ok=bool(evs), events=len(evs))
            (DATA / "raw" / f"{src['id']}.json").write_text(json.dumps(evs, ensure_ascii=False, indent=1), encoding="utf-8")
            return status

        pages = [expand(u, today) for u in src["pages"]]
        texts, evs, links_all = [], [], []
        i = 0
        while i < len(pages):
            url = pages[i]
            r = f.get(url)
            status["pages"].append({"url": url, "ok": r is not None})
            if r is not None:
                if src["adapter"] == "jsonld":
                    evs += jsonld_events(r.text, url)
                else:
                    t = html_to_text(r.text, url)[:MAX_PAGE_CHARS]
                    texts.append(f"=== STRONA: {url}\n{t}")
                if i < len(src["pages"]):  # odkrywanie tylko ze stron startowych
                    for u in discover(f, src, r.text, url):
                        if u not in pages and len(pages) < len(src["pages"]) + MAX_DISCOVERED:
                            pages.append(u)
                    links_all += [h for _, h in internal_links(r.text, url)]
            i += 1

        if src["adapter"] == "jsonld":
            seen, uniq = set(), []
            for e in evs:
                k = (e["title"], e["start"])
                if k not in seen:
                    seen.add(k)
                    uniq.append(e)
            status.update(ok=bool(uniq), events=len(uniq))
            (DATA / "raw" / f"{src['id']}.json").write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            body = "\n\n".join(texts)
            status.update(ok=bool(body), chars=len(body), hash=hashlib.sha256(body.encode()).hexdigest()[:16])
            if body:
                (DATA / "snapshots" / f"{src['id']}.md").write_text(body + "\n", encoding="utf-8")
            (DATA / "snapshots" / f"{src['id']}.links.txt").write_text("\n".join(dict.fromkeys(links_all)) + "\n", encoding="utf-8")
    except Exception as e:  # jedno źródło nie może zatrzymać reszty
        status["error"] = f"{type(e).__name__}: {e}"[:300]
    return status


def main() -> None:
    for d in ("raw", "snapshots"):
        (DATA / d).mkdir(parents=True, exist_ok=True)
    f = Fetcher()
    prev = {}
    sp = DATA / "collect-status.json"
    if sp.exists():
        prev = {s["id"]: s for s in json.loads(sp.read_text(encoding="utf-8")).get("sources", [])}
    with ThreadPoolExecutor(max_workers=5) as ex:
        statuses = list(ex.map(lambda s: run_source(s, f), SOURCES))
    now = datetime.now(TZ).isoformat(timespec="minutes")
    for s in statuses:
        old = prev.get(s["id"], {})
        s["checked_at"] = now
        s["last_ok_at"] = now if s.get("ok") else old.get("last_ok_at")
        s["changed"] = s.get("hash") != old.get("hash") if "hash" in s else None
    sp.write_text(json.dumps({"collected_at": now, "sources": statuses}, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in statuses:
        print(f"{s['id']:12} ok={s.get('ok')} events={s.get('events', '-')} chars={s.get('chars', '-')} changed={s.get('changed')} {s.get('error', '')}")


if __name__ == "__main__":
    main()
