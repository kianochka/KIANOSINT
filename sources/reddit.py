import httpx
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class RedditSource(BaseSource):
    name = "Reddit"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://www.reddit.com/user/{username}/about.json",
                             headers={"User-Agent": "KIANOSINT/0.1"})
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code == 403:
            return Finding(source=self.name, status=SourceStatus.BLOCKED, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        data = r.json().get("data", {})
        if not data or data.get("is_suspended"):
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        sub = data.get("subreddit", {})
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username,
                    url=f"https://www.reddit.com/user/{username}",
                    title=sub.get("title") or f"u/{username}",
                    display_name=sub.get("title"), bio=sub.get("public_description"),
                    avatar=data.get("icon_img") or None, confidence=Confidence.HIGH,
                    extra={"karma": data.get("total_karma"), "created_utc": data.get("created_utc")})
        f.evidence.append(self.build_evidence(f, "profile"))
        return f