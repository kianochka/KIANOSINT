import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class PyPISource(BaseSource):
    name = "PyPI"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        # PyPI ищет пакеты по author, это не совсем профиль, но даёт публичную страницу
        r = await client.get(f"https://pypi.org/user/{username}/")
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        from sources.base import extract_meta
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=f"https://pypi.org/user/{username}/",
            title=extract_meta(r.text, "og:title") or username,
            bio=extract_meta(r.text, "og:description"),
            avatar=extract_meta(r.text, "og:image"),
            confidence=Confidence.MEDIUM,
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f