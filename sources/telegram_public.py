import httpx
from core.enums import Confidence, SourceStatus
from core.models import Finding
from sources.base import BaseSource, extract_meta


class TelegramPublicSource(BaseSource):
    name = "Telegram (public)"

    async def search_username(self, client: httpx.AsyncClient, username: str) -> Finding:
        url = f"https://t.me/{username}"
        r = await client.get(url)
        if r.status_code != 200:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        html = r.text
        if "tgme_page_title" not in html and "tgme_page" not in html:
            return Finding(source=self.name, status=SourceStatus.NOT_FOUND, username=username)
        f = Finding(source=self.name, status=SourceStatus.FOUND, username=username, url=url,
                    title=extract_meta(html, "og:title") or username,
                    display_name=extract_meta(html, "og:title"),
                    bio=extract_meta(html, "og:description"),
                    avatar=extract_meta(html, "og:image"), confidence=Confidence.HIGH,
                    extra={"note": "Скрытые данные Telegram не извлекаются."})
        f.evidence.append(self.build_evidence(f, "profile"))
        return f