#!/usr/bin/env python3
"""Fetch public security + AI RSS/Atom feeds into news/data/feed.json.

GitHub Pages cannot proxy third-party RSS (CORS). This script runs at build
time and on a schedule so the PWA can load a same-origin snapshot. The
browser may also try a live refresh through public CORS proxies.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "news" / "data" / "feed.json"
USER_AGENT = (
    "PulseNews/1.0 (+https://ronglinc.github.io/news/; "
    "personal security+AI news aggregator)"
)
TIMEOUT = 18
PER_SOURCE = 14

FEEDS = [
    {
        "id": "krebs",
        "name": "Krebs on Security",
        "category": "security",
        "url": "https://krebsonsecurity.com/feed/",
        "home": "https://krebsonsecurity.com/",
    },
    {
        "id": "thn",
        "name": "The Hacker News",
        "category": "security",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "home": "https://thehackernews.com/",
    },
    {
        "id": "bleeping",
        "name": "BleepingComputer",
        "category": "security",
        "url": "https://www.bleepingcomputer.com/feed/",
        "home": "https://www.bleepingcomputer.com/",
    },
    {
        "id": "cisa",
        "name": "CISA Advisories",
        "category": "security",
        "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
        "home": "https://www.cisa.gov/news-events/cybersecurity-advisories",
    },
    {
        "id": "schneier",
        "name": "Schneier on Security",
        "category": "security",
        "url": "https://www.schneier.com/feed/atom/",
        "home": "https://www.schneier.com/",
    },
    {
        "id": "project-zero",
        "name": "Google Project Zero",
        "category": "security",
        "url": "https://projectzero.google/feed.xml",
        "home": "https://googleprojectzero.blogspot.com/",
    },
    {
        "id": "openai",
        "name": "OpenAI News",
        "category": "ai",
        "url": "https://openai.com/news/rss.xml",
        "home": "https://openai.com/news/",
    },
    {
        "id": "deepmind",
        "name": "Google DeepMind",
        "category": "ai",
        "url": "https://deepmind.google/blog/rss.xml",
        "home": "https://deepmind.google/blog/",
    },
    {
        "id": "huggingface",
        "name": "Hugging Face Blog",
        "category": "ai",
        "url": "https://huggingface.co/blog/feed.xml",
        "home": "https://huggingface.co/blog",
    },
    {
        "id": "mit-ai",
        "name": "MIT News — AI",
        "category": "ai",
        "url": "https://news.mit.edu/rss/topic/artificial-intelligence2",
        "home": "https://news.mit.edu/topic/artificial-intelligence2",
    },
    {
        "id": "ars-ai",
        "name": "Ars Technica — AI",
        "category": "ai",
        "url": "https://arstechnica.com/ai/feed/",
        "home": "https://arstechnica.com/ai/",
    },
    {
        "id": "nvidia-ai",
        "name": "NVIDIA Technical Blog",
        "category": "ai",
        "url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",
        "home": "https://blogs.nvidia.com/",
    },
    {
        "id": "google-ai",
        "name": "Google AI Blog",
        "category": "ai",
        "url": "https://blog.google/technology/ai/rss/",
        "home": "https://blog.google/technology/ai/",
    },
]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self._parts).split())


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html.unescape(value))
        parser.close()
        return parser.text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node: ET.Element, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in list(node):
        if local_name(child.tag) in wanted:
            text = "".join(child.itertext()).strip()
            if text:
                return text
    return ""


def child_link(node: ET.Element) -> str:
    hrefs: list[str] = []
    for child in list(node):
        if local_name(child.tag) != "link":
            continue
        href = (child.get("href") or "").strip()
        rel = (child.get("rel") or "alternate").lower()
        text = (child.text or "").strip()
        if href:
            if rel in {"alternate", ""}:
                return href
            hrefs.append(href)
        elif text.startswith("http"):
            return text
    if hrefs:
        return hrefs[0]
    guid = child_text(node, "guid", "id")
    if guid.startswith("http"):
        return guid
    return ""


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    cleaned = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def entries_from_xml(root: ET.Element) -> list[ET.Element]:
    found: list[ET.Element] = []
    for node in root.iter():
        if local_name(node.tag) in {"item", "entry"}:
            found.append(node)
    return found


def parse_feed(xml_bytes: bytes, source: dict) -> list[dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        text = xml_bytes.decode("utf-8", errors="replace")
        start = text.find("<")
        if start < 0:
            raise
        root = ET.fromstring(text[start:].encode("utf-8"))

    items: list[dict] = []
    for entry in entries_from_xml(root)[:PER_SOURCE]:
        title = strip_html(child_text(entry, "title"))
        link = child_link(entry)
        if not title or not link.startswith("http"):
            continue
        summary = strip_html(
            child_text(entry, "description", "summary", "content", "content:encoded")
        )
        if len(summary) > 280:
            summary = summary[:277].rsplit(" ", 1)[0] + "…"
        published = parse_date(
            child_text(entry, "pubdate", "published", "updated", "date", "dc:date")
        )
        item_id = hashlib.sha1(f"{source['id']}|{link}".encode()).hexdigest()[:16]
        items.append(
            {
                "id": item_id,
                "title": title,
                "url": link,
                "sourceId": source["id"],
                "source": source["name"],
                "sourceHome": source["home"],
                "category": source["category"],
                "publishedAt": published,
                "excerpt": summary,
            }
        )
    return items


def fetch_source(source: dict) -> tuple[dict, list[dict], str | None]:
    req = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            ctype = (resp.headers.get("content-type") or "").lower()
            if "html" in ctype and b"<rss" not in body[:800].lower() and b"<feed" not in body[:800].lower():
                return source, [], f"HTML instead of feed ({resp.geturl()})"
            return source, parse_feed(body, source), None
    except Exception as exc:  # noqa: BLE001 — aggregator must keep going
        return source, [], f"{type(exc).__name__}: {exc}"


def sort_key(item: dict) -> tuple:
    stamp = item.get("publishedAt") or ""
    return (0 if stamp else 1, stamp)


def main() -> int:
    started = time.time()
    items: list[dict] = []
    status: list[dict] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch_source, source) for source in FEEDS]
        for fut in as_completed(futures):
            source, entries, error = fut.result()
            status.append(
                {
                    "id": source["id"],
                    "name": source["name"],
                    "category": source["category"],
                    "ok": error is None and bool(entries),
                    "count": len(entries),
                    "error": error,
                }
            )
            items.extend(entries)
            mark = "ok" if not error else "fail"
            print(f"[{mark}] {source['name']}: {len(entries)} items" + (f" ({error})" if error else ""))

    # Newest first; drop duplicate URLs, keeping the first (newest) occurrence.
    items.sort(key=sort_key, reverse=True)
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        key = item["url"].split("#", 1)[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "itemCount": len(unique),
        "sources": [
            {
                "id": s["id"],
                "name": s["name"],
                "category": s["category"],
                "home": s["home"],
                "feed": s["url"],
            }
            for s in FEEDS
        ],
        "sourceStatus": sorted(status, key=lambda row: row["name"].lower()),
        "items": unique,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(unique)} items to {OUT.relative_to(ROOT)} in {time.time() - started:.1f}s")
    return 0 if unique else 1


if __name__ == "__main__":
    sys.exit(main())
