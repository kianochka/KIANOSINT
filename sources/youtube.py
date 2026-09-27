import httpx
from core.config import settings
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class YouTubeSource(BaseSource):
    name = "YouTube"
    requires_api = True
    api_env_key = "youtube_api_key"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        if not settings.youtube_api_key:
            return Finding(source=self.name, status=SourceStatus.NOT_CONFIGURED, username=username)
        r = await client.get("https://www.googleapis.com/youtube/v3/channels",
                             params={"part": "snippet", "forHandle": username, "key": settings.youtube_api_key})
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        items = r.json().get("items", [])
        if not items:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        sn = items[0]["snippet"]
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username,
                    url=f"https://youtube.com/@{username}", title=sn.get("title"),
                    display_name=sn.get("title"), bio=sn.get("description"),
                    avatar=(sn.get("thumbnails") or {}).get("default", {}).get("url"),
                    confidence=Confidence.HIGH)
        f.evidence.append(self.build_evidence(f, "profile"))
        return f