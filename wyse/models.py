from dataclasses import asdict, dataclass
from enum import Enum, StrEnum
from typing import ClassVar


class TrustTier(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"
    AGENT = "AGENT"
    WEB = "WEB"


class IncidentState(StrEnum):
    CLEAR = "CLEAR"
    QUARANTINED = "QUARANTINED"


class BeliefStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTESTED = "CONTESTED"
    STALE = "STALE"
    RETRACTED = "RETRACTED"


class UseStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    QUARANTINED = "QUARANTINED"
    RESTRICTED = "RESTRICTED"


class JustificationState(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class IncidentKind(StrEnum):
    RETRACTION = "RETRACTION"
    QUARANTINE = "QUARANTINE"


class Remediation(StrEnum):
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    COMPENSATING_ACTION_REQUIRED = "COMPENSATING_ACTION_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class Node:
    label: ClassVar[str] = "Node"
    id: str
    tenant: str

    def props(self) -> dict:
        return {
            key: value.value if isinstance(value, Enum) else value
            for key, value in asdict(self).items()
        }


@dataclass
class Source(Node):
    label: ClassVar[str] = "Source"
    kind: str
    name: str
    trust_tier: TrustTier
    incident_state: IncidentState = IncidentState.CLEAR


@dataclass
class Observation(Node):
    label: ClassVar[str] = "Observation"
    content: str
    content_hash: str
    observed_at: int
    recorded_at: int


@dataclass
class Claim(Node):
    label: ClassVar[str] = "Claim"
    subject: str
    predicate: str
    object: str
    created_at: int
    revision: int = 1
    belief_status: BeliefStatus = BeliefStatus.UNSUPPORTED
    use_status: UseStatus = UseStatus.ELIGIBLE


@dataclass
class Justification(Node):
    label: ClassVar[str] = "Justification"
    rule: str
    state: JustificationState = JustificationState.INVALID


@dataclass
class Entity(Node):
    label: ClassVar[str] = "Entity"
    name: str
    kind: str


@dataclass
class Agent(Node):
    label: ClassVar[str] = "Agent"
    role: str
    scope: str = "private"


@dataclass
class Decision(Node):
    label: ClassVar[str] = "Decision"
    summary: str
    decided_at: int
    policy_version: str
    remediation: Remediation = Remediation.NO_ACTION_REQUIRED
    acted: bool = False
    snapshot: str = ""


@dataclass
class Incident(Node):
    label: ClassVar[str] = "Incident"
    kind: IncidentKind
    reason: str
    created_at: int
    result: str = ""


ALL_NODES = (Source, Observation, Claim, Justification, Entity, Agent, Decision, Incident)
