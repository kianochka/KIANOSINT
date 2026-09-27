import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class TrelloSource(BaseSource):
    name = "Trello"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://trello.com/1/members/{username}")
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        try:
            u = r.json()
        except Exception:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=f"https://trello.com/{username}",
            title=u.get("fullName") or username,
            display_name=u.get("fullName"),
            bio=u.get("bio"),
            avatar=u.get("avatarUrl") or None,
            confidence=Confidence.HIGH,
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f