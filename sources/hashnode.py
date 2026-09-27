import httpx

from core.enums import SourceStatus
from core.models import Finding
from sources.base import BaseSource


class HashnodeSource(BaseSource):
    name = "Hashnode"
    requires_api = True
    api_env_key = "hashnode_api_key"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        # Публичный GraphQL был закрыт в 2026, теперь только через платный API.
        return Finding(source=self.name, status=SourceStatus.NOT_CONFIGURED, username=username)