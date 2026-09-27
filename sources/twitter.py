import httpx
from core.enums import SourceStatus
from core.models import Finding
from sources.base import BaseSource


class TwitterSource(BaseSource):
    name = "X / Twitter"
    requires_api = True

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        return Finding(source=self.name, status=SourceStatus.NOT_CONFIGURED, username=username)