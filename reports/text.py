import html

from core.models import ScanResult


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def render_report(r: ScanResult) -> str:
    lines = [
        "ОТЧЁТ KIANOSINT",
        "=" * 40,
        "ЦЕЛЬ:     {}".format(_esc(r.target_value)),
        "ТИП:      {}".format(_esc(r.target_type)),
        "НАЧАЛО:   {}".format(r.stats.started_at.strftime("%Y-%m-%d %H:%M:%S")),
    ]
    if r.stats.finished_at:
        lines.append("ОКОНЧАНИЕ: {}".format(r.stats.finished_at.strftime("%Y-%m-%d %H:%M:%S")))
    lines += [
        "",
        "ИСТОЧНИКОВ НАСТРОЕНО:  {}".format(r.stats.sources_configured),
        "ИСТОЧНИКОВ ПРОВЕРЕНО:  {}".format(r.stats.sources_checked),
        "НАЙДЕНО:               {}".format(r.stats.found),
        "НЕ НАЙДЕНО:            {}".format(r.stats.not_found),
        "ОШИБОК:                {}".format(r.stats.errors),
        "НЕДОСТУПНО:            {}".format(r.stats.unavailable),
        "", "НАЙДЕННЫЕ ИСТОЧНИКИ",
    ]
    for f in r.findings:
        if f.is_found:
            lines.append("  [{}] {}: {}".format(_esc(f.status), _esc(f.source), _esc(f.url)))
    lines.append("")
    lines.append("ПУБЛИЧНЫЕ КОНТАКТЫ")
    for c in r.contacts.emails:
        lines.append("  email: {} ({})".format(_esc(c.value), _esc(c.source)))
    for c in r.contacts.phones:
        lines.append("  тел.:  {} ({})".format(_esc(c.value), _esc(c.source)))
    for c in r.contacts.websites:
        lines.append("  сайт:  {} ({})".format(_esc(c.value), _esc(c.source)))
    lines.append("")
    lines.append("КОРРЕЛЯЦИИ")
    for s in r.correlations:
        lines.append("  {} ↔ {}: {} (вес={:.2f})".format(
            _esc(s.left_source), _esc(s.right_source), _esc(s.description), s.weight))
    lines.append("")
    lines.append("ОГРАНИЧЕНИЯ")
    lines.append("  - Только публично доступные данные.")
    lines.append("  - Совпадение username не является доказательством личности.")
    lines.append("  - Скрытые данные не извлекались.")
    return "\n".join(lines)