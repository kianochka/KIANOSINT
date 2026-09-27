import httpx

from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource


class ArXivSource(BaseSource):
    name = "arXiv"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        r = await client.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": f"all:{username}", "max_results": 3},
        )
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.ERROR, username=username)
        html = r.text
        if "<entry>" not in html:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        import re
        m = re.search(r"<title>([^<]+)</title>", html.split("<entry>", 1)[1])
        title = (m.group(1).strip() if m else username)[:150]
        m2 = re.search(r"<id>([^<]+)</id>", html.split("<entry>", 1)[1])
        url = m2.group(1).strip() if m2 else None
        f = Finding(
            source=self.name, status=SourceStatus.FOUND, username=username,
            url=url, title=title, snippet=title,
            confidence=Confidence.LOW, tier=3,
        )
        f.evidence.append(self.build_evidence(f, "search_result"))
        return f