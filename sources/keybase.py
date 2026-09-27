import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class KeybaseSource(BaseSource):
    name = "Keybase"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(
            "https://keybase.io/_/api/1.0/user/lookup.json",
            params={"username": username, "fields": "profile,basics"},
        )
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)

        try:
            data = r.json()
        except Exception:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)

        them = data.get("them")
        if not them or not isinstance(them, list) or not them[0]:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)

        profile = (them[0] or {}).get("profile") or {}
        if not profile:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)

        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=f"https://keybase.io/{username}",
            title=profile.get("full_name") or username,
            display_name=profile.get("full_name"), bio=profile.get("bio"),
            avatar=profile.get("avatar"), location=profile.get("location"),
            confidence=Confidence.HIGH,
            extra={"proofs": profile.get("proofs_summary", {})},
        )
        f.evidence.append(self.build_evidence(f, "profile"))
        return f