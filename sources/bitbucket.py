import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class BitbucketSource(BaseSource):
    name = "Bitbucket"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://api.bitbucket.org/2.0/users/{username}")
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        u = r.json()
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=u.get("links", {}).get("html", {}).get("href"),
            title=u.get("display_name") or username,
            display_name=u.get("display_name"),
            avatar=u.get("links", {}).get("avatar", {}).get("href"),
            location=u.get("location"),
            website=u.get("website") or None,
            confidence=Confidence.HIGH,
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f