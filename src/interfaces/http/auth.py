"""API authentication for the HTTP interface layer.

Protected endpoints require a valid API key / bearer token. The set of
accepted keys is loaded from configuration (never hardcoded) and injected
into ``Authenticator`` from the composition root.

Security posture: FAIL CLOSED. If no keys are configured, every protected
request is denied with 401. A valid token in either supported header lets
the request through.

Supported credential headers (checked in order):
    Authorization: Bearer <token>
    X-API-Key: <token>
"""

from __future__ import annotations

import secrets
from typing import Awaitable, Callable, Iterable

from fastapi import Request
from fastapi.exceptions import HTTPException


class Authenticator:
    """Validates incoming requests against a configured set of API keys."""

    def __init__(self, api_keys: Iterable[str]) -> None:
        # Store as a tuple so we can do constant-time comparisons against each.
        self._api_keys: tuple[str, ...] = tuple(k for k in api_keys if k)

    @property
    def configured(self) -> bool:
        """True if at least one key is configured. Empty => fail closed."""
        return bool(self._api_keys)

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        authorization = request.headers.get("Authorization")
        if authorization:
            scheme, _, credentials = authorization.partition(" ")
            if scheme.lower() == "bearer" and credentials.strip():
                return credentials.strip()
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header and api_key_header.strip():
            return api_key_header.strip()
        return None

    def _is_valid(self, token: str) -> bool:
        # Constant-time comparison against every configured key to avoid
        # leaking key length / prefix via timing.
        valid = False
        for known in self._api_keys:
            if secrets.compare_digest(token, known):
                valid = True
        return valid

    def authenticate(self, request: Request) -> None:
        """Raise 401 unless the request carries a valid, configured key."""
        if not self.configured:
            # FAIL CLOSED: no keys configured -> deny everything.
            raise HTTPException(
                status_code=401,
                detail="Authentication is not configured; access denied.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = self._extract_token(request)
        if token is None:
            raise HTTPException(
                status_code=401,
                detail="Missing API credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not self._is_valid(token):
            raise HTTPException(
                status_code=401,
                detail="Invalid API credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def dependency(self) -> Callable[[Request], Awaitable[None]]:
        """Return a FastAPI dependency that enforces authentication."""

        async def _require_auth(request: Request) -> None:
            self.authenticate(request)

        return _require_auth
