"""Мульти-поисковый движок. Работает без ключей, некоторые движки опциональны."""
import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs, unquote

import httpx

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _decode_ddg_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    if "duckduckgo.com/l/" in url:
        try:
            qs = parse_qs(urlparse(url).query)
            return unquote(qs.get("uddg", [url])[0])
        except Exception:
            return url
    return url


async def _search_ddg(client: httpx.AsyncClient, query: str, limit: int) -> List[Dict]:
    try:
        r = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": UA, "Accept-Language": "ru,en;q=0.8"},
            timeout=20,
        )
    except Exception as e:
        log.debug("ddg net error: %s", e)
        return []
    if r.status_code != 200:
        return []
    html = r.text
    results = []
    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)?',
        html, re.S,
    )
    for href, title_html, snip_a, snip_div in blocks[:limit]:
        url = _decode_ddg_url(href.strip())
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        snippet = re.sub(r"<[^>]+>", "", (snip_a or snip_div or "")).strip()
        if url:
            results.append({"url": url, "title": title, "snippet": snippet, "engine": "DuckDuckGo"})
    return results


async def _search_mojeek(client: httpx.AsyncClient, query: str, limit: int) -> List[Dict]:
    """Mojeek — независимый поисковик, не блокирует ботов."""
    try:
        r = await client.get(
            "https://www.mojeek.com/search",
            params={"q": query},
            headers={"User-Agent": UA, "Accept-Language": "ru,en;q=0.8"},
            timeout=15,
        )
    except Exception as e:
        log.debug("mojeek net error: %s", e)
        return []
    if r.status_code != 200:
        return []
    html = r.text
    results = []
    blocks = re.findall(
        r'<a[^>]+class="ob"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<p[^>]+class="s"[^>]*>(.*?)</p>',
        html, re.S,
    )
    for href, title_html, snip_html in blocks[:limit]:
        url = href.strip()
        if url.startswith("//"):
            url = "https:" + url
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        snippet = re.sub(r"<[^>]+>", "", snip_html).strip()
        if url:
            results.append({"url": url, "title": title, "snippet": snippet, "engine": "Mojeek"})
    return results


async def _search_brave(client: httpx.AsyncClient, query: str, limit: int, api_key: str) -> List[Dict]:
    """Brave Search API. Нужен ключ (free 2000/мес)."""
    try:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            timeout=15,
        )
    except Exception as e:
        log.debug("brave net error: %s", e)
        return []
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    results = []
    for item in (data.get("web", {}) or {}).get("results", [])[:limit]:
        results.append({
            "url": item.get("url"),
            "title": item.get("title") or "",
            "snippet": item.get("description") or "",
            "engine": "Brave",
        })
    return [r for r in results if r["url"]]


async def _search_numverify(client: httpx.AsyncClient, phone: str, api_key: str) -> Optional[Dict]:
    """NumVerify — валидация и оператор. Free 100/мес."""
    try:
        r = await client.get(
            "http://apilayer.net/api/validate",
            params={"access_key": api_key, "number": phone, "format": 1},
            timeout=15,
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except Exception:
        return None
    if not data.get("valid"):
        return None
    return {
        "number": data.get("international_format"),
        "country": data.get("country_name"),
        "location": data.get("location"),
        "carrier": data.get("carrier"),
        "line_type": data.get("line_type"),
    }


async def web_search_multi(
    client: httpx.AsyncClient,
    query: str,
    limit: int = 10,
    brave_key: Optional[str] = None,
) -> List[Dict]:
    """Параллельно спрашивает DDG + Mojeek + Brave (если ключ)."""
    tasks = [
        _search_ddg(client, query, limit),
        _search_mojeek(client, query, limit),
    ]
    if brave_key:
        tasks.append(_search_brave(client, query, limit, brave_key))

    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: List[Dict] = []
    seen_urls = set()
    for batch in all_results:
        if isinstance(batch, Exception) or not batch:
            continue
        for item in batch:
            url = (item.get("url") or "").rstrip("/")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(item)
    return merged


# Обратная совместимость — старая функция
async def web_search(client: httpx.AsyncClient, query: str, limit: int = 15) -> List[Dict]:
    return await _search_ddg(client, query, limit)


async def numverify_lookup(client: httpx.AsyncClient, phone: str, api_key: str) -> Optional[Dict]:
    return await _search_numverify(client, phone, api_key)