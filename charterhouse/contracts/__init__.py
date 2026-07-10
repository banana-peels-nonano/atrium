"""Shared cross-subsystem types (docs/43 §6). Home of the frozen IF-1 surface — the event
envelope + vocabulary (``events``) and the venture/state projection types (``state``) — plus
the shared authorization types (``authz``: AuthClass/Token, docs/40 §4) and the frozen IF-2
Config-half shapes (``config_types``: Route/Model/Provider/Budgets, docs/40 §1)."""

from __future__ import annotations

from charterhouse.contracts.authz import ActionColor, AuthClass, Token
from charterhouse.contracts.config_types import Budgets, Model, Provider, Route
from charterhouse.contracts.events import (
    AUTHORIZATION_REQUIRED,
    GENESIS_PREV_HASH,
    ONCE_PER_LINEAGE,
    SCHEMA_VERSION,
    CapViolation,
    ChainBroken,
    Event,
    EventType,
    InvalidEnvelope,
    LedgerError,
    MissingAuthorization,
    PIIInPayload,
    ProjectionError,
    UnknownEventType,
)
from charterhouse.contracts.state import State, Venture, WorldState

__all__ = [
    "ActionColor",
    "AuthClass",
    "Token",
    "Budgets",
    "Model",
    "Provider",
    "Route",
    "AUTHORIZATION_REQUIRED",
    "GENESIS_PREV_HASH",
    "ONCE_PER_LINEAGE",
    "SCHEMA_VERSION",
    "CapViolation",
    "ChainBroken",
    "Event",
    "EventType",
    "InvalidEnvelope",
    "LedgerError",
    "MissingAuthorization",
    "PIIInPayload",
    "ProjectionError",
    "UnknownEventType",
    "State",
    "Venture",
    "WorldState",
]
