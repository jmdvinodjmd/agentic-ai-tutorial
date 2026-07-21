"""Deterministic tools shared by matched case-study notebooks."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalysisRequest(BaseModel):
    """Validated request for the one permitted tutorial aggregation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    group_column: str = Field(pattern="^intervention$")
    before_column: str = Field(pattern="^before_kg$")
    after_column: str = Field(pattern="^after_kg$")


def summarise_reduction(path: Path, request: AnalysisRequest) -> dict[str, float]:
    """Compute mean before-minus-after values without executing model-authored code."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {request.group_column, request.before_column, request.after_column}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("dataset does not satisfy the approved analysis schema")
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row[request.group_column]].append(
            float(row[request.before_column]) - float(row[request.after_column])
        )
    return {group: round(sum(values) / len(values), 2) for group, values in sorted(grouped.items())}


def file_sha256(path: Path) -> str:
    """Return reproducibility provenance for one input file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SimulatedService:
    """In-memory service with permissions and idempotent address updates."""

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._state = deepcopy(fixture)
        self._receipts: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_path(cls, path: Path) -> SimulatedService:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def read_order(self, order_id: str, *, actor: str) -> dict[str, Any]:
        self._require(actor, "order:read")
        order = self._state["orders"].get(order_id)
        if order is None:
            raise KeyError("unknown order")
        return deepcopy(order)

    def update_address(
        self,
        order_id: str,
        new_address: str,
        *,
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require(actor, "order:update_address")
        if idempotency_key in self._receipts:
            return deepcopy(self._receipts[idempotency_key])
        order = self._state["orders"].get(order_id)
        if order is None:
            raise KeyError("unknown order")
        order["delivery_address"] = new_address
        receipt = {
            "status": "updated",
            "order_id": order_id,
            "delivery_address": new_address,
            "idempotency_key": idempotency_key,
            "duplicate": False,
        }
        self._receipts[idempotency_key] = receipt
        return deepcopy(receipt)

    def replay(self, idempotency_key: str) -> dict[str, Any] | None:
        receipt = self._receipts.get(idempotency_key)
        if receipt is None:
            return None
        replayed = deepcopy(receipt)
        replayed["duplicate"] = True
        return replayed

    def checkpoint(self) -> dict[str, Any]:
        return {"state": deepcopy(self._state), "receipts": deepcopy(self._receipts)}

    @classmethod
    def resume(cls, checkpoint: dict[str, Any]) -> SimulatedService:
        service = cls(checkpoint["state"])
        service._receipts = deepcopy(checkpoint["receipts"])
        return service

    def _require(self, actor: str, permission: str) -> None:
        if permission not in self._state["permissions"].get(actor, []):
            raise PermissionError(f"actor lacks {permission}")
