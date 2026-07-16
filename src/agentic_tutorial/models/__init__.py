"""Provider-independent model interfaces and construction."""

from agentic_tutorial.models.config import GenerationSettings, ModelCapabilities, ModelConfig
from agentic_tutorial.models.errors import (
    AuthenticationError,
    InvalidModelResponseError,
    ModelProviderError,
    ModelTimeoutError,
    RateLimitError,
    UnsupportedCapabilityError,
    normalise_provider_exception,
)
from agentic_tutorial.models.interface import ModelClient, validate_capabilities
from agentic_tutorial.models.providers import (
    DeterministicMockClient,
    ReplayClient,
    ReplayMismatchError,
    register_offline_providers,
)
from agentic_tutorial.models.registry import (
    ProviderRegistry,
    create_model_client,
    provider_registry,
)

register_offline_providers(provider_registry)

__all__ = [
    "AuthenticationError",
    "DeterministicMockClient",
    "GenerationSettings",
    "InvalidModelResponseError",
    "ModelCapabilities",
    "ModelClient",
    "ModelConfig",
    "ModelProviderError",
    "ModelTimeoutError",
    "ProviderRegistry",
    "RateLimitError",
    "ReplayClient",
    "ReplayMismatchError",
    "UnsupportedCapabilityError",
    "create_model_client",
    "normalise_provider_exception",
    "provider_registry",
    "validate_capabilities",
]
