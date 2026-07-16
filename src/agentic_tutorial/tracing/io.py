"""Append-only JSONL trace writing, sanitisation, reading and normalisation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue, TypeAdapter, ValidationError

from agentic_tutorial.tracing.events import TraceEvent, TraceEventType


class TraceWriter:
    """Write canonical events to ``outputs/runs/<run_id>/trace.jsonl`` style paths."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        redact_values: Sequence[str] = (),
        redact_keys: Sequence[str] = ("api_key", "authorization", "token", "secret"),
    ) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self.redact_values = tuple(value for value in redact_values if value)
        self.redact_keys = {key.casefold() for key in redact_keys}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = TraceReader(self.path).read() if self.path.exists() else ()
        if existing and any(event.run_id != run_id for event in existing):
            raise ValueError("existing trace belongs to a different run")
        self._sequence = len(existing)

    def emit(
        self,
        event_type: TraceEventType,
        payload: Mapping[str, object],
        *,
        timestamp: datetime | None = None,
    ) -> TraceEvent:
        """Sanitise and append one event."""
        self._sequence += 1
        sanitised = _sanitise(dict(payload), self.redact_keys, self.redact_values)
        canonical: dict[str, JsonValue] = TypeAdapter(dict[str, JsonValue]).validate_python(
            sanitised
        )
        event = TraceEvent(
            run_id=self.run_id,
            sequence=self._sequence,
            timestamp=timestamp or datetime.now(UTC),
            event_type=event_type,
            payload=canonical,
        )
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(event.model_dump_json() + "\n")
        return event


class TraceReader:
    """Read and validate complete canonical event sequences."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> tuple[TraceEvent, ...]:
        if not self.path.exists():
            return ()
        try:
            events = tuple(
                TraceEvent.model_validate_json(line)
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            )
        except (OSError, ValidationError) as error:
            raise ValueError(f"invalid canonical trace: {self.path}") from error
        if events:
            if [event.sequence for event in events] != list(range(1, len(events) + 1)):
                raise ValueError("trace sequence numbers must be consecutive from one")
            if len({event.run_id for event in events}) != 1:
                raise ValueError("trace contains multiple run identifiers")
        return events


def normalise_events(events: Sequence[TraceEvent]) -> bytes:
    """Normalise generated identifiers, times and durations for deterministic tests."""
    normalised: list[dict[str, JsonValue]] = []
    for event in events:
        payload = _normalise_durations(event.payload)
        normalised.append(
            {
                "trace_schema_version": event.trace_schema_version,
                "run_id": "<run_id>",
                "sequence": event.sequence,
                "timestamp": "<timestamp>",
                "event_type": event.event_type.value,
                "payload": payload,
            }
        )
    return json.dumps(normalised, sort_keys=True, separators=(",", ":")).encode()


def _sanitise(value: object, keys: set[str], secrets: tuple[str, ...]) -> object:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>"
            if str(key).casefold() in keys
            else _sanitise(item, keys, secrets)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitise(item, keys, secrets) for item in value]
    if isinstance(value, str):
        result = value
        for secret in secrets:
            result = result.replace(secret, "<redacted>")
        return result
    return value


def _normalise_durations(value: JsonValue, key: str = "") -> JsonValue:
    if isinstance(value, dict):
        return {name: _normalise_durations(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_normalise_durations(item, key) for item in value]
    if isinstance(value, str) and value.startswith(("{", "[")):
        try:
            nested: JsonValue = TypeAdapter(JsonValue).validate_python(json.loads(value))
        except (json.JSONDecodeError, ValidationError):
            return value
        return json.dumps(_normalise_durations(nested), sort_keys=True, separators=(",", ":"))
    if key == "run_id":
        return "<run_id>"
    if key == "seconds" or key.endswith(
        ("elapsed_ms", "elapsed_seconds", "duration_ms", "duration_seconds")
    ):
        return 0
    return value
