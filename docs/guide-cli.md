# ConversationGateway: HTTP and async client

Save a gateway and create a caller token on the admin pages at port 29407. Replace token placeholders locally. Tools run in the caller, never inside ConversationGateway.

## Validate and chat

```bash
curl -X POST http://127.0.0.1:29407/api/validate -H "X-Internal-Token: <SERVICE_TOKEN>" -H "Content-Type: application/json" -d '{"gateway":"claude","messages":[{"role":"user","content":"Hi"}]}'
```

```bash
curl -N -X POST http://127.0.0.1:29407/api/chat -H "X-Internal-Token: <SERVICE_TOKEN>" -H "Content-Type: application/json" -d '{"gateway":"claude","messages":[{"role":"user","content":"Hi"}],"stream":true}'
```

## Non-blocking Python client

Install dependencies with `uv sync` in the service project; httpx is included. On Windows set UV_CACHE_DIR=D:/User/.uv-cache and UV_LINK_MODE=copy before every uv command. Save this complete example as a local script, replace the token placeholder, then use `uv run` to execute it. Concurrent calls share one pooled client.

```python
"""Concurrent ConversationGateway calls; run with uv run local_chat.py."""
import asyncio
import httpx


class ConversationClient:
    """Own HTTP transport; keep application tool execution outside the gateway."""

    def __init__(self, http: httpx.AsyncClient, gateway: str) -> None:
        self.http = http
        self.gateway = gateway

    async def chat(self, text: str) -> dict:
        response = await self.http.post(
            "/api/chat",
            json={"gateway": self.gateway, "messages": [{"role": "user", "content": text}]},
        )
        response.raise_for_status()
        return response.json()


async def main() -> None:
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:29407",
        headers={"X-Internal-Token": "<SERVICE_TOKEN>"},
        timeout=300,
    ) as http:
        client = ConversationClient(http, "claude")
        for reply in await asyncio.gather(client.chat("Say hello"), client.chat("Say goodbye")):
            print(reply["content"])


if __name__ == "__main__":
    asyncio.run(main())
```

## Tool round trip

Send tools such as `[{"name":"get_time","parameters":{"type":"object","properties":{}}}]`. Append the returned assistant content, including reasoning_state when present, then append a tool message with a matching call id:

```json
{"role":"tool","content":[{"type":"tool_result","id":"c1","text":"12:00","is_error":false}]}
```

Send the complete messages and tools again. Structured output instead uses schema and cannot be combined with tools. Never execute untrusted tool arguments without the caller's own validation.