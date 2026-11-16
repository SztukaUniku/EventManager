"""Krok 3: scal wydarzenia (gotowe dane + wyciągnięte przez AI), nałóż reguły, zapisz dla aplikacji.

Wejście:  data/raw/<id>.json, data/extracted/<id>.json, data/snapshots/<id>.md, data/collect-status.json
Wyjście:  app/data/events.json, app/data/excluded.json, app/data/sources.json

Zasada „zero zmyślania”: wydarzenie wyciągnięte przez AI musi mieć tytuł,
który naprawdę występuje w migawce strony. Jeśli nie – trafia do „Do sprawdzenia”.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import rules
from .sources import SOURCES
from .structured import norm_dt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "app" / "data"
TZ = ZoneInfo("Europe/Warsaw")
WINDOW_DAYS = 30
FREE_RX = re.compile(r"bezpła|wstęp wolny|wstęp bezpłat|darmow|\bfree\b|^0\s*zł|wolny wstęp", re.I)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("ł", "l")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def title_in_snapshot(title: str, snap_folded: str) -> bool:
    words = [w for w in fold(title).split() if len(w) > 3][:6]
    if not words:
        return fold(title) in snap_folded
    hits = sum(1 for w in words if w in snap_folded)
    return hits >= max(1, int(len(words) * 0.6 + 0.5))


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def normalize(src: dict, e: dict, kind: str) -> dict | None:
    title = (e.get("title") or "").strip()
    if not title:
        return None
    if e.get("date_from") or e.get("date_to"):
        d_from, d_to, t = e.get("date_from") or "", e.get("date_to") or "", None
        d = d_from
    else:
        d, t = norm_dt(e.get("start") or "")
        if not d and e.get("date"):
            d, t = e["date"], e.get("time")
        d_to = norm_dt(e.get("end") or "")[0] if e.get("end") else ""
        d_from = d
        if e.get("all_day"):
            t = None
    if not d and not d_to:
        return None
    price = (e.get("price") or "").strip()
    text = " ".join(str(x) for x in [title, e.get("description", ""), " ".join(e.get("categories") or [])])
    tags, cat = rules.classify(text)
    if e.get("category"):
        cat = e["category"]
    for t2 in e.get("tags") or []:
        if t2 not in tags:
            tags.append(t2)
    ongoing = bool(d_to and d_from and d_to > d_from and (
        "wystawa" in tags or cat == "Wystawy" or (date.fromisoformat(d_to) - date.fromisoformat(d_from)).days > 6))
    ev = {
        "title": title,
        "date": d_from or d,
        "time": t if (t and re.match(r"^\d{2}:\d{2}$", t)) else None,
        "date_to": d_to if ongoing else None,
        "ongoing": ongoing,
        "venue": (e.get("venue") or "").strip(),
        "address": (e.get("address") or "").strip(),
        "area": e.get("area") or src.get("area", ""),
        "price": price,
        "free": True if FREE_RX.search(price) else (None if not price else False),
        "how": (e.get("how") or "").strip(),
        "url": e.get("url") or "",
        "ticket_url": e.get("ticket_url") or "",
        "description": (e.get("description") or "").strip()[:300],
        "note": (e.get("note") or "").strip(),
        "category": cat if cat != "Inne" else ("Wystawy" if ongoing else "Inne"),
        "tags": tags,
        "source": src["id"],
        "source_name": src["name"],
        "via": kind,
    }
    ev["_text"] = text
    ev["id"] = hashlib.sha1(f"{src['id']}|{fold(title)}|{ev['date']}|{ev['time']}".encode()).hexdigest()[:10]
    return ev


def dedupe_key(e: dict) -> str:
    return fold(e["title"])[:48] + "|" + (e["date"] if not e["ongoing"] else "on")


def main() -> None:
    today = datetime.now(TZ).date()
    end = today + timedelta(days=WINDOW_DAYS)
    status = {s["id"]: s for s in load_json(DATA / "collect-status.json", {}).get("sources", [])}
    events, check, excluded = [], [], []
    per_source: dict[str, int] = {}

    for src in SOURCES:
        sid = src["id"]
        items: list[tuple[dict, str]] = []
        for e in load_json(DATA / "raw" / f"{sid}.json", []):
            items.append((e, "dane strukturalne"))
        snap_p = DATA / "snapshots" / f"{sid}.md"
        snap = fold(snap_p.read_text(encoding="utf-8")) if snap_p.exists() else ""
        ext = load_json(DATA / "extracted" / f"{sid}.json", {})
        for e in ext.get("events", []) if isinstance(ext, dict) else ext:
            items.append((e, "AI z migawki"))

        for raw, kind in items:
            ev = normalize(src, raw, kind)
            if not ev:
                continue
            text = ev.pop("_text")
            # zakres dat
            if ev["ongoing"]:
                if not (ev["date"] <= end.isoformat() and ev["date_to"] >= today.isoformat()):
                    continue
            elif not (today.isoformat() <= ev["date"] <= end.isoformat()):
                continue
            d = date.fromisoformat(ev["date"])
            ev["day_off"] = rules.day_off(d) if not ev["ongoing"] else None
            # wykluczenia treści (tytuł + opis, bez nazwy miejsca)
            why = rules.exclusion(text)
            if why:
                ev["excluded"] = why
                excluded.append(ev)
                continue
            # zero zmyślania: tytuł z AI musi być w migawce
            if kind == "AI z migawki" and not title_in_snapshot(ev["title"], snap):
                ev["check"] = "tytułu nie znaleziono na stronie źródła"
                check.append(ev)
                continue
            if not ev["ongoing"]:
                ok, reason = rules.time_ok(d, ev["time"])
                if not ok:
                    if ev["time"] is None:
                        ev["check"] = reason
                        check.append(ev)
                    else:
                        ev["excluded"] = reason
                        excluded.append(ev)
                    continue
            events.append(ev)
            per_source[sid] = per_source.get(sid, 0) + 1

    # deduplikacja między źródłami: zostaje pierwsze (kolejność źródeł = priorytet), reszta dopisuje się jako „też w”
    merged: dict[str, dict] = {}
    for e in events:
        k = dedupe_key(e)
        if k in merged:
            m = merged[k]
            m.setdefault("also", []).append({"source_name": e["source_name"], "url": e["url"]})
            for f in ("time", "venue", "address", "price", "ticket_url", "description", "how"):
                if not m.get(f) and e.get(f):
                    m[f] = e[f]
        else:
            merged[k] = e
    events = sorted(merged.values(), key=lambda e: (e["ongoing"], e["date"], e["time"] or "99:99", e["title"]))
    check.sort(key=lambda e: (e["date"], e["title"]))

    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ).isoformat(timespec="minutes")
    meta = {"generated_at": now, "window": {"from": today.isoformat(), "to": end.isoformat()}}
    (OUT / "events.json").write_text(json.dumps({**meta, "events": events, "check": check}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "excluded.json").write_text(json.dumps({**meta, "events": excluded}, ensure_ascii=False, indent=1), encoding="utf-8")
    srcs = []
    for src in SOURCES:
        st = status.get(src["id"], {})
        ext = load_json(DATA / "extracted" / f"{src['id']}.json", {})
        srcs.append({
            "id": src["id"], "name": src["name"], "area": src["area"], "adapter": src["adapter"],
            "url": src["pages"][0], "ok": st.get("ok"), "last_ok_at": st.get("last_ok_at"),
            "checked_at": st.get("checked_at"), "error": st.get("error"),
            "extracted_at": ext.get("extracted_at") if isinstance(ext, dict) else None,
            "events": per_source.get(src["id"], 0),
        })
    (OUT / "sources.json").write_text(json.dumps({**meta, "sources": srcs}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wydarzenia: {len(events)}, do sprawdzenia: {len(check)}, odrzucone: {len(excluded)}")
    for k, v in per_source.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
