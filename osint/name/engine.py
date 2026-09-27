import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, List, Optional

from contacts.extractor import extract_from_finding, merge
from core.config import settings
from core.enums import (
    Confidence, EvidenceType, SearchType, SourceStatus, SourceTier,
)
from core.models import (
    Evidence, Finding, PublicContacts, ScanResult, SearchStats,
)
from evidence.engine import EvidenceEngine
from sources.base import make_client
from sources.web_search import web_search

log = logging.getLogger(__name__)

ProgressCb = Callable[[int, int, str], Awaitable[None]]


def normalize_name(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip())


def parse_name_input(raw: str):
    """'Ivan Petrov, Moscow, Russia' -> ('Ivan Petrov', 'Moscow, Russia')."""
    raw = normalize_name(raw)
    if not raw:
        return "", ""
    parts = [p.strip() for p in raw.split(",")]
    name = parts[0]
    context = ", ".join(p for p in parts[1:] if p)
    return name, context


class NameScanner:
    def __init__(self) -> None:
        pass

    def _build_queries(self, name: str, context: str) -> List[str]:
        base = '"{}"'.format(name)
        queries = [
            base,
            base + " telegram",
            base + " vk",
            base + " github",
            base + " linkedin",
            base + " instagram",
            base + " email",
            base + " резюме",
        ]
        if context:
            queries = [q + " " + context for q in queries[:5]] + queries[5:]

        seen = set()
        out = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                out.append(q)
        return out

    async def scan(
        self,
        raw_input: str,
        on_progress: Optional[ProgressCb] = None,
    ) -> ScanResult:
        started = time.perf_counter()
        name, context = parse_name_input(raw_input)
        stats = SearchStats()
        findings: List[Finding] = []
        ev_engine = EvidenceEngine()
        contacts = PublicContacts()

        if not name:
            stats.finished_at = datetime.now(timezone.utc)
            return ScanResult(
                target_type=SearchType.NAME, target_value=raw_input,
                stats=stats, findings=[], evidence=[], contacts=contacts,
                correlations=[],
            )

        queries = self._build_queries(name, context)
        total = len(queries)
        done = 0

        async with make_client() as client:
            for q in queries:
                results = await web_search(client, q, limit=10)
                done += 1
                if on_progress:
                    try:
                        await on_progress(done, total, "DuckDuckGo")
                    except Exception:
                        pass

                for item in results:
                    url = item.get("url")
                    title = item.get("title") or ""
                    snippet = item.get("snippet") or ""
                    if not url:
                        continue

                    f = Finding(
                        source="DuckDuckGo",
                        status=SourceStatus.FOUND,
                        username=name,
                        url=url,
                        title=title,
                        snippet=snippet,
                        confidence=Confidence.LOW,
                        tier=SourceTier.SEARCH_RESULT,
                        extra={"query": q, "context": context or None},
                    )
                    f.evidence.append(Evidence(
                        source="DuckDuckGo",
                        url=url,
                        title=title,
                        claim="Публичное упоминание имени (возможное совпадение)",
                        evidence_type=EvidenceType.SEARCH_RESULT,
                        confidence=Confidence.LOW,
                        tier=SourceTier.SEARCH_RESULT,
                        snippet=snippet,
                        extra={"query": q},
                    ))
                    findings.append(f)
                    ev_engine.add_finding(f)

                    c = extract_from_finding(f)
                    contacts = merge(contacts, c)

        # Уникализация по URL
        seen_urls = set()
        unique_findings = []
        for f in findings:
            key = (f.url or "").rstrip("/").lower()
            if not key or key in seen_urls:
                continue
            seen_urls.add(key)
            unique_findings.append(f)
        findings = unique_findings

        stats.sources_configured = total
        stats.sources_checked = total
        stats.found = len(findings)
        stats.not_found = 0
        stats.errors = 0
        stats.unavailable = 0
        stats.finished_at = datetime.now(timezone.utc)

        log.info(
            "name scan done name=%r context=%r queries=%d results=%d dur=%.2fs",
            name, context, total, stats.found, time.perf_counter() - started,
        )

        return ScanResult(
            target_type=SearchType.NAME,
            target_value=name + ((" | " + context) if context else ""),
            stats=stats,
            findings=findings,
            evidence=ev_engine.all(),
            contacts=contacts,
            correlations=[],
        )