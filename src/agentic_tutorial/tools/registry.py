"""Typed Python-function registration with canonical tool definitions."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, create_model

from agentic_tutorial.schemas import ToolDefinition, ToolSideEffect

ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class RegisteredTool:
    """Internal executable paired with portable canonical metadata."""

    definition: ToolDefinition
    arguments_model: type[BaseModel]
    handler: ToolHandler


class ToolRegistry:
    """Registry shared by plain Python and future framework adapters."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        handler: ToolHandler,
        *,
        name: str | None = None,
        description: str | None = None,
        version: str = "1",
        side_effect: ToolSideEffect = ToolSideEffect.READ_ONLY,
    ) -> RegisteredTool:
        """Derive an argument schema from a fully typed function."""
        tool_name = name or handler.__name__
        if tool_name in self._tools:
            raise ValueError(f"tool already registered: {tool_name}")
        signature = inspect.signature(handler)
        hints = get_type_hints(handler)
        fields: dict[str, Any] = {}
        for parameter_name, parameter in signature.parameters.items():
            if parameter.kind not in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                raise TypeError("tools may use only named parameters")
            if parameter_name not in hints:
                raise TypeError(f"tool parameter {parameter_name!r} requires a type annotation")
            default = parameter.default
            fields[parameter_name] = (
                hints[parameter_name],
                ... if default is inspect.Parameter.empty else default,
            )
        if "return" not in hints:
            raise TypeError("tool return value requires a type annotation")
        arguments_model = create_model(
            f"{tool_name.title().replace('_', '')}Arguments",
            __config__=ConfigDict(extra="forbid", frozen=True),
            **fields,
        )
        parameters = arguments_model.model_json_schema()
        definition = ToolDefinition(
            name=tool_name,
            description=description or inspect.getdoc(handler) or f"Execute {tool_name}.",
            parameters=parameters,
            version=version,
            side_effect=side_effect,
        )
        registered = RegisteredTool(definition, arguments_model, handler)
        self._tools[tool_name] = registered
        return registered

    def tool(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        version: str = "1",
        side_effect: ToolSideEffect = ToolSideEffect.READ_ONLY,
    ) -> Callable[[ToolHandler], ToolHandler]:
        """Return a decorator that preserves the original callable."""

        def decorator(handler: ToolHandler) -> ToolHandler:
            self.register(
                handler,
                name=name,
                description=description,
                version=version,
                side_effect=side_effect,
            )
            return handler

        return decorator

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Return definitions in deterministic name order."""
        return tuple(self._tools[name].definition for name in sorted(self._tools))
