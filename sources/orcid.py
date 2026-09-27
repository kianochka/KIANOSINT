import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class ORCIDSource(BaseSource):
    name = "ORCID"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        # ORCID ищет по имени/фамилии, не по юзернейму. Используем как имя.
        r = await client.get(
            "https://pub.orcid.org/v3.0/expanded-search/",
            params={"q": username, "rows": 3},
            headers={"Accept": "application/json"},
        )
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        try:
            data = r.json()
        except Exception:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        items = data.get("expanded-result") or []
        if not items:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        u = items[0]
        orcid_id = u.get("orcid-id") or ""
        name = " ".join(filter(None, [u.get("given-names"), u.get("family-names")])) or username
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=f"https://orcid.org/{orcid_id}" if orcid_id else None,
            title=name, display_name=name,
            snippet="Institution: {}".format(", ".join(u.get("institution-name") or [])),
            confidence=Confidence.MEDIUM,
            tier=3,
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f