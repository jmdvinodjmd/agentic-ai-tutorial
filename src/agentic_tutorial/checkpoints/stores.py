"""Atomic JSON and transactional SQLite checkpoint stores."""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from agentic_tutorial.schemas import SCHEMA_VERSION, AgentState

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class CheckpointError(Exception):
    """Checkpoint content or storage failed explicitly."""


@runtime_checkable
class CheckpointStore(Protocol):
    """Minimal asynchronous persistence interface used by the agent loop."""

    async def save(self, state: AgentState) -> None: ...

    async def load(self, run_id: str) -> AgentState | None: ...


class JsonCheckpointStore:
    """One atomically replaced canonical JSON document per run."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    async def save(self, state: AgentState) -> None:
        await asyncio.to_thread(self._save, state)

    async def load(self, run_id: str) -> AgentState | None:
        return await asyncio.to_thread(self._load, run_id)

    def _path(self, run_id: str) -> Path:
        if not _RUN_ID.fullmatch(run_id):
            raise CheckpointError("run_id is not safe for checkpoint storage")
        return self.directory / f"{run_id}.json"

    def _save(self, state: AgentState) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self._path(state.run_id)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.directory,
                prefix=f".{state.run_id}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(state.model_dump_json(indent=2))
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, target)
        except OSError as error:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
            raise CheckpointError(f"could not save checkpoint for {state.run_id}") from error

    def _load(self, run_id: str) -> AgentState | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            return AgentState.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            raise CheckpointError(f"invalid checkpoint for {run_id}") from error


class SQLiteCheckpointStore:
    """Transactional SQLite storage using only the Python standard library."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def save(self, state: AgentState) -> None:
        await asyncio.to_thread(self._save, state)

    async def load(self, run_id: str) -> AgentState | None:
        return await asyncio.to_thread(self._load, run_id)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints "
            "(run_id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, state_json TEXT NOT NULL)"
        )
        return connection

    def _save(self, state: AgentState) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO checkpoints(run_id, schema_version, state_json) VALUES (?, ?, ?) "
                    "ON CONFLICT(run_id) DO UPDATE SET "
                    "schema_version=excluded.schema_version, state_json=excluded.state_json",
                    (state.run_id, state.schema_version, state.model_dump_json()),
                )
        except sqlite3.Error as error:
            raise CheckpointError(f"could not save checkpoint for {state.run_id}") from error

    def _load(self, run_id: str) -> AgentState | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT schema_version, state_json FROM checkpoints WHERE run_id = ?", (run_id,)
                ).fetchone()
        except sqlite3.Error as error:
            raise CheckpointError(f"could not load checkpoint for {run_id}") from error
        if row is None:
            return None
        schema_version, state_json = row
        if schema_version != SCHEMA_VERSION:
            raise CheckpointError(
                f"unsupported checkpoint schema {schema_version!r}; expected {SCHEMA_VERSION!r}"
            )
        try:
            return AgentState.model_validate_json(state_json)
        except ValidationError as error:
            raise CheckpointError(f"invalid checkpoint for {run_id}") from error
