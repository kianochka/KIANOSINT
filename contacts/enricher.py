from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from contacts.extractor import extract_from_text, merge
from core.models import ContactEntry, Finding, PublicContacts

log = logging.getLogger(__name__)

MAILTO_RE = re.compile(r'mailto:([^"\'>\s?]+)', re.I)
TEL_RE = re.compile(r'tel:([+\d\s\-()]{6,})', re.I)

CONTACT_PATHS = ["/contact", "/contacts", "/about", "/about-me", "/impressum", "/kontakt"]
MAX_BYTES = 200_000
FETCH_TIMEOUT = 12


async def _fetch_text(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, timeout=FETCH_TIMEOUT)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    ctype = (r.headers.get("content-type") or "").lower()
    if "html" not in ctype and "text" not in ctype:
        return None
    return r.text[:MAX_BYTES]


def _root(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


async def enrich_from_site(
    client: httpx.AsyncClient,
    base_url: str,
    source: str,
) -> PublicContacts:
    out = PublicContacts()
    if not base_url or not base_url.startswith("http"):
        return out

    root = _root(base_url)
    to_visit = [base_url, root + "/"]
    for p in CONTACT_PATHS:
        to_visit.append(root + p)

    seen_urls = set()
    for url in to_visit:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        html = await _fetch_text(client, url)
        if not html:
            continue

        for m in MAILTO_RE.findall(html):
            out = merge(out, extract_from_text(m, source, url))
        for m in TEL_RE.findall(html):
            out = merge(out, extract_from_text(m, source, url))

        text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        out = merge(out, extract_from_text(text, source, url))

    return out


async def enrich_from_keybase(
    client: httpx.AsyncClient,
    finding: Finding,
) -> PublicContacts:
    out = PublicContacts()
    proofs = (finding.extra or {}).get("proofs") or {}
    if not isinstance(proofs, dict):
        return out

    urls: List[str] = []

    def _walk(node):
        if isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)
        elif isinstance(node, str) and node.startswith("http"):
            urls.append(node)

    _walk(proofs)

    for u in urls[:5]:
        html = await _fetch_text(client, u)
        if not html:
            continue
        text = re.sub(r"<[^>]+>", " ", html)
        out = merge(out, extract_from_text(text, "Keybase proof", u))

    return out


async def enrich_from_rdap(
    client: httpx.AsyncClient,
    domain: str,
) -> PublicContacts:
    out = PublicContacts()
    domain = domain.strip().lower()
    if not domain or "." not in domain:
        return out
    try:
        r = await client.get(f"https://rdap.org/domain/{domain}", timeout=FETCH_TIMEOUT)
    except Exception:
        return out
    if r.status_code != 200:
        return out
    try:
        data = r.json()
    except Exception:
        return out

    entities = data.get("entities") or []
    for ent in entities:
        vcard = ent.get("vcardArray") or [None, []]
        if not isinstance(vcard, list) or len(vcard) < 2:
            continue
        for item in vcard[1]:
            if not isinstance(item, list) or len(item) < 4:
                continue
            kind, value = item[0], item[3]
            if kind in ("email", "tel") and isinstance(value, str):
                out = merge(
                    out,
                    extract_from_text(value, "RDAP/WHOIS", f"https://rdap.org/domain/{domain}"),
                )
    return out


async def enrich_contacts(
    client: httpx.AsyncClient,
    findings: List[Finding],
    base_contacts: PublicContacts,
) -> PublicContacts:
    out = base_contacts
    tasks = []

    site_urls = []
    for f in findings:
        if not f.is_found:
            continue
        if f.website and f.website.startswith("http") and f.website not in site_urls:
            site_urls.append((f.website, f.source))

    for url, src in site_urls[:3]:
        tasks.append(enrich_from_site(client, url, src))

    for f in findings:
        if f.is_found and f.source == "Keybase":
            tasks.append(enrich_from_keybase(client, f))

    domains_seen = set()
    for f in findings:
        if not f.is_found or not f.website:
            continue
        host = urlparse(f.website).hostname or ""
        host = host.lower().lstrip("www.")
        if host and host not in domains_seen and "." in host:
            domains_seen.add(host)
            tasks.append(enrich_from_rdap(client, host))

    if not tasks:
        return out

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, PublicContacts):
            out = merge(out, r)
        elif isinstance(r, Exception):
            log.debug("enrich task failed: %s", r)
    return out