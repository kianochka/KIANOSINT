from collections import defaultdict
from urllib.parse import urlparse, urlunparse
from core.models import Evidence, Finding


def canonical_url(url: str) -> str:
    if not url:
        return url
    p = urlparse(url.strip())
    host = (p.hostname or "").lower()
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme or "https", host, path, "", "", ""))


class EvidenceEngine:
    def __init__(self) -> None:
        self._evidence = []
        self._seen_urls = set()

    def add_finding(self, finding: Finding) -> None:
        if not finding.is_found:
            return
        if not finding.evidence and finding.url:
            finding.evidence.append(Evidence(
                source=finding.source, url=finding.url, title=finding.title,
                claim="Found public profile", evidence_type="profile",
                confidence=finding.confidence, tier=finding.tier, snippet=finding.snippet,
            ))
        for ev in finding.evidence:
            key = canonical_url(ev.url)
            if key in self._seen_urls:
                continue
            self._seen_urls.add(key)
            ev.url = key
            self._evidence.append(ev)

    def all(self):
        return list(self._evidence)

    def by_type(self):
        out = defaultdict(list)
        for ev in self._evidence:
            out[str(ev.evidence_type)].append(ev)
        return dict(out)