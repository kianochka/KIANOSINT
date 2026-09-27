import sys
from enum import Enum

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, Enum):
        """Backport StrEnum for Python 3.10."""

        def __str__(self) -> str:
            return str(self.value)


class SearchType(StrEnum):
    USERNAME = "username"
    PHONE = "phone"
    NAME = "name"
    WEB = "web"


class SourceStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    NOT_CONFIGURED = "not_configured"


class EvidenceType(StrEnum):
    PROFILE = "profile"
    USERNAME = "username"
    BIO = "bio"
    EMAIL = "email"
    PHONE = "phone"
    WEBSITE = "website"
    LOCATION = "location"
    SOCIAL_LINK = "social_link"
    PROJECT = "project"
    POST = "post"
    COMMENT = "comment"
    PUBLIC_DOCUMENT = "public_document"
    SEARCH_RESULT = "search_result"
    AVATAR = "avatar"
    IDENTIFIER = "identifier"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceTier(int):
    DIRECT_PROFILE = 1
    PUBLIC_PAGE = 2
    SEARCH_RESULT = 3
    INDIRECT = 4