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
    def __init__(self, employees: EmployeeRegistry | None, *, persistence=None):
        if employees is not None and not isinstance(employees, EmployeeRegistry):
            raise TypeError("employees must be an EmployeeRegistry or None")
        self._employees = employees
        self._persistence = persistence
        self._positions: dict[str, CorporationPosition] = {}
        self._lock = RLock()
        if persistence is not None:
            self._restore(persistence.load_positions())

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
            try:
                self._persist()
            except Exception:
                del self._positions[position.id]
                raise
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
            try:
                self._persist()
            except Exception:
                self._positions[position_id] = current
                raise
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
            try:
                self._persist()
            except Exception:
                self._positions[position_id] = current
                raise
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
            try:
                self._persist()
            except Exception:
                self._positions[position_id] = current
                raise

    @contextmanager
    def employee_reference_guard(self, employee_id: str):
        with self._lock:
            if any(item.employee_id == employee_id for item in self._positions.values()):
                raise PositionConflictError(
                    "Resolve position assignments before removing this Employee"
                )
            yield

    def _persist(self) -> None:
        if self._persistence is None:
            return
        self._persistence.save_positions(tuple(_position_record(item) for item in self._positions.values()))

    def _restore(self, records) -> None:
        """Restore persisted state only through the registry's domain validation."""
        if not isinstance(records, tuple) or len(records) > MAX_POSITIONS:
            raise RuntimeError("Stored position state is invalid")
        restored: dict[str, CorporationPosition] = {}
        try:
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError
                identifier = record["id"]
                title, responsibilities, parent, employee = self._validate_fields(
                    record["title"], tuple(record["responsibilities"]),
                    record["reports_to_position_id"], record["employee_id"],
                )
                active, revision = record["active"], record["revision"]
                if type(active) is not bool or type(revision) is not int or revision < 1:
                    raise ValueError
                if not isinstance(identifier, str) or not identifier.strip() or identifier in restored:
                    raise ValueError
                raw_history = record["history"]
                if not isinstance(raw_history, list) or len(raw_history) != revision - 1 or len(raw_history) > MAX_POSITION_HISTORY:
                    raise ValueError
                history_items = []
                for index, item in enumerate(raw_history):
                    old_title, old_responsibilities, old_parent, old_employee = self._validate_fields(
                        item["title"], tuple(item["responsibilities"]),
                        item["reports_to_position_id"], item["employee_id"],
                    )
                    if (type(item["revision"]) is not int or item["revision"] != index + 1
                            or type(item["active"]) is not bool
                            or not isinstance(item["recorded_at"], str)
                            or not item["recorded_at"]):
                        raise ValueError
                    history_items.append(PositionRevision(
                        item["revision"], old_title, old_responsibilities, old_parent,
                        old_employee, item["active"], item["recorded_at"],
                    ))
                history = tuple(history_items)
                restored[identifier] = CorporationPosition(
                    identifier, title, responsibilities, parent, employee,
                    active, revision, history,
                )
            previous = self._positions
            self._positions = restored
            for item in restored.values():
                self._validate_references(
                    item.id, item.reports_to_position_id, item.employee_id,
                    active=item.active,
                )
            self._positions = previous
            # Validate the hierarchy as a whole, including cycles that may have
            # entered through a stale/corrupt or manually edited database.
            for identifier in restored:
                seen = set()
                cursor = identifier
                while cursor is not None:
                    if cursor in seen:
                        raise ValueError
                    seen.add(cursor)
                    parent = restored.get(cursor)
                    cursor = parent.reports_to_position_id if parent else None
            self._positions = restored
        except Exception:
            self._positions = {}
            raise RuntimeError("Stored position state failed validation; no records were loaded") from None


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


def _position_record(item: CorporationPosition) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "responsibilities": list(item.responsibilities),
        "reports_to_position_id": item.reports_to_position_id,
        "employee_id": item.employee_id,
        "active": item.active,
        "revision": item.revision,
        "history": [{
            "revision": revision.revision,
            "title": revision.title,
            "responsibilities": list(revision.responsibilities),
            "reports_to_position_id": revision.reports_to_position_id,
            "employee_id": revision.employee_id,
            "active": revision.active,
            "recorded_at": revision.recorded_at,
        } for revision in item.history],
    }
