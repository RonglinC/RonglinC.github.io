#!/usr/bin/env python3
"""Fetch public security, cloud, Azure, endpoint, vuln, finance, and AI RSS/Atom feeds.

Writes news/data/feed.json for GitHub Pages (no CORS). Also extracts CVEs, vendors,
and topics so the PWA can draw related-story links.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
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
    "QingqingNews/1.1 (+https://ronglinc.github.io/news/; "
    "personal security news aggregator for detection engineers)"
)
TIMEOUT = 18
PER_SOURCE = 8

FEEDS = [
    # Core security
    {"id": "krebs", "name": "Krebs on Security", "category": "security", "topics": ["finance"], "url": "https://krebsonsecurity.com/feed/", "home": "https://krebsonsecurity.com/"},
    {"id": "thn", "name": "The Hacker News", "category": "security", "topics": [], "url": "https://feeds.feedburner.com/TheHackersNews", "home": "https://thehackernews.com/"},
    {"id": "bleeping", "name": "BleepingComputer", "category": "security", "topics": ["vuln", "endpoint"], "url": "https://www.bleepingcomputer.com/feed/", "home": "https://www.bleepingcomputer.com/"},
    {"id": "schneier", "name": "Schneier on Security", "category": "security", "topics": [], "url": "https://www.schneier.com/feed/atom/", "home": "https://www.schneier.com/"},
    {"id": "darkreading", "name": "Dark Reading", "category": "security", "topics": [], "url": "https://www.darkreading.com/rss.xml", "home": "https://www.darkreading.com/"},
    {"id": "securityweek", "name": "SecurityWeek", "category": "security", "topics": ["vuln"], "url": "https://www.securityweek.com/feed/", "home": "https://www.securityweek.com/"},
    {"id": "infosecmag", "name": "Infosecurity Magazine", "category": "security", "topics": ["finance"], "url": "https://www.infosecurity-magazine.com/rss/news/", "home": "https://www.infosecurity-magazine.com/"},
    {"id": "unit42", "name": "Palo Alto Unit 42", "category": "security", "topics": ["endpoint"], "url": "https://unit42.paloaltonetworks.com/feed/", "home": "https://unit42.paloaltonetworks.com/"},
    {"id": "talos", "name": "Cisco Talos", "category": "security", "topics": ["vuln", "endpoint"], "url": "https://blog.talosintelligence.com/rss/", "home": "https://blog.talosintelligence.com/"},
    # Vulnerabilities
    {"id": "cisa", "name": "CISA Advisories", "category": "vuln", "topics": ["security"], "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml", "home": "https://www.cisa.gov/news-events/cybersecurity-advisories"},
    {"id": "project-zero", "name": "Google Project Zero", "category": "vuln", "topics": ["security"], "url": "https://projectzero.google/feed.xml", "home": "https://googleprojectzero.blogspot.com/"},
    {"id": "zdi", "name": "Zero Day Initiative", "category": "vuln", "topics": [], "url": "https://www.zerodayinitiative.com/rss/published/", "home": "https://www.zerodayinitiative.com/"},
    {"id": "rapid7", "name": "Rapid7 Blog", "category": "vuln", "topics": [], "url": "https://www.rapid7.com/rss.xml", "home": "https://www.rapid7.com/blog/"},
    {"id": "tenable", "name": "Tenable Blog", "category": "vuln", "topics": [], "url": "https://www.tenable.com/blog/feed", "home": "https://www.tenable.com/blog"},
    {"id": "msrc", "name": "Microsoft Update Guide", "category": "vuln", "topics": ["azure"], "url": "https://api.msrc.microsoft.com/update-guide/rss", "home": "https://msrc.microsoft.com/update-guide/"},
    # Cloud
    {"id": "aws-sec", "name": "AWS Security Blog", "category": "cloud", "topics": [], "url": "https://aws.amazon.com/blogs/security/feed/", "home": "https://aws.amazon.com/blogs/security/"},
    {"id": "gcp-blog", "name": "Google Cloud Blog", "category": "cloud", "topics": [], "url": "https://cloudblog.withgoogle.com/rss/", "home": "https://cloud.google.com/blog/"},
    {"id": "wiz", "name": "Wiz Blog", "category": "cloud", "topics": ["vuln"], "url": "https://www.wiz.io/feed/rss.xml", "home": "https://www.wiz.io/blog"},
    {"id": "datadog-sec", "name": "Datadog Security Labs", "category": "cloud", "topics": ["detection"], "url": "https://securitylabs.datadoghq.com/rss/feed.xml", "home": "https://securitylabs.datadoghq.com/"},
    {"id": "cloudflare-sec", "name": "Cloudflare Security", "category": "cloud", "topics": [], "url": "https://blog.cloudflare.com/tag/security/rss/", "home": "https://blog.cloudflare.com/tag/security/"},
    {"id": "okta-sec", "name": "Okta Security", "category": "cloud", "topics": ["identity"], "url": "https://sec.okta.com/rss.xml", "home": "https://sec.okta.com/"},
    # Azure
    {"id": "ms-security", "name": "Microsoft Security Blog", "category": "azure", "topics": ["endpoint", "cloud"], "url": "https://www.microsoft.com/en-us/security/blog/feed/", "home": "https://www.microsoft.com/en-us/security/blog/"},
    {"id": "azure-blog", "name": "Azure Blog", "category": "azure", "topics": ["cloud"], "url": "https://azure.microsoft.com/en-us/blog/feed/", "home": "https://azure.microsoft.com/en-us/blog/"},
    # Endpoint
    {"id": "crowdstrike", "name": "CrowdStrike Blog", "category": "endpoint", "topics": ["detection"], "url": "https://www.crowdstrike.com/en-us/blog/feed", "home": "https://www.crowdstrike.com/en-us/blog/"},
    {"id": "sentinelone", "name": "SentinelOne Blog", "category": "endpoint", "topics": ["detection"], "url": "https://www.sentinelone.com/blog/feed/", "home": "https://www.sentinelone.com/blog/"},
    {"id": "malwarebytes", "name": "Malwarebytes Labs", "category": "endpoint", "topics": [], "url": "https://www.malwarebytes.com/blog/feed/index.xml", "home": "https://www.malwarebytes.com/blog/"},
    {"id": "elastic-sec", "name": "Elastic Security Labs", "category": "endpoint", "topics": ["detection"], "url": "https://www.elastic.co/security-labs/rss/feed.xml", "home": "https://www.elastic.co/security-labs/"},
    # AI
    {"id": "openai", "name": "OpenAI News", "category": "ai", "topics": [], "url": "https://openai.com/news/rss.xml", "home": "https://openai.com/news/"},
    {"id": "deepmind", "name": "Google DeepMind", "category": "ai", "topics": [], "url": "https://deepmind.google/blog/rss.xml", "home": "https://deepmind.google/blog/"},
    {"id": "huggingface", "name": "Hugging Face Blog", "category": "ai", "topics": [], "url": "https://huggingface.co/blog/feed.xml", "home": "https://huggingface.co/blog"},
    {"id": "mit-ai", "name": "MIT News — AI", "category": "ai", "topics": [], "url": "https://news.mit.edu/rss/topic/artificial-intelligence2", "home": "https://news.mit.edu/topic/artificial-intelligence2"},
    {"id": "ars-ai", "name": "Ars Technica — AI", "category": "ai", "topics": [], "url": "https://arstechnica.com/ai/feed/", "home": "https://arstechnica.com/ai/"},
    {"id": "nvidia-ai", "name": "NVIDIA Technical Blog", "category": "ai", "topics": [], "url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/", "home": "https://blogs.nvidia.com/"},
    {"id": "google-ai", "name": "Google AI Blog", "category": "ai", "topics": [], "url": "https://blog.google/technology/ai/rss/", "home": "https://blog.google/technology/ai/"},
]

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.I)

VENDOR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Microsoft", re.compile(r"\b(microsoft|azure|entra|defender|windows|m365|office 365|active directory|activedirectory)\b", re.I)),
    ("Amazon Web Services", re.compile(r"\b(aws|amazon web services|amazon s3)\b", re.I)),
    ("Google", re.compile(r"\b(google cloud|gcp|google chrome|android)\b", re.I)),
    ("CrowdStrike", re.compile(r"\bcrowdstrike\b|\bfalcon\b", re.I)),
    ("SentinelOne", re.compile(r"\bsentinelone\b", re.I)),
    ("Palo Alto Networks", re.compile(r"\bpalo alto\b|\bunit 42\b|\bprisma cloud\b", re.I)),
    ("Cisco", re.compile(r"\bcisco\b|\btalos\b", re.I)),
    ("Fortinet", re.compile(r"\bfortinet\b|\bfortigate\b", re.I)),
    ("Okta", re.compile(r"\bokta\b", re.I)),
    ("Cloudflare", re.compile(r"\bcloudflare\b", re.I)),
    ("Apple", re.compile(r"\b(apple|ios|macos|iphone)\b", re.I)),
    ("Linux", re.compile(r"\b(linux|kernel)\b", re.I)),
    ("Kubernetes", re.compile(r"\b(kubernetes|k8s)\b", re.I)),
    ("GitHub", re.compile(r"\bgithub\b", re.I)),
    ("OpenAI", re.compile(r"\bopenai\b|\bchatgpt\b", re.I)),
    ("Ivanti", re.compile(r"\bivanti\b", re.I)),
    ("Citrix", re.compile(r"\bcitrix\b|\bnetscaler\b", re.I)),
    ("VMware", re.compile(r"\bvmware\b", re.I)),
    ("Okta", re.compile(r"\bokta\b", re.I)),
    ("Snowflake", re.compile(r"\bsnowflake\b", re.I)),
    ("Wiz", re.compile(r"\bwiz\b", re.I)),
    ("Elastic", re.compile(r"\belastic(search)?\b", re.I)),
    ("Splunk", re.compile(r"\bsplunk\b", re.I)),
]

TOPIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("vuln", re.compile(r"\b(cve-\d{4}-\d+|vulnerabilit|zero-?day|n-day|rce|remote code|advisory|patch tuesday|exploit)\b", re.I)),
    ("ransomware", re.compile(r"\bransomware\b|\bextortion\b", re.I)),
    ("phishing", re.compile(r"\bphish|\bbeef\b|\bcredential theft\b", re.I)),
    ("endpoint", re.compile(r"\b(edr|xdr|endpoint|malware|trojan|backdoor|loader)\b", re.I)),
    ("cloud", re.compile(r"\b(cloud|aws|gcp|kubernetes|container|s3 bucket)\b", re.I)),
    ("azure", re.compile(r"\b(azure|entra|m365|office 365|active directory)\b", re.I)),
    ("finance", re.compile(r"\b(bank|banking|swift|atm|payment card|pci|fintech|wire fraud|ach)\b", re.I)),
    ("identity", re.compile(r"\b(identity|iam|mfa|sso|okta|entra id)\b", re.I)),
    ("detection", re.compile(r"\b(detection|siem|sigma|yara|telemetry|hunt)\b", re.I)),
    ("ai", re.compile(r"\b(llm|generative ai|machine learning|chatgpt|openai|model)\b", re.I)),
]


def extract_signals(title: str, excerpt: str, source: dict) -> dict:
    text = f"{title} {excerpt}"
    cves = sorted({match.group(0).upper() for match in CVE_RE.finditer(text)})
    vendors: list[str] = []
    seen_v: set[str] = set()
    for name, pattern in VENDOR_PATTERNS:
        if name not in seen_v and pattern.search(text):
            vendors.append(name)
            seen_v.add(name)
    topics: list[str] = []
    seen_t: set[str] = set()
    for topic in [source.get("category"), *(source.get("topics") or [])]:
        if topic and topic not in seen_t:
            topics.append(topic)
            seen_t.add(topic)
    for name, pattern in TOPIC_PATTERNS:
        if name not in seen_t and pattern.search(text):
            topics.append(name)
            seen_t.add(name)
    return {"cves": cves, "vendors": vendors, "topics": topics}


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
        signals = extract_signals(title, summary, source)
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
                **signals,
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

    with ThreadPoolExecutor(max_workers=10) as pool:
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
