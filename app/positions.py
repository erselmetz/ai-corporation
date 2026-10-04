"""Ephemeral, owner-managed organizational position records."""
from dataclasses import dataclass, replace
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.agents import EmployeeRegistry

POSITION_TEMPLATES = (
    "Architect",
    "Developer",
    "Researcher",
    "Reasoning Analyst",
    "QA Engineer",
    "Security",
    "Code Reviewer",
    "Project Manager",
    "Technical Writer",
    "UI/UX",
)
MAX_POSITIONS = 100
MAX_POSITION_HISTORY = 100


class PositionNotFoundError(Exception):
    pass


class PositionConflictError(ValueError):
    pass


class PositionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PositionRevision:
    revision: int
    title: str
    responsibilities: tuple[str, ...]
    reports_to_position_id: str | None
    employee_id: str | None
    active: bool
    recorded_at: str


@dataclass(frozen=True)
class CorporationPosition:
    id: str
    title: str
    responsibilities: tuple[str, ...]
    reports_to_position_id: str | None
    employee_id: str | None
    active: bool
    revision: int
    history: tuple[PositionRevision, ...] = ()


class PositionRegistry:
    def __init__(self, employees: EmployeeRegistry | None):
        if employees is not None and not isinstance(employees, EmployeeRegistry):
            raise TypeError("employees must be an EmployeeRegistry or None")
        self._employees = employees
        self._positions: dict[str, CorporationPosition] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_fields(
        title: str,
        responsibilities: list[str] | tuple[str, ...],
        reports_to_position_id: str | None,
        employee_id: str | None,
    ) -> tuple[str, tuple[str, ...], str | None, str | None]:
        if not isinstance(title, str) or title not in POSITION_TEMPLATES:
            raise PositionValidationError("Choose a supported position template")
        if not isinstance(responsibilities, (list, tuple)) or not 1 <= len(responsibilities) <= 20:
            raise PositionValidationError("Supply 1 to 20 position responsibilities")
        normalized = []
        for item in responsibilities:
            if not isinstance(item, str) or not item.strip() or len(item.strip()) > 256:
                raise PositionValidationError("Responsibilities must be non-empty and at most 256 characters")
            normalized.append(item.strip())
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise PositionValidationError("Position responsibilities must be unique")
        for name, value in (
            ("reports_to_position_id", reports_to_position_id),
            ("employee_id", employee_id),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 256
            ):
                raise PositionValidationError(f"{name} is invalid")
        return title, tuple(normalized), reports_to_position_id, employee_id

    def list(self) -> tuple[CorporationPosition, ...]:
        with self._lock:
            return tuple(self._positions.values())

    def get(self, position_id: str) -> CorporationPosition:
        with self._lock:
            try:
                return self._positions[position_id]
            except KeyError:
                raise PositionNotFoundError from None

    def create(
        self,
        title: str,
        responsibilities: list[str] | tuple[str, ...],
        reports_to_position_id: str | None = None,
        employee_id: str | None = None,
    ) -> CorporationPosition:
        fields = self._validate_fields(
            title, responsibilities, reports_to_position_id, employee_id
        )
        with self._lock:
            if len(self._positions) >= MAX_POSITIONS:
                raise PositionConflictError("Position capacity reached")
            self._validate_references(
                None, fields[2], fields[3], active=True
            )
            position = CorporationPosition(
                id=f"position_{uuid4().hex}",
                title=fields[0],
                responsibilities=fields[1],
                reports_to_position_id=fields[2],
                employee_id=fields[3],
                active=True,
                revision=1,
            )
            self._positions[position.id] = position
            return position

    def update(
        self,
        position_id: str,
        expected_revision: int,
        title: str,
        responsibilities: list[str] | tuple[str, ...],
        reports_to_position_id: str | None,
        employee_id: str | None,
    ) -> CorporationPosition:
        fields = self._validate_fields(
            title, responsibilities, reports_to_position_id, employee_id
        )
        with self._lock:
            current = self._require(position_id)
            self._check_revision(current, expected_revision)
            self._validate_references(
                position_id, fields[2], fields[3], active=current.active
            )
            updated = self._revise(current, *fields, active=current.active)
            self._positions[position_id] = updated
            return updated

    def deactivate(self, position_id: str, expected_revision: int) -> CorporationPosition:
        with self._lock:
            current = self._require(position_id)
            self._check_revision(current, expected_revision)
            if not current.active:
                raise PositionConflictError("Position is already inactive")
            if any(
                item.active and item.reports_to_position_id == position_id
                for item in self._positions.values()
            ):
                raise PositionConflictError(
                    "Reassign or deactivate active reporting positions first"
                )
            updated = self._revise(
                current,
                current.title,
                current.responsibilities,
                current.reports_to_position_id,
                current.employee_id,
                active=False,
            )
            self._positions[position_id] = updated
            return updated

    def remove(self, position_id: str) -> None:
        with self._lock:
            current = self._require(position_id)
            if current.history or current.employee_id is not None:
                raise PositionConflictError(
                    "Position history or employee assignment requires deactivation, not removal"
                )
            if any(
                item.reports_to_position_id == position_id
                for item in self._positions.values()
            ):
                raise PositionConflictError(
                    "Reassign or remove reporting positions before removal"
                )
            del self._positions[position_id]

    @contextmanager
    def employee_reference_guard(self, employee_id: str):
        with self._lock:
            if any(item.employee_id == employee_id for item in self._positions.values()):
                raise PositionConflictError(
                    "Resolve position assignments before removing this Employee"
                )
            yield

    def _require(self, position_id: str) -> CorporationPosition:
        try:
            return self._positions[position_id]
        except KeyError:
            raise PositionNotFoundError from None

    @staticmethod
    def _check_revision(current: CorporationPosition, expected_revision: int) -> None:
        if current.revision != expected_revision:
            raise PositionConflictError("Position changed; refresh before editing")
        if len(current.history) >= MAX_POSITION_HISTORY:
            raise PositionConflictError("Position revision history limit reached")

    def _validate_references(
        self,
        current_id: str | None,
        reports_to_position_id: str | None,
        employee_id: str | None,
        *,
        active: bool,
    ) -> None:
        if reports_to_position_id is not None:
            parent = self._positions.get(reports_to_position_id)
            if parent is None or not parent.active:
                raise PositionValidationError("Reporting position must be an existing active position")
            ancestor_id: str | None = reports_to_position_id
            while ancestor_id is not None:
                if ancestor_id == current_id:
                    raise PositionValidationError("Reporting references cannot form a cycle")
                ancestor = self._positions.get(ancestor_id)
                ancestor_id = ancestor.reports_to_position_id if ancestor else None
        if employee_id is not None:
            if self._employees is None or not self._employees.exists(employee_id):
                raise PositionValidationError("Employee reference is not registered")
            if active and any(
                item.id != current_id and item.active and item.employee_id == employee_id
                for item in self._positions.values()
            ):
                raise PositionConflictError("Employee already occupies an active position")

    @staticmethod
    def _revise(
        current: CorporationPosition,
        title: str,
        responsibilities: tuple[str, ...],
        reports_to_position_id: str | None,
        employee_id: str | None,
        *,
        active: bool,
    ) -> CorporationPosition:
        revision = PositionRevision(
            revision=current.revision,
            title=current.title,
            responsibilities=current.responsibilities,
            reports_to_position_id=current.reports_to_position_id,
            employee_id=current.employee_id,
            active=current.active,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        return replace(
            current,
            title=title,
            responsibilities=responsibilities,
            reports_to_position_id=reports_to_position_id,
            employee_id=employee_id,
            active=active,
            revision=current.revision + 1,
            history=(*current.history, revision),
        )
