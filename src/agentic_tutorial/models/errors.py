"""Normalised model-provider errors shared by all adapters."""

from __future__ import annotations

from collections.abc import Mapping

from agentic_tutorial.schemas import AgentError, ErrorClass


class ModelProviderError(Exception):
    """Base class for errors crossing the provider boundary."""

    error_code = "provider_error"
    error_class = ErrorClass.TERMINAL

    def __init__(self, message: str, *, provider: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.cause = cause

    def as_agent_error(self) -> AgentError:
        """Return a sanitised canonical representation for agent state."""
        return AgentError(
            error_class=self.error_class,
            code=self.error_code,
            message=str(self),
            source=self.provider,
        )


class AuthenticationError(ModelProviderError):
    """Credentials are missing or rejected."""

    error_code = "authentication_error"
    error_class = ErrorClass.HUMAN_ESCALATION


class RateLimitError(ModelProviderError):
    """The provider temporarily rejected a request quota."""

    error_code = "rate_limit"
    error_class = ErrorClass.RETRYABLE


class ModelTimeoutError(ModelProviderError):
    """The provider request exceeded its allotted time."""

    error_code = "model_timeout"
    error_class = ErrorClass.RETRYABLE


class InvalidModelResponseError(ModelProviderError):
    """The provider returned data that cannot satisfy canonical contracts."""

    error_code = "invalid_model_response"
    error_class = ErrorClass.RECOVERABLE


class UnsupportedCapabilityError(ModelProviderError):
    """A request requires a capability that the configured client lacks."""

    error_code = "unsupported_capability"
    error_class = ErrorClass.TERMINAL


def normalise_provider_exception(
    error: BaseException,
    *,
    provider: str,
    mappings: Mapping[type[BaseException], type[ModelProviderError]],
) -> ModelProviderError:
    """Map adapter-specific exception types into the shared error hierarchy."""
    if isinstance(error, ModelProviderError):
        return error
    for source_type, target_type in mappings.items():
        if isinstance(error, source_type):
            return target_type(str(error), provider=provider, cause=error)
    return InvalidModelResponseError(
        "unrecognised provider failure",
        provider=provider,
        cause=error,
    )
