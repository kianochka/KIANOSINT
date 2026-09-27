import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class HuggingFaceSource(BaseSource):
    name = "Hugging Face"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(f"https://huggingface.co/api/users/{username}/overview")
        if r.status_code == 404:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        u = r.json()
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=f"https://huggingface.co/{username}",
            title=u.get("fullname") or username,
            display_name=u.get("fullname"),
            bio=u.get("bio"),
            avatar=u.get("avatarUrl"),
            confidence=Confidence.HIGH,
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f