"""Bounded intake of caller-supplied capability candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

MAX_CAPABILITY_CANDIDATES = 100
MAX_CANDIDATE_ID_BYTES = 128
MAX_CANDIDATE_NAME_BYTES = 256
MAX_CANDIDATE_DESCRIPTION_BYTES = 2_048
MAX_CANDIDATE_REFERENCE_BYTES = 2_048
MAX_LIMITATIONS = 10
MAX_LIMITATION_BYTES = 512


class CapabilityCandidateSource(str, Enum):
    CALLER_SUPPLIED = "caller_supplied"


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    candidate_id: str
    name: str
    description: str
    source_reference: str

    def __post_init__(self) -> None:
        _validate_text(self.candidate_id, "candidate_id", MAX_CANDIDATE_ID_BYTES)
        _validate_text(self.name, "name", MAX_CANDIDATE_NAME_BYTES)
        _validate_text(
            self.description,
            "description",
            MAX_CANDIDATE_DESCRIPTION_BYTES,
        )
        _validate_text(
            self.source_reference,
            "source_reference",
            MAX_CANDIDATE_REFERENCE_BYTES,
        )


@dataclass(frozen=True, slots=True)
class CapabilityDiscoveryReport:
    discovered_at: datetime
    candidates: tuple[CapabilityCandidate, ...]
    source: CapabilityCandidateSource = CapabilityCandidateSource.CALLER_SUPPLIED
    limitations: tuple[str, ...] = (
        "Candidates and source references are caller-supplied and are not independently verified.",
        "Discovery does not evaluate, rank, register, grant, or activate capabilities.",
        "No external source is queried and no runtime state is changed.",
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.discovered_at, datetime)
            or self.discovered_at.tzinfo is None
            or self.discovered_at.utcoffset() is None
        ):
            raise ValueError("discovered_at must be timezone-aware")
        if not isinstance(self.source, CapabilityCandidateSource):
            raise TypeError("source must be a CapabilityCandidateSource")
        if not isinstance(self.candidates, tuple) or not all(
            isinstance(candidate, CapabilityCandidate)
            for candidate in self.candidates
        ):
            raise TypeError("candidates must be an immutable tuple of CapabilityCandidates")
        if len(self.candidates) > MAX_CAPABILITY_CANDIDATES:
            raise ValueError("candidate count exceeds its limit")
        if len({candidate.candidate_id for candidate in self.candidates}) != len(
            self.candidates
        ):
            raise ValueError("candidate IDs must be unique")
        if not isinstance(self.limitations, tuple):
            raise TypeError("limitations must be an immutable tuple of text")
        if len(self.limitations) > MAX_LIMITATIONS:
            raise ValueError("limitation count exceeds its limit")
        for limitation in self.limitations:
            _validate_text(limitation, "limitation", MAX_LIMITATION_BYTES)


class CapabilityDiscoveryService:
    """Return bounded caller-supplied candidates without evaluating or activating them."""

    def discover(
        self,
        candidates: tuple[CapabilityCandidate, ...],
    ) -> CapabilityDiscoveryReport:
        if not isinstance(candidates, tuple):
            raise TypeError("candidates must be an immutable tuple")
        if len(candidates) > MAX_CAPABILITY_CANDIDATES:
            raise ValueError("candidate count exceeds its limit")
        if not all(
            isinstance(candidate, CapabilityCandidate) for candidate in candidates
        ):
            raise TypeError("Expected CapabilityCandidate")
        if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
            raise ValueError("candidate IDs must be unique")
        return CapabilityDiscoveryReport(
            discovered_at=datetime.now(timezone.utc),
            candidates=candidates,
        )


def _validate_text(value: str, field_name: str, maximum_bytes: int) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    try:
        encoded_size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must contain valid Unicode text") from exc
    if encoded_size > maximum_bytes:
        raise ValueError(f"{field_name} exceeds its byte limit")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} contains control characters")
