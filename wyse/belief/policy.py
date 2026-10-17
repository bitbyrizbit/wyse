import hashlib

from wyse.models import TrustTier

MAX_CONTENT = 20_000
MAX_FIELD = 500

TRUST_RANK = {
    TrustTier.SYSTEM: 5,
    TrustTier.USER: 4,
    TrustTier.TOOL: 3,
    TrustTier.AGENT: 2,
    TrustTier.WEB: 1,
}

KIND_TIER = {
    "system": TrustTier.SYSTEM,
    "user": TrustTier.USER,
    "tool": TrustTier.TOOL,
    "agent": TrustTier.AGENT,
    "web": TrustTier.WEB,
}


def tier_for_kind(kind: str) -> TrustTier:
    return KIND_TIER.get(kind.strip().lower(), TrustTier.WEB)


def rank_of(tier: str) -> int:
    return TRUST_RANK[TrustTier(tier)]


def normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def digest(*parts: str, size: int = 16) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:size]


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def source_id_for(kind: str, name: str) -> str:
    return "src_" + digest(normalize(kind), normalize(name))


def check_text(label: str, value: str, limit: int) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    if len(text) > limit:
        raise ValueError(f"{label} exceeds {limit} characters")
    return text
