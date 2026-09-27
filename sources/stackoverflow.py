import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class StackOverflowSource(BaseSource):
    name = "Stack Overflow"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(
            "https://api.stackexchange.com/2.3/users",
            params={"inname": username, "site": "stackoverflow", "filter": "default"},
        )
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        items = r.json().get("items", [])
        if not items:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        # точное совпадение
        u = None
        for it in items:
            if (it.get("display_name") or "").lower() == username.lower():
                u = it
                break
        if u is None:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=u.get("link"), title=u.get("display_name"),
            display_name=u.get("display_name"),
            avatar=u.get("profile_image"),
            location=u.get("location"),
            website=u.get("website") or None,
            confidence=Confidence.HIGH,
            extra={"reputation": u.get("reputation")},
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f