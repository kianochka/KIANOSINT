import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from contacts.enricher import enrich_contacts
from contacts.extractor import extract_from_finding, merge
from core.config import settings
from core.enums import SearchType, SourceStatus
from core.models import PublicContacts, ScanResult, SearchStats
from correlation.engine import CorrelationEngine
from evidence.engine import EvidenceEngine
from sources.base import make_client
from sources.registry import registry

log = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[a-z0-9._\-]{2,64}$", re.I)


def normalize_username(raw: str) -> str:
    v = raw.strip().lstrip("@").strip()
    m = re.search(
        r"(?:t\.me/|twitter\.com/|x\.com/|instagram\.com/|github\.com/)([^/?#\s]+)",
        v,
    )
    if m:
        v = m.group(1)
    return v.lower()


def validate_username(u: str) -> bool:
    return bool(USERNAME_RE.match(u))


ProgressCb = Callable[[int, int, str], Awaitable[None]]


class UsernameScanner:
    def __init__(self, semaphore_size: Optional[int] = None) -> None:
        self.sem = asyncio.Semaphore(semaphore_size or settings.max_concurrent_sources)

    async def scan(
        self,
        username: str,
        on_progress: Optional[ProgressCb] = None,
    ) -> ScanResult:
        sources = registry.all()
        total = len(sources)
        stats = SearchStats(sources_configured=total)
        started = time.perf_counter()
        findings = []
        ev_engine = EvidenceEngine()
        contacts = None
        done = 0

        async with make_client() as client:
            async def run_one(src):
                nonlocal done
                async with self.sem:
                    f = await src.run(client, username)
                done += 1
                if on_progress is not None:
                    try:
                        await on_progress(done, total, src.name)
                    except Exception:
                        pass
                return f

            results = await asyncio.gather(*(run_one(s) for s in sources))

            for f in results:
                findings.append(f)
                if f.status == SourceStatus.FOUND:
                    stats.found += 1
                    stats.sources_checked += 1
                elif f.status == SourceStatus.NOT_FOUND:
                    stats.not_found += 1
                    stats.sources_checked += 1
                elif f.status == SourceStatus.NOT_CONFIGURED:
                    stats.unavailable += 1
                else:
                    stats.errors += 1
                    stats.sources_checked += 1
                ev_engine.add_finding(f)
                if f.is_found:
                    c = extract_from_finding(f)
                    contacts = c if contacts is None else merge(contacts, c)

            contacts = contacts or PublicContacts()

            try:
                contacts = await enrich_contacts(client, findings, contacts)
            except Exception as e:
                log.warning("enrich failed: %s", e)

        # Запись health — не блокирует, ошибки глотаем
        try:
            from database.session import SessionLocal
            from database.repos import record_source_health
            async with SessionLocal() as hsession:
                for f in results:
                    ok = f.status in (SourceStatus.FOUND, SourceStatus.NOT_FOUND)
                    timed_out = f.status == SourceStatus.TIMEOUT
                    await record_source_health(
                        hsession,
                        f.source,
                        ok=ok,
                        timed_out=timed_out,
                        duration_ms=f.duration_ms or 0,
                    )
        except Exception as e:
            log.debug("health write failed: %s", e)

        correlations = CorrelationEngine(username).analyze(findings)
        stats.finished_at = datetime.now(timezone.utc)

        result = ScanResult(
            target_type=SearchType.USERNAME,
            target_value=username,
            stats=stats,
            findings=findings,
            evidence=ev_engine.all(),
            contacts=contacts,
            correlations=correlations,
        )
        log.info(
            "scan done user=%s checked=%d found=%d errors=%d emails=%d phones=%d sites=%d dur=%.2fs",
            username,
            stats.sources_checked,
            stats.found,
            stats.errors,
            len(contacts.emails),
            len(contacts.phones),
            len(contacts.websites),
            time.perf_counter() - started,
        )
        return result