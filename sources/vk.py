import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource, extract_meta


class VKSource(BaseSource):
    name = "VK"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        url = f"https://vk.com/{username}"
        r = await client.get(url, headers={"Accept-Language": "ru,en;q=0.8"})

        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.BLOCKED, username=username)

        html = r.text
        low = html[:5000].lower()

        if "страница удалена" in low or "page not found" in low or "profile not found" in low:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)

        login_markers = [
            "войдите в vk", "войти в vk", "log in to vk",
            "login.vk.com", "чтобы просматривать", "join vk",
        ]
        if any(m in low for m in login_markers):
            return Finding(source=self.name, status=SourceStatus.BLOCKED, username=username)

        title = extract_meta(html, "og:title")
        description = extract_meta(html, "og:description")

        if not title and not description:
            return Finding(source=self.name, status=SourceStatus.BLOCKED, username=username)

        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username, url=url,
            title=title or username,
            bio=description,
            avatar=extract_meta(html, "og:image"),
            confidence=Confidence.MEDIUM,
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f