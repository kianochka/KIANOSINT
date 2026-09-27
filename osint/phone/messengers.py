"""Проверка номера в мессенджерах."""
import logging
from typing import Optional

import httpx

from core.enums import Confidence, SourceStatus, SourceTier
from core.models import Evidence, Finding

log = logging.getLogger(__name__)


async def check_telegram(client: httpx.AsyncClient, phone_e164: str) -> Optional[Finding]:
    """t.me/+<номер> — если номер зарегистрирован, отдаёт страницу."""
    url = f"https://t.me/{phone_e164}"
    try:
        r = await client.get(url, timeout=12)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    html = r.text
    if "tgme_page_title" not in html and "tgme_page" not in html:
        return None
    from sources.base import extract_meta
    f = Finding(
        source="Telegram (phone)",
        status=SourceStatus.FOUND,
        username=phone_e164,
        url=url,
        title=extract_meta(html, "og:title") or "Telegram",
        bio=extract_meta(html, "og:description"),
        avatar=extract_meta(html, "og:image"),
        confidence=Confidence.MEDIUM,
        tier=SourceTier.DIRECT_PROFILE,
        extra={"note": "Публичная страница номера в Telegram."},
    )
    f.evidence.append(Evidence(
        source="Telegram (phone)",
        url=url,
        title=f.title,
        claim="Публичная страница номера в Telegram",
        evidence_type="phone",
        confidence=Confidence.MEDIUM,
        tier=SourceTier.DIRECT_PROFILE,
    ))
    return f


async def check_whatsapp(client: httpx.AsyncClient, phone_e164: str) -> Optional[Finding]:
    """wa.me/<номер без +> — публичное превью."""
    digits = phone_e164.lstrip("+")
    url = f"https://wa.me/{digits}"
    try:
        r = await client.get(url, timeout=12, follow_redirects=True)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    html = r.text.lower()
    if "share on whatsapp" not in html and "whatsapp" not in html:
        return None
    f = Finding(
        source="WhatsApp (public preview)",
        status=SourceStatus.FOUND,
        username=phone_e164,
        url=url,
        title="WhatsApp: номер активен",
        snippet="Страница wa.me отдала превью — номер зарегистрирован в WhatsApp.",
        confidence=Confidence.LOW,
        tier=SourceTier.PUBLIC_PAGE,
    )
    f.evidence.append(Evidence(
        source="WhatsApp (public preview)",
        url=url,
        claim="Номер зарегистрирован в WhatsApp (публичное превью)",
        evidence_type="phone",
        confidence=Confidence.LOW,
        tier=SourceTier.PUBLIC_PAGE,
    ))
    return f


async def check_all(client: httpx.AsyncClient, phone_e164: str):
    import asyncio
    results = await asyncio.gather(
        check_telegram(client, phone_e164),
        check_whatsapp(client, phone_e164),
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, Finding)]