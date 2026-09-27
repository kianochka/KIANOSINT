import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class MixcloudSource(BaseSource):
    name = "Mixcloud"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://api.mixcloud.com/{username}/")
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        u = r.json()
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=u.get("url"), title=u.get("name") or username,
            display_name=u.get("name"),
            bio=u.get("biog"),
            avatar=(u.get("pictures") or {}).get("large"),
            location=u.get("city"),
            confidence=Confidence.HIGH,
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f