"""Zamiana strony HTML na zwarty tekst z linkami (do odczytu przez AI)."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

DROP = ["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header"]
BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "article", "section", "br", "dt", "dd", "time"}


def html_to_text(html: str, base_url: str, keep_header: bool = False) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(DROP if not keep_header else [t for t in DROP if t not in ("header", "nav")]):
        tag.decompose()
    for el in soup.select('[class*="cookie"], [id*="cookie"], [class*="menu"], [id*="menu"]'):
        el.decompose()
    host = urlparse(base_url).netloc
    out: list[str] = []

    def walk(node):
        for ch in node.children:
            if isinstance(ch, NavigableString):
                t = str(ch)
                if t.strip():
                    out.append(re.sub(r"\s+", " ", t))
            elif isinstance(ch, Tag):
                if ch.name == "a" and ch.get("href"):
                    label = re.sub(r"\s+", " ", ch.get_text(" ", strip=True))
                    href = urljoin(base_url, ch["href"])
                    if label and urlparse(href).netloc.endswith(host.replace("www.", "")) and href.rstrip("/") != base_url.rstrip("/"):
                        out.append(f" [{label}]({href}) ")
                    elif label:
                        out.append(" " + label + " ")
                    continue
                if ch.name == "img" and ch.get("alt"):
                    continue
                if ch.name in BLOCK:
                    out.append("\n")
                walk(ch)
                if ch.name in BLOCK:
                    out.append("\n")

    walk(soup.body or soup)
    text = "".join(out)
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    res: list[str] = []
    for l in lines:
        if not l:
            continue
        if res and res[-1] == l:
            continue
        res.append(l)
    return "\n".join(res)


def internal_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base_url).netloc.replace("www.", "")
    seen, res = set(), []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        if urlparse(href).netloc.replace("www.", "") != host or href in seen:
            continue
        seen.add(href)
        res.append((re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:80], href))
    return res
