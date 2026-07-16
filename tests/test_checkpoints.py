"""Tests for checkpoint persistence and resumption."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from agentic_tutorial.checkpoints import (
    CheckpointError,
    CheckpointStore,
    JsonCheckpointStore,
    SQLiteCheckpointStore,
)
from agentic_tutorial.execution import PlainPythonAgent, minimal_research_task
from agentic_tutorial.schemas import ModelResponse
from agentic_tutorial.tools import ToolExecutor, build_tutorial_registry
from tests.test_agent_loop import ScriptClient, _finish, _search


@pytest.fixture(params=["json", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> CheckpointStore:
    if request.param == "json":
        return JsonCheckpointStore(tmp_path / "checkpoints")
    return SQLiteCheckpointStore(tmp_path / "checkpoints.sqlite3")


def _agent(responses: list[ModelResponse], store: CheckpointStore) -> PlainPythonAgent:
    return PlainPythonAgent(
        ScriptClient(responses),
        ToolExecutor(build_tutorial_registry()),
        allowed_tools=("catalogue_search",),
        checkpoint_store=store,
    )


def test_pause_resume_matches_uninterrupted_result(store: CheckpointStore) -> None:
    task = minimal_research_task()
    uninterrupted = asyncio.run(
        _agent([_search(), _finish()], store).run(task, run_id="uninterrupted")
    )
    interrupted = asyncio.run(
        _agent([_search()], store).run(task, run_id="resumed", interrupt_after_steps=1)
    )
    assert interrupted.termination is not None
    resumed = asyncio.run(_agent([_finish()], store).run(task, run_id="resumed", resume=True))
    assert resumed.final_answer == uninterrupted.final_answer
    assert resumed.usage.model_dump(exclude={"elapsed_seconds"}) == uninterrupted.usage.model_dump(
        exclude={"elapsed_seconds"}
    )
    assert resumed.usage.elapsed_seconds >= interrupted.usage.elapsed_seconds
    assert resumed.budget == interrupted.budget


def test_checkpoint_round_trip_preserves_state_and_usage(store: CheckpointStore) -> None:
    state = asyncio.run(
        _agent([_finish()], store).run(minimal_research_task(), run_id="round-trip")
    )
    loaded = asyncio.run(store.load("round-trip"))
    assert loaded == state
    assert loaded is not None and loaded.usage == state.usage


def test_corrupt_json_checkpoint_fails_explicitly(tmp_path: Path) -> None:
    directory = tmp_path / "checkpoints"
    directory.mkdir()
    (directory / "broken.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(CheckpointError, match="invalid checkpoint"):
        asyncio.run(JsonCheckpointStore(directory).load("broken"))


def test_schema_mismatch_fails_explicitly(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite3"
    store = SQLiteCheckpointStore(path)
    asyncio.run(store.load("initialise"))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO checkpoints(run_id, schema_version, state_json) VALUES (?, ?, ?)",
            ("old", "0", json.dumps({})),
        )
    with pytest.raises(CheckpointError, match="unsupported checkpoint schema"):
        asyncio.run(store.load("old"))


def test_json_atomic_save_leaves_no_temporary_file(tmp_path: Path) -> None:
    store = JsonCheckpointStore(tmp_path)
    asyncio.run(_agent([_finish()], store).run(minimal_research_task(), run_id="atomic"))
    assert [path.name for path in tmp_path.iterdir()] == ["atomic.json"]
