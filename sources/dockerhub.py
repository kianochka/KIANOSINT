import httpx
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class DockerHubSource(BaseSource):
    name = "Docker Hub"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://hub.docker.com/v2/users/{username}/")
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        u = r.json()
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username,
                    url=f"https://hub.docker.com/u/{username}",
                    title=u.get("full_name") or username, display_name=u.get("full_name"),
                    bio=u.get("company"), avatar=u.get("gravatar_url"),
                    location=u.get("location"), confidence=Confidence.HIGH)
        f.evidence.append(self.build_evidence(f, "profile"))
        return f