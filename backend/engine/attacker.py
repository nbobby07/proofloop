"""Attacker entry points. Proposals select trusted templates; no challenge execution here."""

from backend.providers.akash_client import AkashAttacker, ChallengeTemplate

__all__ = ["AkashAttacker", "ChallengeTemplate"]
