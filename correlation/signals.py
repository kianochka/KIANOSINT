from core.models import CorrelationSignal, Finding

WEIGHTS = {
    "same_website": 0.9, "cross_link": 0.85, "same_email": 0.9, "same_phone": 0.9,
    "same_project": 0.6, "same_display_name": 0.4, "same_username": 0.25,
    "same_location": 0.35, "same_bio": 0.3,
}


def detect(findings, target_username: str):
    found = [f for f in findings if f.is_found]
    signals = []
    seen = set()

    def push(a, b, kind, desc, urls=None):
        key = (a.source, b.source, kind)
        if key in seen:
            return
        seen.add(key)
        signals.append(CorrelationSignal(
            left_source=a.source, right_source=b.source, kind=kind,
            weight=WEIGHTS.get(kind, 0.2), description=desc,
            evidence_urls=urls or [u for u in (a.url, b.url) if u],
        ))

    for f in found:
        if f.username and f.username.lower() == target_username.lower():
            push(f, f, "same_username", f"Username совпадает с целевым на {f.source}")

    for i, a in enumerate(found):
        for b in found[i + 1:]:
            if a.website and b.website and a.website.rstrip("/") == b.website.rstrip("/"):
                push(a, b, "same_website", "Одинаковый публичный website")
            if a.display_name and b.display_name and a.display_name.lower() == b.display_name.lower():
                push(a, b, "same_display_name", "Одинаковое display name")
            if a.location and b.location and a.location.lower() == b.location.lower():
                push(a, b, "same_location", "Одинаковая публичная локация")
            if a.bio and b.url and b.url.split("//")[-1].rstrip("/") in a.bio:
                push(a, b, "cross_link", f"{a.source} ссылается на {b.source}")
            if b.bio and a.url and a.url.split("//")[-1].rstrip("/") in b.bio:
                push(b, a, "cross_link", f"{b.source} ссылается на {a.source}")
    return signals