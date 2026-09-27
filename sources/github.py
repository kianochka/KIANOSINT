import httpx
from core.config import settings
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class GithubSource(BaseSource):
    name = "GitHub"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        headers = {}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        r = await client.get(f"https://api.github.com/users/{username}", headers=headers)
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code == 403:
            return Finding(source=self.name, status=SourceStatus.RATE_LIMITED, username=username)
        r.raise_for_status()
        data = r.json()
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=data.get("html_url"), title=data.get("name") or username,
            display_name=data.get("name"), bio=data.get("bio"),
            avatar=data.get("avatar_url"), location=data.get("location"),
            website=data.get("blog") or None, confidence=Confidence.HIGH,
            extra={"public_repos": data.get("public_repos"), "followers": data.get("followers"),
                   "company": data.get("company"), "twitter_username": data.get("twitter_username")},
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f