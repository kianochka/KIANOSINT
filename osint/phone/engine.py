import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import phonenumbers
from phonenumbers import geocoder, carrier, timezone as pn_timezone, number_type, PhoneNumberType

from contacts.extractor import extract_from_finding, merge
from core.config import settings
from core.enums import (
    Confidence, EvidenceType, SearchType, SourceStatus, SourceTier,
)
from core.models import (
    Evidence, Finding, PublicContacts, ScanResult, SearchStats,
)
from evidence.engine import EvidenceEngine
from osint.phone import messengers, reputation
from sources.base import make_client
from sources.web_search import web_search_multi, numverify_lookup

log = logging.getLogger(__name__)

ProgressCb = Callable[[int, int, str], Awaitable[None]]


TYPE_MAP = {
    PhoneNumberType.MOBILE: "мобильный",
    PhoneNumberType.FIXED_LINE: "городской",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "городской/мобильный",
    PhoneNumberType.TOLL_FREE: "бесплатный",
    PhoneNumberType.PREMIUM_RATE: "премиум",
    PhoneNumberType.SHARED_COST: "shared cost",
    PhoneNumberType.VOIP: "VoIP",
    PhoneNumberType.PERSONAL_NUMBER: "персональный",
    PhoneNumberType.PAGER: "пейджер",
    PhoneNumberType.UAN: "UAN",
    PhoneNumberType.VOICEMAIL: "голосовая почта",
    PhoneNumberType.UNKNOWN: "неизвестный",
}


def normalize_phone(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        parsed = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def phone_meta(e164: str) -> dict:
    try:
        parsed = phonenumbers.parse(e164, None)
    except phonenumbers.NumberParseException:
        return {}

    country = geocoder.country_name_for_number(parsed, "ru") or geocoder.country_name_for_number(parsed, "en")
    location = (
        geocoder.description_for_number(parsed, "ru")
        or geocoder.description_for_number(parsed, "en")
    )
    operator = (
        carrier.name_for_number(parsed, "ru")
        or carrier.name_for_number(parsed, "en")
    )
    tzs = list(pn_timezone.time_zones_for_number(parsed))

    return {
        "country_code": parsed.country_code,
        "country": country or "—",
        "location": location or "—",
        "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
        "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "carrier": operator or "—",
        "timezones": tzs,
        "type": TYPE_MAP.get(number_type(parsed), "неизвестный"),
        "is_valid": phonenumbers.is_valid_number(parsed),
    }


class PhoneScanner:
    def __init__(self) -> None:
        pass

    async def scan(self, raw_phone: str, on_progress: Optional[ProgressCb] = None) -> ScanResult:
        started = time.perf_counter()
        e164 = normalize_phone(raw_phone)
        stats = SearchStats()
        findings = []
        ev_engine = EvidenceEngine()
        contacts = PublicContacts()

        if e164 is None:
            stats.finished_at = datetime.now(timezone.utc)
            return ScanResult(
                target_type=SearchType.PHONE, target_value=raw_phone,
                stats=stats, findings=[], evidence=[], contacts=contacts,
                correlations=[],
            )

        meta = phone_meta(e164)

        base = Finding(
            source="PhoneInfo", status=SourceStatus.FOUND, username=e164,
            url=None, title=meta.get("international") or e164,
            snippet="{} • {} • {}".format(
                meta.get("country", ""), meta.get("carrier", ""), meta.get("type", "")
            ),
            confidence=Confidence.HIGH, tier=SourceTier.DIRECT_PROFILE,
            extra=meta,
        )
        base.evidence.append(Evidence(
            source="PhoneInfo", url="phone://{}".format(e164), title=e164,
            claim="Номер разобран и подтверждён библиотекой phonenumbers",
            evidence_type=EvidenceType.PHONE, confidence=Confidence.HIGH,
            tier=SourceTier.DIRECT_PROFILE, snippet=str(meta),
        ))
        findings.append(base)
        ev_engine.add_finding(base)

        queries = [
            '"{}"'.format(e164),
            '"{}"'.format(meta.get("national", "")),
            '"{}" telegram'.format(e164),
            '"{}" email'.format(e164),
            '"{}" whatsapp'.format(e164),
        ]
        queries = [q for q in queries if q.strip('"').strip()]

        total_steps = len(queries) + 3
        done = 0

        async with make_client() as client:
            brave_key = getattr(settings, "brave_api_key", "") or ""
            for q in queries:
                results = await web_search_multi(client, q, limit=10, brave_key=brave_key or None)
                done += 1
                if on_progress:
                    try:
                        await on_progress(done, total_steps, "Web Search")
                    except Exception:
                        pass

                for item in results:
                    url = item.get("url")
                    title = item.get("title") or ""
                    snippet = item.get("snippet") or ""
                    if not url:
                        continue
                    digits = e164.replace("+", "")
                    blob = (title + " " + snippet).replace(" ", "").replace("-", "")
                    if digits not in blob and e164 not in (title + snippet):
                        continue
                    engine = item.get("engine") or "Web"
                    f = Finding(
                        source=engine, status=SourceStatus.FOUND, username=e164,
                        url=url, title=title, snippet=snippet,
                        confidence=Confidence.LOW, tier=SourceTier.SEARCH_RESULT,
                    )
                    f.evidence.append(Evidence(
                        source=engine, url=url, title=title,
                        claim="Публичное упоминание номера",
                        evidence_type=EvidenceType.SEARCH_RESULT,
                        confidence=Confidence.LOW, tier=SourceTier.SEARCH_RESULT,
                        snippet=snippet, extra={"query": q},
                    ))
                    findings.append(f)
                    ev_engine.add_finding(f)
                    contacts = merge(contacts, extract_from_finding(f))

            try:
                ms = await messengers.check_all(client, e164)
                for f in ms:
                    findings.append(f)
                    ev_engine.add_finding(f)
            except Exception as e:
                log.debug("messengers failed: %s", e)
            done += 1
            if on_progress:
                try:
                    await on_progress(done, total_steps, "Messengers")
                except Exception:
                    pass

            try:
                rp = await reputation.check_all(client, e164)
                for f in rp:
                    findings.append(f)
                    ev_engine.add_finding(f)
            except Exception as e:
                log.debug("reputation failed: %s", e)
            done += 1
            if on_progress:
                try:
                    await on_progress(done, total_steps, "Reputation")
                except Exception:
                    pass

            done += 1
            if on_progress:
                try:
                    await on_progress(done, total_steps, "Finalize")
                except Exception:
                    pass

        seen = set()
        unique = []
        for f in findings:
            key = (f.url or "phone://" + e164).rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(f)
        findings = unique

        stats.sources_configured = total_steps
        stats.sources_checked = total_steps
        stats.found = sum(1 for f in findings if f.is_found)
        stats.not_found = 0
        stats.errors = 0
        stats.unavailable = 0
        stats.finished_at = datetime.now(timezone.utc)

        log.info(
            "phone scan done number=%s queries=%d findings=%d dur=%.2fs",
            e164, len(queries), stats.found, time.perf_counter() - started,
        )

        return ScanResult(
            target_type=SearchType.PHONE, target_value=e164,
            stats=stats, findings=findings, evidence=ev_engine.all(),
            contacts=contacts, correlations=[],
        )