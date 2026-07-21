"""Thin provider adapters included in the shared foundation."""

from agentic_tutorial.models.providers.gemini import GeminiClient, register_gemini_provider
from agentic_tutorial.models.providers.local_llama_cpp import (
    LocalLlamaCppClient,
    LocalLlamaCppConfig,
    LocalModelMetadata,
    register_local_llama_cpp_provider,
)
from agentic_tutorial.models.providers.mock import DeterministicMockClient
from agentic_tutorial.models.providers.registration import register_offline_providers

__all__ = [
    "DeterministicMockClient",
    "GeminiClient",
    "LocalLlamaCppClient",
    "LocalLlamaCppConfig",
    "LocalModelMetadata",
    "register_gemini_provider",
    "register_local_llama_cpp_provider",
    "register_offline_providers",
]
