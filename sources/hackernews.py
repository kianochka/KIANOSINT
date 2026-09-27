import httpx
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class HackerNewsSource(BaseSource):
    name = "Hacker News"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://hacker-news.firebaseio.com/v0/user/{username}.json")
        if r.status_code != 200 or r.json() is None:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        data = r.json()
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username,
                    url=f"https://news.ycombinator.com/user?id={username}",
                    title=username, bio=data.get("about"), confidence=Confidence.HIGH,
                    extra={"karma": data.get("karma")})
        f.evidence.append(self.build_evidence(f, "profile"))
        return f