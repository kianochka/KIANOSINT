import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class BlueskySource(BaseSource):
    name = "Bluesky"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        handle = f"{username}.bsky.social"
        r = await client.get(
            "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile",
            params={"actor": handle},
        )
        if r.status_code == 400 or r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        u = r.json()
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=f"https://bsky.app/profile/{handle}",
            title=u.get("displayName") or username,
            display_name=u.get("displayName"),
            bio=u.get("description"),
            avatar=u.get("avatar"),
            confidence=Confidence.HIGH,
            extra={"followers": u.get("followersCount"), "following": u.get("followsCount")},
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f