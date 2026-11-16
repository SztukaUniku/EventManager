"""Uprzejme pobieranie stron: robots.txt, odstępy między żądaniami, limity czasu."""

from __future__ import annotations

import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

UA = "EventManagerBot/0.2 (+https://github.com/SztukaUniku/EventManager; prywatny kalendarz wydarzen)"
TIMEOUT = 30
PAUSE = 2.0  # sekundy między żądaniami do tego samego hosta


class Fetcher:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "pl,en;q=0.5"})
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self.log: list[dict] = []

    def _host(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def _wait(self, host: str) -> None:
        with self._lock:
            last = self._last.get(host, 0.0)
            now = time.monotonic()
            delay = max(0.0, last + PAUSE - now)
            self._last[host] = now + delay
        if delay:
            time.sleep(delay)

    def allowed(self, url: str) -> bool:
        host = self._host(url)
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait(host)
                r = self.s.get(host + "/robots.txt", timeout=TIMEOUT)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self._robots[host] = rp
                elif r.status_code in (401, 403):
                    self._robots[host] = "deny"  # type: ignore[assignment]
                else:
                    self._robots[host] = None
            except requests.RequestException:
                self._robots[host] = None
        rp = self._robots[host]
        if rp == "deny":
            return False
        return True if rp is None else rp.can_fetch(UA, url)

    def get(self, url: str, **kw) -> requests.Response | None:
        entry = {"url": url}
        if not self.allowed(url):
            entry["result"] = "robots"
            self.log.append(entry)
            return None
        self._wait(self._host(url))
        try:
            r = self.s.get(url, timeout=TIMEOUT, **kw)
        except requests.RequestException as e:
            entry["result"] = type(e).__name__
            self.log.append(entry)
            return None
        entry["result"] = r.status_code
        self.log.append(entry)
        if r.status_code >= 400:
            return None
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r
