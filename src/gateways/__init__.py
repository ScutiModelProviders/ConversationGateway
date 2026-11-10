"""Providers. A new provider is one adapter file plus one line in PROVIDERS."""
from __future__ import annotations

from typing import Any

import httpx

from src.gateways.base import BaseGateway

PROVIDERS: dict[str, type[BaseGateway]] = {}  # filled in by tasks 4 to 6


def build_gateway(gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> BaseGateway:
    return PROVIDERS[entry["provider"]](gateway_id, entry, transport)
