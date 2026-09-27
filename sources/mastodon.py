import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class MastodonSource(BaseSource):
    name = "Mastodon (mastodon.social)"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://mastodon.social/api/v1/accounts/lookup", params={"acct": username})
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        u = r.json()
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=u.get("url"), title=u.get("display_name") or username,
            display_name=u.get("display_name"),
            bio=u.get("note"),
            avatar=u.get("avatar"),
            confidence=Confidence.HIGH,
            extra={"followers": u.get("followers_count")},
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f