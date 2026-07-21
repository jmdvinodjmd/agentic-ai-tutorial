"""Provider-independent model interfaces and construction."""

from agentic_tutorial.models.config import (
    GenerationSettings,
    ModelCapabilities,
    ModelConfig,
    ModelProvider,
    model_config_from_environment,
)
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
    GeminiClient,
    LocalLlamaCppClient,
    LocalLlamaCppConfig,
    LocalModelMetadata,
    register_gemini_provider,
    register_local_llama_cpp_provider,
    register_offline_providers,
)
from agentic_tutorial.models.registry import (
    ProviderRegistry,
    create_model_client,
    provider_registry,
)

register_offline_providers(provider_registry)
register_local_llama_cpp_provider(provider_registry)
register_gemini_provider(provider_registry)

__all__ = [
    "AuthenticationError",
    "DeterministicMockClient",
    "GeminiClient",
    "GenerationSettings",
    "InvalidModelResponseError",
    "LocalLlamaCppClient",
    "LocalLlamaCppConfig",
    "LocalModelMetadata",
    "ModelCapabilities",
    "ModelClient",
    "ModelConfig",
    "ModelProvider",
    "ModelProviderError",
    "ModelTimeoutError",
    "ProviderRegistry",
    "RateLimitError",
    "UnsupportedCapabilityError",
    "create_model_client",
    "model_config_from_environment",
    "normalise_provider_exception",
    "provider_registry",
    "register_gemini_provider",
    "register_local_llama_cpp_provider",
    "validate_capabilities",
]
