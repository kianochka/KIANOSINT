import re
from typing import List, Optional

import phonenumbers

from core.models import ContactEntry, Finding, PublicContacts

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s\"'<>)\]}]+")

BAD_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net",
    "sentry.io", "wixpress.com", "wix.com", "sentry-next.wixpress.com",
    "domain.com", "email.com", "yourdomain.com", "site.com",
}
BAD_EMAIL_LOCAL = {
    "noreply", "no-reply", "donotreply", "postmaster",
    "abuse", "webmaster", "hostmaster",
}
SKIP_URL_HOSTS = {
    "twitter.com", "x.com", "instagram.com", "facebook.com", "t.me",
    "youtube.com", "youtu.be", "tiktok.com", "linkedin.com",
    "github.com", "gitlab.com", "medium.com", "reddit.com",
    "google.com", "goo.gl", "bit.ly",
}


def _valid_email(email: str) -> bool:
    email = email.lower()
    local, _, domain = email.partition("@")
    if domain in BAD_EMAIL_DOMAINS:
        return False
    if local in BAD_EMAIL_LOCAL:
        return False
    if len(local) < 2 or local.startswith(".") or local.endswith("."):
        return False
    return True


def _extract_phones(text: str, region: Optional[str] = None) -> List[str]:
    out: List[str] = []
    try:
        for m in phonenumbers.PhoneNumberMatcher(text, region or "ZZ"):
            if phonenumbers.is_valid_number(m.number):
                e164 = phonenumbers.format_number(
                    m.number, phonenumbers.PhoneNumberFormat.E164
                )
                if e164 not in out:
                    out.append(e164)
    except Exception:
        pass
    return out


def extract_from_text(
    text: str,
    source: str,
    source_url: Optional[str] = None,
    region: Optional[str] = None,
) -> PublicContacts:
    c = PublicContacts()
    if not text:
        return c

    for em in EMAIL_RE.findall(text):
        if _valid_email(em):
            c.emails.append(ContactEntry(
                value=em.lower(), kind="email",
                source=source, source_url=source_url,
            ))

    for ph in _extract_phones(text, region):
        c.phones.append(ContactEntry(
            value=ph, kind="phone",
            source=source, source_url=source_url,
        ))

    for url in URL_RE.findall(text):
        parts = url.split("/")
        host = parts[2].lower() if len(parts) >= 3 else ""
        host = host[4:] if host.startswith("www.") else host
        if host in SKIP_URL_HOSTS:
            continue
        c.websites.append(ContactEntry(
            value=url, kind="website",
            source=source, source_url=source_url,
        ))
    return c


def extract_from_finding(finding: Finding) -> PublicContacts:
    out = PublicContacts()
    region = None
    if finding.location:
        loc = finding.location.strip().upper()
        if len(loc) == 2:
            region = loc

    for text in (finding.bio, finding.snippet, finding.website):
        if not text:
            continue
        out = merge(out, extract_from_text(text, finding.source, finding.url, region))

    if finding.website:
        out.websites.append(ContactEntry(
            value=finding.website, kind="website",
            source=finding.source, source_url=finding.url,
        ))
    return out


def merge(*many: PublicContacts) -> PublicContacts:
    out = PublicContacts()
    seen = {"emails": set(), "phones": set(), "websites": set(), "socials": set()}
    for c in many:
        for bucket in ("emails", "phones", "websites", "socials"):
            for entry in getattr(c, bucket):
                key = entry.value.lower().rstrip("/")
                if key in seen[bucket]:
                    continue
                seen[bucket].add(key)
                getattr(out, bucket).append(entry)
    return out