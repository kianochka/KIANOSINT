import httpx
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource, extract_meta


class TwitchSource(BaseSource):
    name = "Twitch"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        url = f"https://www.twitch.tv/{username}"
        r = await client.get(url)
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        html = r.text
        if "Sorry. Unless you've got a time machine" in html:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username, url=url,
                    title=extract_meta(html, "og:title") or username,
                    bio=extract_meta(html, "og:description"),
                    avatar=extract_meta(html, "og:image"), confidence=Confidence.MEDIUM)
        f.evidence.append(self.build_evidence(f, "profile"))
        return f