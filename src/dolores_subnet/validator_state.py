"""Durable epoch allocation and crash recovery for recurring validator ticks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from dolores_subnet.atomic import ExclusiveFileLock, atomic_write_json
from dolores_subnet.epoch import (
    EpochCompletionValidationError,
    chain_attempt_path,
    chain_receipt_path,
    completion_marker_path,
    verify_epoch_completion,
)

ValidatorPhase = Literal[
    "allocated",
    "querying",
    "evaluating",
    "weights_submitting",
    "committed",
]
PHASES = frozenset(
    {"allocated", "querying", "evaluating", "weights_submitting", "committed"}
)
STATE_VERSION = 1


class ValidatorStateError(RuntimeError):
    """Base error for invalid or unsafe validator runtime state."""


class StateCorruptionError(ValidatorStateError):
    """The durable state or recovery receipt is malformed."""


class AmbiguousWeightSubmissionError(ValidatorStateError):
    """A crash may have happened after submitting weights but before receipt persistence."""


class ReceiptRecoveryRequired(ValidatorStateError):
    """A durable receipt exists and must be recovered explicitly."""


@dataclass(frozen=True)
class ValidatorRuntimeState:
    version: int = STATE_VERSION
    next_epoch_id: int = 1
    active_epoch_id: int | None = None
    phase: ValidatorPhase | None = None
    attempt: int = 0
    last_completed_epoch: int | None = None
    last_failed_epoch: int | None = None
    last_error: str | None = None
    last_receipt: dict[str, object] | None = None
    last_successful_weight_receipt: dict[str, object] | None = None
    updated_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ValidatorRuntimeState:
        try:
            state = cls(
                version=int(payload.get("version", 0)),
                next_epoch_id=int(payload.get("next_epoch_id", 0)),
                active_epoch_id=_optional_int(payload.get("active_epoch_id")),
                phase=_optional_phase(payload.get("phase")),
                attempt=int(payload.get("attempt", 0)),
                last_completed_epoch=_optional_int(payload.get("last_completed_epoch")),
                last_failed_epoch=_optional_int(payload.get("last_failed_epoch")),
                last_error=_optional_string(payload.get("last_error")),
                last_receipt=_optional_dict(payload.get("last_receipt")),
                last_successful_weight_receipt=_optional_dict(
                    payload.get("last_successful_weight_receipt")
                ),
                updated_at=str(payload.get("updated_at", "")),
            )
        except (TypeError, ValueError) as exc:
            raise StateCorruptionError(f"invalid validator state fields: {exc}") from exc
        state.validate()
        return state

    def validate(self) -> None:
        if self.version != STATE_VERSION:
            raise StateCorruptionError(
                f"unsupported validator state version: {self.version}"
            )
        if self.next_epoch_id < 1:
            raise StateCorruptionError("next_epoch_id must be positive")
        if self.attempt < 0:
            raise StateCorruptionError("attempt must be non-negative")
        if (self.active_epoch_id is None) != (self.phase is None):
            raise StateCorruptionError("active_epoch_id and phase must be set together")
        if self.active_epoch_id is not None:
            if self.active_epoch_id < 1 or self.next_epoch_id <= self.active_epoch_id:
                raise StateCorruptionError("active epoch must be allocated below next_epoch_id")
            if self.attempt < 1:
                raise StateCorruptionError("active epoch must have a positive attempt")
        if self.phase == "committed" and self.last_completed_epoch != self.active_epoch_id:
            raise StateCorruptionError("committed phase must match last_completed_epoch")


class ValidatorStateStore:
    """Own durable state and allocate one serialized tick at a time."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.archive_dir = self.root.parent
        self.state_path = self.root / "state.json"
        self.lock_path = self.root / "tick.lock"

    def read(self) -> ValidatorRuntimeState:
        if not self.state_path.exists():
            return ValidatorRuntimeState()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateCorruptionError(f"cannot read validator state: {exc}") from exc
        if not isinstance(payload, dict):
            raise StateCorruptionError("validator state must be a JSON object")
        return ValidatorRuntimeState.from_dict(payload)

    def tick(self) -> ValidatorTick:
        return ValidatorTick(self)

    def recover_receipt(self) -> ValidatorRuntimeState:
        """Commit only a fully verified canonical epoch completion marker."""

        with ExclusiveFileLock(self.lock_path):
            state = self.read()
            if state.phase != "weights_submitting" or state.active_epoch_id is None:
                raise ValidatorStateError("no weights-submitting epoch is awaiting recovery")
            self._raise_if_ambiguous_attempt(state.active_epoch_id)
            if not self.completion_path(state.active_epoch_id).is_file():
                if self.receipt_path(state.active_epoch_id).is_file():
                    raise AmbiguousWeightSubmissionError(
                        f"epoch {state.active_epoch_id} has a receipt written before artifacts "
                        "but no canonical completion marker"
                    )
                raise AmbiguousWeightSubmissionError(
                    f"epoch {state.active_epoch_id} has no canonical completion marker"
                )
            recovered = self._commit_from_completion(state, state.active_epoch_id)
            self._write(recovered)
            return recovered

    def _begin_locked(self) -> tuple[ValidatorRuntimeState, int]:
        state = self.read()
        if state.phase == "weights_submitting":
            assert state.active_epoch_id is not None
            self._raise_if_ambiguous_attempt(state.active_epoch_id)
            marker = self.completion_path(state.active_epoch_id)
            if marker.is_file():
                raise ReceiptRecoveryRequired(
                    f"epoch {state.active_epoch_id} has a completion marker at {marker}; "
                    "call recover_receipt() explicitly"
                )
            receipt = self.receipt_path(state.active_epoch_id)
            if receipt.is_file():
                receipt_payload = _load_json_object(receipt, label="chain receipt")
                if receipt_payload.get("epoch_id") != state.active_epoch_id:
                    raise StateCorruptionError("canonical chain receipt epoch mismatch")
                receipt_mode = receipt_payload.get("mode")
                if receipt_mode not in {"dry_run", "skipped", "error"}:
                    raise AmbiguousWeightSubmissionError(
                        f"epoch {state.active_epoch_id} has a receipt but no canonical "
                        "completion marker; chain state requires reconciliation"
                    )
                state = replace(
                    state,
                    active_epoch_id=None,
                    phase=None,
                    attempt=0,
                    last_failed_epoch=state.active_epoch_id,
                    last_error=(
                        f"interrupted_after_{receipt_mode}_receipt_before_completion"
                    ),
                    updated_at=_now(),
                )
                self._write(state)
            else:
                raise AmbiguousWeightSubmissionError(
                    f"epoch {state.active_epoch_id} stopped during weights_submitting "
                    "without a canonical completion marker; reconcile chain state before "
                    "continuing"
                )

        if state.phase in {"allocated", "querying"}:
            retried = replace(
                state,
                phase="allocated",
                attempt=state.attempt + 1,
                updated_at=_now(),
            )
            self._write(retried)
            assert retried.active_epoch_id is not None
            return retried, retried.active_epoch_id

        if state.phase == "evaluating":
            state = replace(
                state,
                active_epoch_id=None,
                phase=None,
                attempt=0,
                last_failed_epoch=state.active_epoch_id,
                last_error="interrupted_during_evaluation",
                updated_at=_now(),
            )

        epoch_id = state.next_epoch_id
        allocated = replace(
            state,
            next_epoch_id=epoch_id + 1,
            active_epoch_id=epoch_id,
            phase="allocated",
            attempt=1,
            updated_at=_now(),
        )
        self._write(allocated)
        return allocated, epoch_id

    def _transition_locked(
        self,
        *,
        epoch_id: int,
        phase: ValidatorPhase,
    ) -> ValidatorRuntimeState:
        state = self.read()
        if state.active_epoch_id != epoch_id or state.phase is None:
            raise ValidatorStateError(f"epoch {epoch_id} is not the active validator tick")
        if phase == state.phase:
            return state
        allowed: dict[ValidatorPhase, frozenset[ValidatorPhase]] = {
            "allocated": frozenset({"querying", "evaluating"}),
            "querying": frozenset({"evaluating"}),
            "evaluating": frozenset({"weights_submitting"}),
            "weights_submitting": frozenset({"committed"}),
            "committed": frozenset(),
        }
        if phase not in allowed[state.phase]:
            raise ValidatorStateError(f"invalid phase transition: {state.phase} -> {phase}")
        if phase == "committed":
            committed = self._commit_from_completion(state, epoch_id)
            self._write(committed)
            return committed
        updates: dict[str, object] = {"phase": phase, "updated_at": _now()}
        transitioned = replace(state, **updates)
        self._write(transitioned)
        return transitioned

    def _fail_evaluation_locked(self, *, epoch_id: int, error: str) -> ValidatorRuntimeState:
        state = self.read()
        if state.active_epoch_id != epoch_id or state.phase != "evaluating":
            raise ValidatorStateError(f"epoch {epoch_id} is not in evaluating phase")
        failed = replace(
            state,
            active_epoch_id=None,
            phase=None,
            attempt=0,
            last_failed_epoch=epoch_id,
            last_error=error,
            updated_at=_now(),
        )
        self._write(failed)
        return failed

    def _fail_weights_locked(self, *, epoch_id: int, error: str) -> ValidatorRuntimeState:
        state = self.read()
        if state.active_epoch_id != epoch_id or state.phase != "weights_submitting":
            raise ValidatorStateError(f"epoch {epoch_id} is not in weights_submitting phase")
        if self.attempt_path(epoch_id).is_file():
            raise AmbiguousWeightSubmissionError(
                f"epoch {epoch_id} has a live chain attempt and cannot be failed automatically"
            )
        failed = replace(
            state,
            active_epoch_id=None,
            phase=None,
            attempt=0,
            last_failed_epoch=epoch_id,
            last_error=error,
            updated_at=_now(),
        )
        self._write(failed)
        return failed

    def _record_receipt_locked(
        self,
        *,
        epoch_id: int,
        receipt: dict[str, object],
    ) -> ValidatorRuntimeState:
        state = self.read()
        if (
            state.active_epoch_id != epoch_id
            or state.phase != "committed"
            or state.last_completed_epoch != epoch_id
        ):
            raise ValidatorStateError(
                f"epoch {epoch_id} receipt requires a committed active tick"
            )
        # The completion transition already recorded the canonical verified
        # receipt. Keep this compatibility seam read-only so callers cannot
        # replace it with an arbitrary path or payload.
        expected = state.last_receipt or {}
        if (
            receipt.get("mode") != expected.get("mode")
            or receipt.get("reason") != expected.get("reason")
        ):
            raise ValidatorStateError("receipt does not match canonical completion marker")
        return state

    def receipt_path(self, epoch_id: int) -> Path:
        return chain_receipt_path(self.archive_dir, epoch_id)

    def completion_path(self, epoch_id: int) -> Path:
        return completion_marker_path(self.archive_dir, epoch_id)

    def attempt_path(self, epoch_id: int) -> Path:
        return chain_attempt_path(self.archive_dir, epoch_id)

    def _raise_if_ambiguous_attempt(self, epoch_id: int) -> None:
        path = self.attempt_path(epoch_id)
        if not path.exists():
            return
        attempt = _load_json_object(path, label="chain attempt")
        if attempt.get("epoch_id") != epoch_id or attempt.get("mode") != "live_attempt":
            raise StateCorruptionError(f"invalid canonical chain attempt: {path}")
        status = attempt.get("status")
        if status not in {"started", "ambiguous", "completed"}:
            raise StateCorruptionError(f"unknown chain attempt status: {status!r}")
        if status != "completed":
            raise AmbiguousWeightSubmissionError(
                f"epoch {epoch_id} has an ambiguous live chain attempt at {path}; "
                "automatic recovery and resubmission are forbidden"
            )

    def _commit_from_completion(
        self,
        state: ValidatorRuntimeState,
        epoch_id: int,
    ) -> ValidatorRuntimeState:
        self._raise_if_ambiguous_attempt(epoch_id)
        marker = self.completion_path(epoch_id)
        if not marker.is_file():
            raise AmbiguousWeightSubmissionError(
                f"epoch {epoch_id} has no canonical completion marker"
            )
        try:
            completed = verify_epoch_completion(self.archive_dir, epoch_id)
        except EpochCompletionValidationError as exc:
            raise StateCorruptionError(f"invalid epoch completion: {exc}") from exc
        receipt = completed["receipt"]
        assert isinstance(receipt, dict)
        miner_state = completed["miner_state"]
        if not isinstance(miner_state, dict):
            raise StateCorruptionError("completion marker has invalid miner state")
        atomic_write_json(self.archive_dir / "miner_state.json", miner_state)
        canonical_receipt = {
            str(key): value for key, value in receipt.items()
        }
        canonical_receipt["completion_marker"] = str(marker)
        return replace(
            state,
            phase="committed",
            last_completed_epoch=epoch_id,
            last_error=None,
            last_receipt=canonical_receipt,
            last_successful_weight_receipt=(
                canonical_receipt
                if _receipt_succeeded(canonical_receipt)
                else state.last_successful_weight_receipt
            ),
            updated_at=_now(),
        )

    def _write(self, state: ValidatorRuntimeState) -> None:
        state.validate()
        atomic_write_json(self.state_path, state.to_dict())


