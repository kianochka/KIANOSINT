import httpx
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class GitLabSource(BaseSource):
    name = "GitLab"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get("https://gitlab.com/api/v4/users", params={"username": username})
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        users = r.json()
        if not users:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        u = users[0]
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username,
                    url=u.get("web_url"), title=u.get("name") or username,
                    display_name=u.get("name"), bio=u.get("bio"), avatar=u.get("avatar_url"),
                    location=u.get("location"), website=u.get("website_url") or None,
                    confidence=Confidence.HIGH)
        f.evidence.append(self.build_evidence(f, "profile"))
        return f