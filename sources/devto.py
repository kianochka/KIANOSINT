import httpx
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class DevToSource(BaseSource):
    name = "Dev.to"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get("https://dev.to/api/users/by_username", params={"url": username})
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        u = r.json()
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username,
                    url=f"https://dev.to/{username}", title=u.get("name") or username,
                    display_name=u.get("name"), bio=u.get("summary"),
                    avatar=u.get("profile_image"), location=u.get("location"),
                    website=u.get("website_url") or None, confidence=Confidence.HIGH)
        f.evidence.append(self.build_evidence(f, "profile"))
        return f