"""PDF-отчёт KIANOSINT. Чистый fpdf2, шрифт Arial из системной папки."""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fpdf import FPDF

from core.models import ScanResult

log = logging.getLogger(__name__)


FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\Arial.ttf",
    r"C:\Windows\Fonts\DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]

FONT_BOLD_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _find_font(candidates):
    for path in candidates:
        if Path(path).exists():
            return path
    return None


class PDFReport(FPDF):
    def __init__(self, font_regular: str, font_bold: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.font_regular = font_regular
        self.font_bold = font_bold
        self.add_font("Main", "", font_regular, uni=True)
        self.add_font("Main", "B", font_bold, uni=True)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Main", "B", 14)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, "KIANOSINT — OSINT Report", ln=True, align="L")
        self.set_font("Main", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, "Только публично доступные данные", ln=True)
        self.ln(2)
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Main", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, f"Стр. {self.page_no()} | KIANOSINT", align="C")

    def section(self, title: str):
        self.ln(3)
        self.set_font("Main", "B", 12)
        self.set_text_color(20, 60, 120)
        self.cell(0, 7, title, ln=True)
        self.set_draw_color(20, 60, 120)
        y = self.get_y()
        self.line(10, y, 60, y)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def kv(self, key: str, value: str):
        self.set_font("Main", "B", 10)
        self.cell(45, 6, key, ln=0)
        self.set_font("Main", "", 10)
        self.multi_cell(0, 6, str(value), ln=1)

    def para(self, text: str):
        self.set_font("Main", "", 10)
        self.multi_cell(0, 5, text, ln=1)

    def bullet(self, text: str):
        self.set_font("Main", "", 10)
        self.multi_cell(0, 5, "• " + text, ln=1)

    def small(self, text: str):
        self.set_font("Main", "", 8)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 4, text, ln=1)
        self.set_text_color(0, 0, 0)


def render_pdf(result: ScanResult, out_path: Optional[str] = None) -> str:
    font_regular = _find_font(FONT_CANDIDATES)
    font_bold = _find_font(FONT_BOLD_CANDIDATES) or font_regular

    if not font_regular:
        raise RuntimeError(
            "Не найден TTF-шрифт с поддержкой кириллицы. "
            "Установи DejaVu или используй Windows."
        )

    pdf = PDFReport(font_regular, font_bold)
    pdf.add_page()

    # --- 1. Target ---
    pdf.section("1. Цель")
    pdf.kv("Тип:", str(result.target_type))
    pdf.kv("Значение:", result.target_value)

    # --- 2. Метаданные сканирования ---
    pdf.section("2. Метаданные сканирования")
    pdf.kv("Начало:", result.stats.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"))
    if result.stats.finished_at:
        pdf.kv("Окончание:", result.stats.finished_at.strftime("%Y-%m-%d %H:%M:%S UTC"))
        dur = (result.stats.finished_at - result.stats.started_at).total_seconds()
        pdf.kv("Длительность:", f"{dur:.2f} сек")

    # --- 3. Сводка ---
    pdf.section("3. Сводка")
    pdf.kv("Источников настроено:", str(result.stats.sources_configured))
    pdf.kv("Источников проверено:", str(result.stats.sources_checked))
    pdf.kv("Найдено:", str(result.stats.found))
    pdf.kv("Не найдено:", str(result.stats.not_found))
    pdf.kv("Ошибок:", str(result.stats.errors))
    pdf.kv("Недоступно:", str(result.stats.unavailable))

    # --- 4. Найденные профили ---
    pdf.section("4. Найденные профили")
    found = [f for f in result.findings if f.is_found and f.url]
    if not found:
        pdf.para("Профили не обнаружены.")
    else:
        for f in found:
            pdf.set_font("Main", "B", 10)
            pdf.cell(0, 5, f.source, ln=True)
            pdf.set_font("Main", "", 9)
            pdf.multi_cell(0, 4, "URL: " + (f.url or "—"), ln=1)
            if f.title:
                pdf.multi_cell(0, 4, "Название: " + f.title, ln=1)
            if f.bio:
                pdf.multi_cell(0, 4, "Bio: " + f.bio[:300], ln=1)
            pdf.ln(1)

    # --- 5. Public contacts ---
    pdf.section("5. Публичные контакты")
    c = result.contacts
    if not (c.emails or c.phones or c.websites):
        pdf.para("Публичные контактные данные не обнаружены.")
    else:
        if c.emails:
            pdf.set_font("Main", "B", 10)
            pdf.cell(0, 5, "Email:", ln=True)
            for e in c.emails:
                pdf.bullet(f"{e.value}  (источник: {e.source})")
        if c.phones:
            pdf.set_font("Main", "B", 10)
            pdf.cell(0, 5, "Телефоны:", ln=True)
            for p in c.phones:
                pdf.bullet(f"{p.value}  (источник: {p.source})")
        if c.websites:
            pdf.set_font("Main", "B", 10)
            pdf.cell(0, 5, "Сайты:", ln=True)
            for w in c.websites:
                pdf.bullet(f"{w.value}  (источник: {w.source})")

    # --- 6. Корреляции ---
    pdf.section("6. Корреляции")
    if not result.correlations:
        pdf.para("Сигналы связи не обнаружены.")
    else:
        for s in result.correlations:
            pdf.bullet(
                f"{s.left_source} ↔ {s.right_source} — {s.description} (вес {s.weight:.2f})"
            )
    pdf.small(
        "Сигнал связи не доказывает, что за источниками стоит один человек."
    )

    # --- 7. Evidence ---
    pdf.section("7. Evidence")
    if not result.evidence:
        pdf.para("Evidence отсутствует.")
    else:
        for ev in result.evidence[:100]:
            pdf.bullet(
                f"[{ev.evidence_type}] {ev.source} — {ev.url}\n  {ev.claim} "
                f"(уверенность: {ev.confidence})"
            )

    # --- 8. Недоступные источники ---
    pdf.section("8. Недоступные источники")
    unavail = [f for f in result.findings if not f.is_found and f.status != "not_found"]
    if not unavail:
        pdf.para("Все источники ответили.")
    else:
        for f in unavail:
            pdf.bullet(f"{f.source} — {f.status}" + (f" ({f.error})" if f.error else ""))

    # --- 9. Ограничения ---
    pdf.section("9. Ограничения")
    pdf.para(
        "• Отчёт содержит только публично доступные данные.\n"
        "• Совпадение username не является доказательством личности.\n"
        "• Скрытые данные и приватные источники не использовались.\n"
        "• Результаты — это сигналы и evidence, а не утверждения о человеке."
    )

    if not out_path:
        out_path = str(Path.cwd() / f"kianosint_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf.output(out_path)
    log.info("PDF report saved: %s", out_path)
    return out_path