class ValidatorTick:
    """Context that retains the exclusive OS lock across a complete tick."""

    def __init__(self, store: ValidatorStateStore) -> None:
        self.store = store
        self.lock = ExclusiveFileLock(store.lock_path)
        self.epoch_id: int | None = None
        self._entered = False

    @property
    def state(self) -> ValidatorRuntimeState:
        if self.epoch_id is None:
            raise ValidatorStateError("validator tick has not started")
        return self.store.read()

    def __enter__(self) -> ValidatorTick:
        self.lock.acquire()
        try:
            _, self.epoch_id = self.store._begin_locked()
            self._entered = True
            return self
        except BaseException:
            self.lock.release()
            raise

    def __exit__(self, exc_type, exc, traceback) -> bool:  # noqa: ANN001
        del exc_type, traceback
        try:
            if self._entered and self.epoch_id is not None:
                state = self.store.read()
                if state.active_epoch_id == self.epoch_id and state.phase == "evaluating":
                    detail = str(exc) if exc is not None else "evaluation_exited_without_result"
                    self.store._fail_evaluation_locked(epoch_id=self.epoch_id, error=detail)
        finally:
            self._entered = False
            self.lock.release()
        return False

    def transition(self, phase: ValidatorPhase) -> ValidatorRuntimeState:
        if not self._entered or self.epoch_id is None or not self.lock.held:
            raise ValidatorStateError("phase transition requires an active locked tick")
        return self.store._transition_locked(epoch_id=self.epoch_id, phase=phase)

    def mark_querying(self) -> ValidatorRuntimeState:
        return self.transition("querying")

    def phase_hook(self, phase: str) -> None:
        if phase not in {"evaluating", "weights_submitting", "committed"}:
            raise ValidatorStateError(f"run_epoch emitted an unknown phase: {phase}")
        self.transition(phase)  # type: ignore[arg-type]

    def fail_evaluation(self, error: str) -> ValidatorRuntimeState:
        if not self._entered or self.epoch_id is None or not self.lock.held:
            raise ValidatorStateError("evaluation failure requires an active locked tick")
        return self.store._fail_evaluation_locked(epoch_id=self.epoch_id, error=error)

    def fail_weights(self, error: str) -> ValidatorRuntimeState:
        if not self._entered or self.epoch_id is None or not self.lock.held:
            raise ValidatorStateError("weights failure requires an active locked tick")
        return self.store._fail_weights_locked(epoch_id=self.epoch_id, error=error)

    def record_receipt(self, receipt: dict[str, object]) -> ValidatorRuntimeState:
        if not self._entered or self.epoch_id is None or not self.lock.held:
            raise ValidatorStateError("receipt recording requires an active locked tick")
        return self.store._record_receipt_locked(epoch_id=self.epoch_id, receipt=receipt)


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateCorruptionError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StateCorruptionError(f"{label} must be a JSON object")
    return {str(key): value for key, value in payload.items()}


def _receipt_succeeded(receipt: dict[str, object]) -> bool:
    return receipt.get("mode") in {"dry_run", "submitted"}


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_dict(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("last_receipt must be an object")
    return {str(key): item for key, item in value.items()}


def _optional_phase(value: object) -> ValidatorPhase | None:
    if value is None:
        return None
    phase = str(value)
    if phase not in PHASES:
        raise ValueError(f"unknown validator phase: {phase}")
    return phase  # type: ignore[return-value]


def _now() -> str:
    return datetime.now(UTC).isoformat()
