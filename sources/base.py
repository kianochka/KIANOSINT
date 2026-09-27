import abc
import asyncio
import logging
import re
import time
from typing import Any, Optional
import httpx
from core.config import settings
from core.enums import Confidence, EvidenceType, SourceStatus, SourceTier
from core.models import Evidence, Finding

log = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 KIANOSINT/0.1"
)


class BaseSource(abc.ABC):
    name: str = "base"
    tier: int = SourceTier.DIRECT_PROFILE
    requires_api: bool = False
    api_env_key: Optional[str] = None
    timeout: int = settings.request_timeout

    def is_configured(self) -> bool:
        if not self.requires_api:
            return True
        if not self.api_env_key:
            return True
        return bool(getattr(settings, self.api_env_key, ""))

    @abc.abstractmethod
    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        ...

    async def run(self, client: httpx.AsyncClient, username: str) -> Finding:
        started = time.perf_counter()
        if not self.is_configured():
            return Finding(source=self.name, status=SourceStatus.NOT_CONFIGURED, username=username, confidence=Confidence.LOW)
        try:
            finding = await asyncio.wait_for(self.search_username(client, username), timeout=self.timeout)
        except asyncio.TimeoutError:
            return Finding(source=self.name, status=SourceStatus.TIMEOUT, username=username, error="timeout")
        except httpx.HTTPError as e:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username, error=f"http: {e.__class__.__name__}")
        except Exception as e:
            log.exception("source %s failed", self.name)
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username, error=str(e)[:200])
        finding.duration_ms = int((time.perf_counter() - started) * 1000)
        return finding

    def build_evidence(self, finding: Finding, evidence_type: EvidenceType) -> Evidence:
        return Evidence(
            source=finding.source,
            url=finding.url or "",
            title=finding.title,
            claim="Found public profile" if finding.is_found else "Not found",
            evidence_type=evidence_type,
            confidence=finding.confidence,
            tier=finding.tier,
            snippet=finding.snippet,
        )


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(html: str) -> str:
    return TAG_RE.sub("", html)


def extract_meta(html: str, prop: str) -> Optional[str]:
    for pattern in (
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']',
    ):
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def make_client(**kwargs: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": DEFAULT_UA, "Accept-Language": "en-US,en;q=0.9"},
        timeout=settings.request_timeout,
        follow_redirects=True,
        **kwargs,
    )