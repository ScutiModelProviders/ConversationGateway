"""Providers. A new provider is one adapter file plus one line in PROVIDERS."""
from __future__ import annotations

from typing import Any

import httpx

from src.gateways.base import BaseGateway

from src.gateways.anthropic import AnthropicGateway

PROVIDERS: dict[str, type[BaseGateway]] = {"anthropic": AnthropicGateway}


def build_gateway(gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> BaseGateway:
    return PROVIDERS[entry["provider"]](gateway_id, entry, transport)
