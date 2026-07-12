"""S8 provider adapters (docs/11): one OpenAI-compatible adapter covers ~all providers;
Anthropic/Gemini are thin translation shims; Grok is a named OpenAI-compatible subclass.
Every cloud adapter enforces the INV-PII-3 guard before any send (base.py).
"""

from charterhouse.router.adapters.anthropic import AnthropicAdapter
from charterhouse.router.adapters.base import BaseAdapter
from charterhouse.router.adapters.gemini import GeminiAdapter
from charterhouse.router.adapters.openai_compat import GrokAdapter, OpenAICompatibleAdapter

__all__ = [
    "AnthropicAdapter",
    "BaseAdapter",
    "GeminiAdapter",
    "GrokAdapter",
    "OpenAICompatibleAdapter",
]
