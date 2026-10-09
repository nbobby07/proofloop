"""Defender entry point for coordinator injection. Never applies a patch or decides a verdict."""

from backend.providers.openai_client import OpenAIDefender

__all__ = ["OpenAIDefender"]
