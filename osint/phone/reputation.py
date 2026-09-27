"""Публичные обзоры номера. Работаем только с открытыми страницами."""
import logging
import re
from typing import Optional

import httpx

from core.enums import Confidence, SourceStatus, SourceTier
from core.models import Evidence, Finding
from sources.base import extract_meta

log = logging.getLogger(__name__)


async def check_tellows(client: httpx.AsyncClient, phone_e164: str) -> Optional[Finding]:
    """tellows.com — публичная база жалоб на номера."""
    digits = phone_e164.lstrip("+")
    url = f"https://www.tellows.com/num/{digits}"
    try:
        r = await client.get(url, timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    html = r.text
    if "not found" in html.lower()[:3000] or "no entries" in html.lower()[:3000]:
        return None

    title = extract_meta(html, "og:title") or f"tellows: {phone_e164}"
    description = extract_meta(html, "og:description") or ""

    score_match = re.search(r"(\d+)\s*/\s*10", html)
    score = score_match.group(1) if score_match else None

    f = Finding(
        source="tellows.com",
        status=SourceStatus.FOUND,
        username=phone_e164,
        url=url,
        title=title,
        snippet=(description + (f" • Score: {score}/10" if score else ""))[:500],
        confidence=Confidence.LOW,
        tier=SourceTier.SEARCH_RESULT,
    )
    f.evidence.append(Evidence(
        source="tellows.com",
        url=url,
        title=title,
        claim="Публичный обзор номера на tellows",
        evidence_type="public_document",
        confidence=Confidence.LOW,
        tier=SourceTier.SEARCH_RESULT,
        snippet=f.snippet,
    ))
    return f


async def check_800notes(client: httpx.AsyncClient, phone_e164: str) -> Optional[Finding]:
    """800notes.com — публичные жалобы."""
    digits = re.sub(r"\D", "", phone_e164)
    if len(digits) > 10:
        # 800notes работает с US-номерами, но страницы бывают для любых
        pass
    url = f"https://800notes.com/Phone.aspx/{digits}"
    try:
        r = await client.get(url, timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    html = r.text
    if "no reports" in html.lower() or "not been reported" in html.lower():
        return None

    title = extract_meta(html, "og:title") or f"800notes: {phone_e164}"
    description = extract_meta(html, "og:description") or ""

    f = Finding(
        source="800notes.com",
        status=SourceStatus.FOUND,
        username=phone_e164,
        url=url,
        title=title,
        snippet=description[:500],
        confidence=Confidence.LOW,
        tier=SourceTier.SEARCH_RESULT,
    )
    f.evidence.append(Evidence(
        source="800notes.com",
        url=url,
        title=title,
        claim="Публичный отчёт о номере",
        evidence_type="public_document",
        confidence=Confidence.LOW,
        tier=SourceTier.SEARCH_RESULT,
        snippet=f.snippet,
    ))
    return f


async def check_all(client: httpx.AsyncClient, phone_e164: str):
    import asyncio
    results = await asyncio.gather(
        check_tellows(client, phone_e164),
        check_800notes(client, phone_e164),
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, Finding)]