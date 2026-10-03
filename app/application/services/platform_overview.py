"""Bounded, read-only overview of currently configured Corporation sources."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, Sequence

from app.capabilities import (
    CapabilityCatalogSnapshot,
    CapabilityRegistry,
    CapabilitySource,
    MAX_CAPABILITY_RECORDS,
)
from app.orchestrator import Orchestrator
from app.tools import ToolRegistry
from .corporation import CorporationStatusSummary


class PlatformSourceState(str, Enum):
    CONFIGURED = "configured"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PlatformRegistryName(str, Enum):
    EMPLOYEES = "employees"
    AGENTS = "agents"
    PROVIDERS = "providers"
    PROJECTS = "projects"
    TASKS = "tasks"


@dataclass(frozen=True, slots=True)
class PlatformRegistryCount:
    registry: PlatformRegistryName
    state: PlatformSourceState
    count: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.registry, PlatformRegistryName):
            raise TypeError("registry must be a PlatformRegistryName")
        if not isinstance(self.state, PlatformSourceState):
            raise TypeError("state must be a PlatformSourceState")
        if self.state is PlatformSourceState.CONFIGURED:
            if type(self.count) is not int or self.count < 0:
                raise ValueError("configured registry count must be a non-negative integer")
        elif self.count is not None:
            raise ValueError("unavailable or unknown registry counts must be None")


@dataclass(frozen=True, slots=True)
class PlatformCapabilitySource:
    source: CapabilitySource
    state: PlatformSourceState
    record_count: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.source, CapabilitySource):
            raise TypeError("source must be a CapabilitySource")
        if not isinstance(self.state, PlatformSourceState):
            raise TypeError("state must be a PlatformSourceState")
        if self.state is PlatformSourceState.CONFIGURED:
            if type(self.record_count) is not int or not (
                0 <= self.record_count <= MAX_CAPABILITY_RECORDS
            ):
                raise ValueError("configured capability source count is invalid")
        elif self.record_count is not None:
            raise ValueError("unavailable or unknown source counts must be None")


@dataclass(frozen=True, slots=True)
class PlatformOverviewReport:
    observed_at: datetime
    identity: CorporationStatusSummary | None
    identity_state: PlatformSourceState
    registries: tuple[PlatformRegistryCount, ...]
    capability_catalog: CapabilityCatalogSnapshot
    capability_sources: tuple[PlatformCapabilitySource, ...]
    limitations: tuple[str, ...] = (
        "Configured means a local registry is present; it does not imply production readiness.",
        "Registry counts describe registered records, not provider or model health.",
        "Provider/model availability, hardware feasibility, resource capacity, and "
        "routing are not evaluated.",
        "Capability evidence is metadata; it does not establish competence, authorization, or execution readiness.",
        "Requirements of None mean the source supplied no requirement metadata.",
        "An unavailable ToolRegistry is not represented as an empty configured registry.",
        "Gemini capability metadata is UNKNOWN because no existing catalog snapshot was supplied.",
        "Registry and capability sources are sampled sequentially, not as an atomic snapshot.",
        "No Provider/network calls, Task execution, resource reservations, assignment changes, or background work occur.",
        "No credentials, persistence, API/UI, or new dependencies are introduced.",
        "This overview does not claim that the Corporation is autonomous or production-ready.",
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware")
        if self.identity is not None and not isinstance(
            self.identity, CorporationStatusSummary
        ):
            raise TypeError("identity must be a CorporationStatusSummary or None")
        if self.identity is not None and any(
            not isinstance(value, str)
            or not value.strip()
            or _utf8_size(value) > 512
            for value in (
                self.identity.corporation_id,
                self.identity.corporation_name,
                self.identity.node_id,
                self.identity.node_name,
            )
        ):
            raise ValueError("platform identity fields must be nonempty and bounded")
        if not isinstance(self.identity_state, PlatformSourceState):
            raise TypeError("identity_state must be a PlatformSourceState")
        expected_identity_state = (
            PlatformSourceState.CONFIGURED
            if self.identity is not None
            else PlatformSourceState.UNAVAILABLE
        )
        if self.identity_state is not expected_identity_state:
            raise ValueError("identity_state does not match the identity")
        if not isinstance(self.registries, tuple) or len(self.registries) != len(
            PlatformRegistryName
        ):
            raise ValueError("registries must contain the bounded Platform registry set")
        if not all(isinstance(item, PlatformRegistryCount) for item in self.registries):
            raise TypeError("registries must contain PlatformRegistryCount values")
        if {item.registry for item in self.registries} != set(PlatformRegistryName):
            raise ValueError("registry count entries must be unique and complete")
        if not isinstance(self.capability_catalog, CapabilityCatalogSnapshot):
            raise TypeError("capability_catalog must be a CapabilityCatalogSnapshot")
        if not isinstance(self.capability_sources, tuple) or len(
            self.capability_sources
        ) != 3:
            raise ValueError("capability_sources must contain three bounded source states")
        if not all(
            isinstance(item, PlatformCapabilitySource)
            for item in self.capability_sources
        ):
            raise TypeError("capability_sources must contain PlatformCapabilitySource values")
        if {item.source for item in self.capability_sources} != {
            CapabilitySource.AGENT,
            CapabilitySource.TOOL,
            CapabilitySource.GEMINI_MODEL,
        }:
            raise ValueError("capability source states must be unique and complete")
        for source in self.capability_sources:
            source_record_count = sum(
                record.source is source.source
                for record in self.capability_catalog.records
            )
            if source.state is PlatformSourceState.CONFIGURED:
                if source.record_count != source_record_count:
                    raise ValueError("capability source count does not match its records")
            elif source_record_count:
                raise ValueError("unavailable or unknown sources cannot have catalog records")
        if not isinstance(self.limitations, tuple) or len(self.limitations) > 12:
            raise ValueError("limitations must be a bounded immutable tuple")
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 512
            for item in self.limitations
        ):
            raise ValueError("limitations must contain bounded nonempty text")


class _RegistryWithAll(Protocol):
    def all(self) -> Sequence[object]: ...


class PlatformOverviewService:
    """Build a read-only report from existing registry and metadata interfaces."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        identity: CorporationStatusSummary | None,
        tools: ToolRegistry | None,
    ) -> None:
        if not isinstance(orchestrator, Orchestrator):
            raise TypeError("orchestrator must be an Orchestrator")
        if identity is not None and not isinstance(
            identity, CorporationStatusSummary
        ):
            raise TypeError("identity must be a CorporationStatusSummary or None")
        if tools is not None and not isinstance(tools, ToolRegistry):
            raise TypeError("tools must be a ToolRegistry or None")
        self._orchestrator = orchestrator
        self._identity = identity
        self._tools = tools

    def report(self) -> PlatformOverviewReport:
        registries = (
            _registry_count(
                PlatformRegistryName.EMPLOYEES,
                self._orchestrator.employees,
            ),
            _registry_count(
                PlatformRegistryName.AGENTS,
                self._orchestrator.agents,
            ),
            _registry_count(
                PlatformRegistryName.PROVIDERS,
                self._orchestrator.providers,
            ),
            _registry_count(
                PlatformRegistryName.PROJECTS,
                self._orchestrator.projects,
            ),
            _registry_count(
                PlatformRegistryName.TASKS,
                self._orchestrator.tasks,
            ),
        )
        catalog = CapabilityRegistry(
            self._orchestrator.agents,
            self._tools,
        ).snapshot()
        record_counts = {
            source: sum(record.source is source for record in catalog.records)
            for source in CapabilitySource
        }
        capability_sources = (
            PlatformCapabilitySource(
                CapabilitySource.AGENT,
                (
                    PlatformSourceState.CONFIGURED
                    if self._orchestrator.agents is not None
                    else PlatformSourceState.UNAVAILABLE
                ),
                (
                    record_counts[CapabilitySource.AGENT]
                    if self._orchestrator.agents is not None
                    else None
                ),
            ),
            PlatformCapabilitySource(
                CapabilitySource.TOOL,
                (
                    PlatformSourceState.CONFIGURED
                    if self._tools is not None
                    else PlatformSourceState.UNAVAILABLE
                ),
                (
                    record_counts[CapabilitySource.TOOL]
                    if self._tools is not None
                    else None
                ),
            ),
            PlatformCapabilitySource(
                CapabilitySource.GEMINI_MODEL,
                PlatformSourceState.UNKNOWN,
                None,
            ),
        )
        return PlatformOverviewReport(
            observed_at=datetime.now(timezone.utc),
            identity=self._identity,
            identity_state=(
                PlatformSourceState.CONFIGURED
                if self._identity is not None
                else PlatformSourceState.UNAVAILABLE
            ),
            registries=registries,
            capability_catalog=catalog,
            capability_sources=capability_sources,
        )


def _registry_count(
    registry_name: PlatformRegistryName,
    registry: _RegistryWithAll | None,
) -> PlatformRegistryCount:
    if registry is None:
        return PlatformRegistryCount(
            registry_name,
            PlatformSourceState.UNAVAILABLE,
            None,
        )
    return PlatformRegistryCount(
        registry_name,
        PlatformSourceState.CONFIGURED,
        len(registry.all()),
    )


def _utf8_size(value: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("platform identity fields must contain valid Unicode") from exc
