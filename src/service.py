"""Validates which gateway may answer a request, asks it, and shapes the reply. app.py is only transport glue."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

import httpx

from src.contract import ChatRequest, ChatResult
from src.errors import GatewayError
from src.gateways import BaseGateway, build_gateway
from src.store import GatewayStore

REACHABLE_SECONDS = 15.0
PROBE_SECONDS = 3.0
USAGE = ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens")


class ChatService:
    def __init__(self, store: GatewayStore, settings: Any, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._store, self._settings, self._transport = store, settings, transport
        self._gateways: dict[str, tuple[dict[str, Any], BaseGateway]] = {}
        self._inflight = 0
        self._reachable: dict[str, tuple[float, bool]] = {}

    async def _gateway(self, gateway_id: str) -> BaseGateway:
        entry = (await asyncio.to_thread(self._store.all)).get(gateway_id)
        if entry is None:
            self._gateways.pop(gateway_id, None)
            raise GatewayError(422, "unknown_gateway", f"There is no gateway named '{gateway_id}'.")
        cached = self._gateways.get(gateway_id)
        if cached is None or cached[0] != entry:  # rebuilt when the saved entry changed
            cached = (entry, build_gateway(gateway_id, entry, self._transport))
            self._gateways[gateway_id] = cached
        return cached[1]

    @staticmethod
    def _check(gateway: BaseGateway, request: ChatRequest) -> None:
        for capability in sorted(request.uses):
            if capability == "images" and gateway.forwards_images:
                continue
            if not gateway.can(capability):
                raise GatewayError(422, f"{capability}_unsupported", f"The gateway '{gateway.id}' does not support {capability}.")
        limit = gateway.entry.get("max_tokens_limit")
        if request.max_tokens and limit and request.max_tokens > limit:
            raise GatewayError(422, "max_tokens_too_large", f"The gateway '{gateway.id}' allows at most {limit} max_tokens.")
        gateway.validate(request)

    async def check(self, request: ChatRequest) -> None:
        self._check(await self._gateway(request.gateway), request)

    def _enter(self) -> None:
        if self._inflight >= self._settings.max_inflight:
            raise GatewayError(429, "busy", "Too many chats at once.", retry_after=1)
        self._inflight += 1

    @staticmethod
    def _body(gateway: BaseGateway, result: ChatResult, streamed: bool, started: float) -> dict[str, Any]:
        body: dict[str, Any] = {"gateway": gateway.id, "provider": gateway.provider, "model": result.model or gateway.model,
                                "content": result.content}
        if result.reasoning:
            body["reasoning"] = result.reasoning
        if result.reasoning_state:
            body["reasoning_state"] = result.reasoning_state
        body.update(stop_reason=result.stop_reason, usage={k: int(result.usage.get(k) or 0) for k in USAGE},
                    duration_ms=round((time.perf_counter() - started) * 1000), streamed=streamed)
        return body

    async def chat(self, request: ChatRequest) -> dict[str, Any]:
        gateway = await self._gateway(request.gateway)
        self._check(gateway, request)
        self._enter()
        started = time.perf_counter()
        try:
            result = await gateway.complete(request)
        finally:
            self._inflight -= 1
        return self._body(gateway, result, False, started)

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        gateway = await self._gateway(request.gateway)
        self._check(gateway, request)
        self._enter()
        started = time.perf_counter()
        try:
            if not gateway.can("streams"):  # emulated: the finished answer in the same lines
                result = await gateway.complete(request)
                if result.reasoning:
                    yield {"type": "reasoning", "delta": result.reasoning}
                for block in result.content:
                    if block["type"] == "text":
                        yield {"type": "text", "delta": block["text"]}
                    elif block["type"] == "tool_call":
                        yield {"type": "tool_call", "id": block["id"], "name": block["name"], "arguments_delta": json.dumps(block["arguments"])}
                yield {"type": "done", **self._body(gateway, result, False, started)}
                return
            async for item in gateway.stream(request):
                if item[0] in ("text", "reasoning"):
                    yield {"type": item[0], "delta": item[1]}
                elif item[0] == "tool_call":
                    yield {"type": "tool_call", "id": item[1], "name": item[2], "arguments_delta": item[3]}
                else:
                    yield {"type": "done", **self._body(gateway, item[1], True, started)}
        finally:
            self._inflight -= 1

    async def _is_reachable(self, gateway: BaseGateway) -> bool:
        seen = self._reachable.get(gateway.id)
        if seen and time.monotonic() - seen[0] < REACHABLE_SECONDS:
            return seen[1]
        try:
            await asyncio.wait_for(gateway.probe(), PROBE_SECONDS)
            ok = True
        except (GatewayError, asyncio.TimeoutError):
            ok = False
        self._reachable[gateway.id] = (time.monotonic(), ok)
        return ok

    async def gateways(self) -> list[dict[str, Any]]:
        rows = await asyncio.to_thread(self._store.public)
        built = [await self._gateway(row["id"]) for row in rows]
        # Only Scuti services are probed on a listing: a probe of a paid provider costs a request.
        reachable = await asyncio.gather(*(self._is_reachable(g) if g.provider == "scuti" else asyncio.sleep(0, None) for g in built))
        out = []
        for row, g, ok in zip(rows, built, reachable):
            item = {**row, **g.capabilities}
            if ok is not None:
                item["reachable"] = ok
            out.append(item)
        return out

    async def test(self, gateway_id: str) -> str:
        try:
            gateway = await self._gateway(gateway_id)
        except GatewayError:
            raise GatewayError(404, "unknown_gateway", f"There is no gateway named '{gateway_id}'.") from None
        self._reachable.pop(gateway_id, None)
        return await gateway.probe()
