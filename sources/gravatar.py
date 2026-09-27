import httpx
from core.enums import SourceStatus
from core.models import Finding
from sources.base import BaseSource


class GravatarSource(BaseSource):
    name = "Gravatar"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        return Finding(source=self.name, status=SourceStatus.NOT_CONFIGURED, username=username)