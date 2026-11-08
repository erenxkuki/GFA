"""Shared HTTP helpers for model providers."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from gfa.shared.errors import ConnectionFailedError, RequestTimeoutError


def build_client(timeout: float, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, headers=headers or {}, follow_redirects=True)


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 2,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code >= 500 and attempt < max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            return resp
        except httpx.TimeoutException as exc:
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise RequestTimeoutError(f"Request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise ConnectionFailedError(f"HTTP error: {exc}") from exc
    if last_exc is not None:
        raise ConnectionFailedError(str(last_exc))
    raise ConnectionFailedError("Unknown request failure")