"""Shared error types for GFA."""

from __future__ import annotations


class GFAError(Exception):
    """Base class for all GFA errors."""

    def __init__(self, message: str, *, code: str = "gfa_error", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ConfigurationError(GFAError):
    pass


class ValidationError(GFAError):
    pass


class ProviderError(GFAError):
    pass


class ConnectionFailedError(ProviderError):
    pass


class RequestTimeoutError(ProviderError):
    pass


class CapabilityError(ProviderError):
    pass


class SessionError(GFAError):
    pass


class NotFoundError(GFAError):
    pass