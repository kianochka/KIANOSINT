from core.config import settings
from core.models import ScanResult

SYSTEM_PROMPT = (
    "Ты — аналитик OSINT. Работаешь ТОЛЬКО с предоставленными данными. "
    "Запрещено придумывать факты. Если данных мало — пиши: Недостаточно публичных данных для вывода. "
    "Никогда не утверждай тождество личности. Пиши возможное совпадение, сигнал связи. "
    "Формат ответа (markdown): ## Краткое резюме, ## Основные источники, ## Сильные сигналы, "
    "## Слабые сигналы, ## Противоречия, ## Публичные контакты, ## Вывод."
)


def _pack(r: ScanResult) -> str:
    parts = ["Target: {}".format(r.target_value),
             "Sources checked: {}, found: {}".format(r.stats.sources_checked, r.stats.found)]
    for f in r.findings:
        if not f.is_found:
            continue
        parts.append("- {}: {} | title={} | bio={} | loc={} | site={}".format(
            f.source, f.url, f.title, f.bio, f.location, f.website))
    if r.contacts.emails:
        parts.append("Emails: " + ", ".join(e.value for e in r.contacts.emails))
    if r.contacts.phones:
        parts.append("Phones: " + ", ".join(p.value for p in r.contacts.phones))
    if r.correlations:
        parts.append("Correlations:")
        for s in r.correlations:
            parts.append("- {} <-> {}: {} ({})".format(s.left_source, s.right_source, s.description, s.weight))
    return "\n".join(parts)


def _fallback(r: ScanResult) -> str:
    lines = ["🤖 <b>AI Анализ</b> (без OpenAI)\n",
             "Кратко: найдено {} публичных источников.".format(r.stats.found), "\nОсновные источники:"]
    for f in r.findings:
        if f.is_found:
            lines.append("• {}".format(f.source))
    lines.append("\nСильные сигналы (вес ≥ 0.6):")
    strong = [s for s in r.correlations if s.weight >= 0.6]
    lines.extend(["• {} ↔ {}: {}".format(s.left_source, s.right_source, s.description) for s in strong] or ["—"])
    lines.append("\nСлабые сигналы (вес ниже 0.6):")
    weak = [s for s in r.correlations if s.weight < 0.6]
    lines.extend(["• {} ↔ {}: {}".format(s.left_source, s.right_source, s.description) for s in weak] or ["—"])
    lines.append("\nВывод: набор публичных evidence и сигналов связи. Тождество не подтверждено.")
    return "\n".join(lines)


async def analyze(r: ScanResult) -> str:
    if not settings.openai_api_key:
        return _fallback(r)
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": _pack(r)}],
            temperature=0.2)
        text = "🤖 <b>AI Анализ</b>\n\n" + resp.choices[0].message.content
        return text
    except Exception:
        return _fallback(r)