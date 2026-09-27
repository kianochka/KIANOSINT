from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from core.enums import Confidence, EvidenceType, SearchType, SourceStatus, SourceTier


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(BaseModel):
    source: str
    url: str
    title: Optional[str] = None
    claim: str
    evidence_type: EvidenceType = EvidenceType.PROFILE
    confidence: Confidence = Confidence.MEDIUM
    tier: int = SourceTier.DIRECT_PROFILE
    snippet: Optional[str] = None
    collected_at: datetime = Field(default_factory=utcnow)
    extra: dict = Field(default_factory=dict)


class Finding(BaseModel):
    source: str
    status: SourceStatus
    username: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    snippet: Optional[str] = None
    confidence: Confidence = Confidence.MEDIUM
    tier: int = SourceTier.DIRECT_PROFILE
    duration_ms: int = 0
    error: Optional[str] = None
    extra: dict = Field(default_factory=dict)
    evidence: List[Evidence] = Field(default_factory=list)

    @property
    def is_found(self) -> bool:
        return self.status == SourceStatus.FOUND


class CorrelationSignal(BaseModel):
    left_source: str
    right_source: str
    kind: str
    weight: float
    description: str
    evidence_urls: List[str] = Field(default_factory=list)


class ContactEntry(BaseModel):
    value: str
    kind: str
    source: str
    source_url: Optional[str] = None


class PublicContacts(BaseModel):
    emails: List[ContactEntry] = Field(default_factory=list)
    phones: List[ContactEntry] = Field(default_factory=list)
    websites: List[ContactEntry] = Field(default_factory=list)
    socials: List[ContactEntry] = Field(default_factory=list)


class SearchStats(BaseModel):
    sources_configured: int = 0
    sources_checked: int = 0
    found: int = 0
    not_found: int = 0
    errors: int = 0
    unavailable: int = 0
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None


class ScanResult(BaseModel):
    target_type: SearchType
    target_value: str
    stats: SearchStats
    findings: List[Finding] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    contacts: PublicContacts = Field(default_factory=PublicContacts)
    correlations: List[CorrelationSignal] = Field(default_factory=list)
    ai_analysis: dict = Field(default_factory=dict)
    cached: bool = False