"""Read-only capability inventory assembled from existing runtime sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.agents import AgentRegistry
from app.integrations.gemini_catalog import (
    GeminiCatalogAuditEvent,
    GeminiCatalogAuditStatus,
    GeminiModel,
    GeminiModelCapability,
    GeminiModelCatalogResult,
    MAX_GEMINI_MODELS_PER_REQUEST,
)
from app.integrations.models import IntegrationCapability
from app.tools import ToolRegistry

MAX_CAPABILITY_RECORDS = 2_000
MAX_CAPABILITY_LABEL_CHARACTERS = 512
MAX_CAPABILITY_DESCRIPTION_CHARACTERS = 2_048
MAX_CAPABILITY_NOTE_CHARACTERS = 512


class CapabilitySource(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    INTEGRATION_SCOPE = "integration_scope"
    GEMINI_MODEL = "gemini_model"


class CapabilityEvidence(str, Enum):
    AGENT_DECLARED = "agent_declared"
    TOOL_REGISTERED = "tool_registered"
    SCOPE_ONLY = "scope_only"
    SERVICE_REPORTED = "service_reported"


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    source: CapabilitySource
    source_id: str
    capability: str
    evidence: CapabilityEvidence
    owner_id: str
    owner_name: str
    description: str
    requirements: tuple[str, ...] | None
    policy_boundaries: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.source, CapabilitySource):
            raise TypeError("source must be a CapabilitySource")
        if not isinstance(self.evidence, CapabilityEvidence):
            raise TypeError("evidence must be a CapabilityEvidence")
        for field_name, value in (
            ("source_id", self.source_id),
            ("capability", self.capability),
            ("owner_id", self.owner_id),
            ("owner_name", self.owner_name),
        ):
            _validate_text(
                value,
                field_name,
                MAX_CAPABILITY_LABEL_CHARACTERS,
            )
        _validate_text(
            self.description,
            "description",
            MAX_CAPABILITY_DESCRIPTION_CHARACTERS,
            allow_line_breaks=True,
        )
        if self.requirements is not None:
            _validate_notes(self.requirements, "requirements")
        _validate_notes(self.policy_boundaries, "policy_boundaries")
        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CapabilityCatalogSnapshot:
    generated_at: datetime
    records: tuple[CapabilityRecord, ...]
    gemini_catalog_retrieved_at: datetime | None = None
    gemini_catalog_model_count: int | None = None
    gemini_catalog_has_more: bool | None = None
    limitations: tuple[str, ...] = (
        "This is a sequential read of independent sources, not an atomic cross-registry snapshot.",
        "Evidence describes declarations, registrations, scopes, or service metadata; it does not grant access or guarantee execution.",
        "Gemini metadata is included only when the caller supplies an existing catalog result; no network request is made.",
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise ValueError("generated_at must be timezone-aware")
        if not isinstance(self.records, tuple) or not all(
            isinstance(record, CapabilityRecord) for record in self.records
        ):
            raise TypeError("records must be an immutable tuple of CapabilityRecords")
        if len(self.records) > MAX_CAPABILITY_RECORDS:
            raise ValueError("capability snapshot exceeds its record limit")
        if self.gemini_catalog_retrieved_at is not None and (
            not isinstance(self.gemini_catalog_retrieved_at, datetime)
            or self.gemini_catalog_retrieved_at.tzinfo is None
            or self.gemini_catalog_retrieved_at.utcoffset() is None
        ):
            raise ValueError("Gemini catalog time must be timezone-aware")
        if self.gemini_catalog_model_count is not None and (
            not isinstance(self.gemini_catalog_model_count, int)
            or isinstance(self.gemini_catalog_model_count, bool)
            or not (
                0
                <= self.gemini_catalog_model_count
                <= MAX_GEMINI_MODELS_PER_REQUEST
            )
        ):
            raise ValueError("Gemini model count is invalid")
        if self.gemini_catalog_has_more is not None and not isinstance(
            self.gemini_catalog_has_more, bool
        ):
            raise TypeError("Gemini catalog completeness must be a bool or None")
        _validate_notes(self.limitations, "limitations")


def _validate_text(
    value: str,
    field_name: str,
    maximum: int,
    *,
    allow_line_breaks: bool = False,
) -> None:
    allowed_controls = "\t\n\r" if allow_line_breaks else ""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(
            ord(character) < 32 and character not in allowed_controls
            for character in value
        )
    ):
        raise ValueError(f"{field_name} is invalid or exceeds its size limit")


def _validate_notes(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be an immutable tuple")
    for value in values:
        _validate_text(value, field_name, MAX_CAPABILITY_NOTE_CHARACTERS)


class CapabilityRegistry:
    """Aggregate existing declarations without creating a new source of authority."""

    def __init__(
        self,
        agents: AgentRegistry | None,
        tools: ToolRegistry | None = None,
    ) -> None:
        if agents is not None and not isinstance(agents, AgentRegistry):
            raise TypeError("agents must be an AgentRegistry or None")
        if tools is not None and not isinstance(tools, ToolRegistry):
            raise TypeError("tools must be a ToolRegistry or None")
        self._agents = agents
        self._tools = tools

    def snapshot(
        self,
        *,
        gemini_catalog: GeminiModelCatalogResult | None = None,
    ) -> CapabilityCatalogSnapshot:
        if gemini_catalog is not None and not isinstance(
            gemini_catalog, GeminiModelCatalogResult
        ):
            raise TypeError("gemini_catalog must be a GeminiModelCatalogResult")
        if gemini_catalog is not None and (
            not isinstance(gemini_catalog.models, tuple)
            or len(gemini_catalog.models) > MAX_GEMINI_MODELS_PER_REQUEST
        ):
            raise ValueError("Gemini catalog models must be a bounded immutable tuple")
        if gemini_catalog is not None and (
            not isinstance(gemini_catalog.audit_event, GeminiCatalogAuditEvent)
            or gemini_catalog.audit_event.service != "gemini"
            or gemini_catalog.audit_event.operation != "list_models"
            or gemini_catalog.audit_event.status
            is not GeminiCatalogAuditStatus.SUCCEEDED
            or not isinstance(gemini_catalog.has_more, bool)
            or gemini_catalog.audit_event.occurred_at
            != gemini_catalog.retrieved_at
            or gemini_catalog.audit_event.model_count != len(gemini_catalog.models)
            or gemini_catalog.audit_event.has_more is not gemini_catalog.has_more
        ):
            raise ValueError(
                "Gemini catalog must contain a matching successful audit event"
            )

        records: list[CapabilityRecord] = []
        identities: set[tuple[CapabilitySource, str, str]] = set()

        agents = () if self._agents is None else self._agents.all()
        for agent in agents:
            for capability in dict.fromkeys(agent.capabilities):
                observed_at = datetime.now(timezone.utc)
                self._append(
                    records,
                    identities,
                    CapabilityRecord(
                        source=CapabilitySource.AGENT,
                        source_id=agent.id,
                        capability=capability,
                        evidence=CapabilityEvidence.AGENT_DECLARED,
                        owner_id=agent.id,
                        owner_name=agent.name,
                        description=f"Agent-declared capability: {capability}.",
                        requirements=(
                            "The Agent is registered and declares this capability.",
                        ),
                        policy_boundaries=(
                            "Self-declared metadata; it does not verify competence or grant authorization.",
                        ),
                        observed_at=observed_at,
                    ),
                )

        tools = () if self._tools is None else self._tools.all()
        for tool in tools:
            observed_at = datetime.now(timezone.utc)
            self._append(
                records,
                identities,
                CapabilityRecord(
                    source=CapabilitySource.TOOL,
                    source_id=tool.id,
                    capability="tool.execute",
                    evidence=CapabilityEvidence.TOOL_REGISTERED,
                    owner_id=tool.id,
                    owner_name=tool.name,
                    description=tool.description,
                    requirements=("The Tool is explicitly registered in ToolRegistry.",),
                    policy_boundaries=(
                        "Registration does not authorize or execute the Tool; no Agent integration is implied.",
                    ),
                    observed_at=observed_at,
                ),
            )

        for scope in IntegrationCapability:
            observed_at = datetime.now(timezone.utc)
            scope_name = scope.name.replace("_", " ").title()
            self._append(
                records,
                identities,
                CapabilityRecord(
                    source=CapabilitySource.INTEGRATION_SCOPE,
                    source_id=scope.value,
                    capability=scope.value,
                    evidence=CapabilityEvidence.SCOPE_ONLY,
                    owner_id="integration_pipeline",
                    owner_name="Integration pipeline",
                    description=(
                        f"{scope_name} is a possible request scope, not an active capability."
                    ),
                    requirements=None,
                    policy_boundaries=(
                        "Scope metadata only; it grants no permission and performs no execution.",
                    ),
                    observed_at=observed_at,
                ),
            )

        if gemini_catalog is not None:
            self._append_gemini_records(
                records,
                identities,
                gemini_catalog,
            )

        records.sort(
            key=lambda record: (
                record.source.value,
                record.source_id.casefold(),
                record.source_id,
                record.capability.casefold(),
                record.capability,
            )
        )
        return CapabilityCatalogSnapshot(
            generated_at=datetime.now(timezone.utc),
            records=tuple(records),
            gemini_catalog_retrieved_at=(
                None if gemini_catalog is None else gemini_catalog.retrieved_at
            ),
            gemini_catalog_model_count=(
                None if gemini_catalog is None else len(gemini_catalog.models)
            ),
            gemini_catalog_has_more=(
                None if gemini_catalog is None else gemini_catalog.has_more
            ),
        )

    def _append_gemini_records(
        self,
        records: list[CapabilityRecord],
        identities: set[tuple[CapabilitySource, str, str]],
        catalog: GeminiModelCatalogResult,
    ) -> None:
        if (
            not isinstance(catalog.retrieved_at, datetime)
            or catalog.retrieved_at.tzinfo is None
            or catalog.retrieved_at.utcoffset() is None
        ):
            raise ValueError("Gemini catalog timestamp must be timezone-aware")
        for model in catalog.models:
            if not isinstance(model, GeminiModel):
                raise TypeError("Gemini catalog contains invalid model metadata")
            if not isinstance(model.capabilities, tuple):
                if model.capabilities is None:
                    continue
                raise TypeError("Gemini model capabilities must be an immutable tuple")
            for capability in model.capabilities:
                if not isinstance(capability, GeminiModelCapability):
                    raise TypeError("Gemini catalog contains invalid capability metadata")
                self._append(
                    records,
                    identities,
                    CapabilityRecord(
                        source=CapabilitySource.GEMINI_MODEL,
                        source_id=model.model_id,
                        capability=capability.value,
                        evidence=CapabilityEvidence.SERVICE_REPORTED,
                        owner_id="google_gemini_api",
                        owner_name="Google Gemini API",
                        description=(
                            f"Gemini reports {capability.value} for {model.model_id}."
                        ),
                        requirements=None,
                        policy_boundaries=(
                            "Service-reported metadata does not establish job suitability, hardware feasibility, or execution success.",
                        ),
                        observed_at=catalog.retrieved_at,
                    ),
                )

    @staticmethod
    def _append(
        records: list[CapabilityRecord],
        identities: set[tuple[CapabilitySource, str, str]],
        record: CapabilityRecord,
    ) -> None:
        identity = (record.source, record.source_id, record.capability)
        if identity in identities:
            raise ValueError("Capability sources contain duplicate records")
        if len(records) >= MAX_CAPABILITY_RECORDS:
            raise ValueError("Capability catalog exceeds its record limit")
        identities.add(identity)
        records.append(record)
