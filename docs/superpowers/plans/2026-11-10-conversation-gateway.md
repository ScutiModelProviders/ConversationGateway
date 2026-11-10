# ConversationGateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build ConversationGateway, a tool service on port 29407 that gives callers one HTTP contract for chat models (messages, tool calls, reasoning, images, structured output, streaming) through saved gateways of three providers: `anthropic`, `openai` (including `gemini`) and `scuti` (CNV model services).

**Architecture:** A sibling of `AI/ToolServices/DecisionGateway`: Starlette plus an empty FastMCP shell, shared admin files copied byte-identical from Bard, an own gateways page, gateway entries in `gateways.json`. Callers name a gateway. Adapters translate one normalized request into the provider's API and the reply back. Tool calls pass through to the caller; there is no tool loop.

**Tech Stack:** Python 3.11+, uv, Starlette/FastMCP, `anthropic` and `openai` SDKs (with `http_client=httpx.AsyncClient(transport=...)` so tests use `httpx.MockTransport`), async httpx for Scuti, pydantic, uvicorn, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-11-10-conversation-gateway-design.md` (read it first; this plan implements it).

**Template:** `AI/ToolServices/DecisionGateway` is the working reference for layout, admin wiring, store, app, gateways page, launchers, Docker and docs. Read the file named in each task before changing the copy.

## Global Constraints

- Port 29407. Environment prefix `SERVICE_`. Caller token prefix `dg_` is DecisionGateway's; here it is `cg_`.
- Python `>=3.11`. Use `uv` with `UV_CACHE_DIR=D:/User/.uv-cache` and `UV_LINK_MODE=copy` on Windows for every uv command.
- Tests use `httpx.MockTransport` only: no real network, no API keys.
- Never read or print `.env*`, `gateways.json`, `tokens.json`, `settings.json`. Secrets (`api_key`, `token`, `aws_access_key_id`, `aws_secret_access_key`) are write-only in responses, logs and errors.
- Copy these files byte-identical from Bard and never edit them: `src/admin_api.py`, `src/tokens.py`, `src/middleware.py`, `src/runtime.py`, `web/index.html`, `web/playground.js`, `tests/test_admin_api.py`, `tests/test_tokens.py`, `tests/seed.py`, `tests/test_env_file.py`, `tools/check_sync.py`. Only the lines matched by `ALLOWED` in `check_sync.py` (`PREFIX = `, `const CONFIG = `) may differ. If a copied test fails, stop and report.
- Public routes are under `/api/`. Own admin routes are under `/admin/gateways`.
- No tool execution, no sessions, no failover, no model tiers, no response cache, no stored prompts or replies. Logs: gateway id, model, status, token counts, duration only.
- Commits: author name from `git -C ../Bard config user.name`, email `214214011+scutiii2@users.noreply.github.com`. Do not push, add a remote, or run `tools/publish_live.py`.
- Blocking file work runs through `asyncio.to_thread`.
- SDK call details below (parameter and event names) follow the public `anthropic` and `openai` SDKs. If the installed version differs, fix the call, keep the behavior, and say so in the commit message.

## File structure

| File | Responsibility |
|---|---|
| `src/errors.py` | `GatewayError(status, code, message, kind, retry_after)` |
| `src/config.py`, `src/options.py` | Settings from the environment; admin-editable limits |
| `src/contract.py` | `Limits`, `ChatRequest`, `ChatResult`, `parse_request` |
| `src/failure.py` | `scrub`, `upstream_error`: upstream status and text to `GatewayError` with `kind` |
| `src/gateways/base.py` | `BaseGateway`: capabilities, client, `guard()`, SDK error mapping |
| `src/gateways/anthropic.py` | Anthropic Messages adapter (key, bedrock, vertex) |
| `src/gateways/openai.py` | OpenAI adapter (`api: chat` and `api: responses`, key and azure) |
| `src/gateways/scuti.py` | CNV `/v1/chat` adapter |
| `src/gateways/__init__.py` | `PROVIDERS` registry, `build_gateway` |
| `src/presets.py` | Preset gateway entries (no secrets) for the gateways page |
| `src/store.py` | `GatewayStore`: validated entries in `gateways.json` |
| `src/service.py` | `ChatService`: pick gateway, capability check, in-flight cap, body shaping, emulated streaming |
| `src/gateways_api.py` | `/admin/gateways*` routes |
| `src/app.py`, `src/run.py` | HTTP transport glue and launcher |
| `web/gateways.html` | Own gateways page |

Normalized message shapes used everywhere after parsing:

```python
# message  = {"role": "user"|"assistant"|"tool", "content": [block, ...], "reasoning_state": str (assistant only, optional)}
# block    = {"type": "text", "text": str}
#          | {"type": "image", "media_type": str, "data": str}                       # base64
#          | {"type": "tool_call", "id": str, "name": str, "arguments": dict}
#          | {"type": "tool_result", "id": str, "text": str, "is_error": bool}
# tool     = {"name": str, "description": str, "parameters": dict}
# schema   = {"name": str, "schema": dict, "strict": bool}
# reasoning= {"effort": "low"|"medium"|"high"|None, "budget_tokens": int|None}      # at least one set
```

Adapter interface (`BaseGateway`):

```python
async def complete(self, request: ChatRequest) -> ChatResult
def stream(self, request: ChatRequest) -> AsyncIterator[tuple]   # ("text", str) | ("reasoning", str) | ("tool_call", id, name, args_delta) | ("done", ChatResult)
async def probe(self) -> str                                       # raises GatewayError
def validate(self, request: ChatRequest) -> None                   # adapter-specific 422s
```

---

### Task 1: Scaffold, shared files, settings

**Files:**
- Create: whole repo skeleton from DecisionGateway: `.gitignore`, `.dockerignore`, `pyproject.toml`, `src/__init__.py`, `src/config.py`, `src/options.py`, `src/errors.py`, `src/run.py`, `tests/__init__.py`, `tests/test_config.py`
- Copy byte-identical from Bard: the shared files listed in Global Constraints
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (frozen dataclass), `load_settings()`, `GatewayError`, `schema(base)`, `make_config(base)`, `live(base, config)`.

- [ ] **Step 1: Copy the skeleton.** From `../DecisionGateway` copy `.gitignore`, `.dockerignore`, `src/__init__.py`, `tests/__init__.py`, `tests/test_config.py`, `src/run.py`. From `../Bard` copy the shared files into the same relative paths. In the copied `src/run.py` replace `DecisionGateway refuses` with `ConversationGateway refuses`.

- [ ] **Step 2: Write `src/errors.py`.**

```python
"""The one error every layer raises. `message` is safe to show: no paths, URLs or credentials."""
from __future__ import annotations


class GatewayError(Exception):
    """`kind` is rate_limit, quota, auth or unavailable for upstream failures a caller may react to, else None."""

    def __init__(self, status: int, code: str, message: str, kind: str | None = None, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.kind, self.retry_after = status, code, message, kind, retry_after

    def body(self) -> dict:
        error = {"code": self.code, "message": self.message}
        if self.kind:
            error["kind"] = self.kind
        return {"error": error}
```

- [ ] **Step 3: Write `src/config.py`.** Start from DecisionGateway's `src/config.py`. Change the module docstring to `ConversationGateway settings`, the default port to 29407 (both places), remove `max_chars`, `cache_*`, and add these fields and environment reads:

```python
    max_messages: int = 500
    max_text: int = 400000
    max_tools: int = 128
    max_images: int = 20
    max_image_mb: int = 16
    max_inflight: int = 16
```

```python
        max_messages=int(env("SERVICE_MAX_MESSAGES", "500")),
        max_text=int(env("SERVICE_MAX_TEXT", "400000")),
        max_tools=int(env("SERVICE_MAX_TOOLS", "128")),
        max_images=int(env("SERVICE_MAX_IMAGES", "20")),
        max_image_mb=int(env("SERVICE_MAX_IMAGE_MB", "16")),
        max_inflight=int(env("SERVICE_MAX_INFLIGHT", "16")),
```

Keep `state_dir`, `exposed_without_auth`, `with_saved_data_path`, `load_settings` unchanged.

- [ ] **Step 4: Write `src/options.py`.**

```python
"""The options the admin page can change. A saved value wins over the environment value shown as default."""
from __future__ import annotations

from src.config import Settings
from src.runtime import Config, LiveSettings, Setting

FIELDS = {  # Settings attribute -> (setting key, conversion)
    "max_messages": ("max_messages", int),
    "max_text": ("max_text", int),
    "max_tools": ("max_tools", int),
    "max_images": ("max_images", int),
    "max_image_mb": ("max_image_mb", int),
    "max_inflight": ("max_inflight", int),
}


def schema(base: Settings) -> list[Setting]:
    return [
        Setting("max_messages", "Most messages per request", "int", base.max_messages, minimum=1, maximum=5000),
        Setting("max_text", "Longest text block (characters)", "int", base.max_text, minimum=1, maximum=5000000),
        Setting("max_tools", "Most tools per request", "int", base.max_tools, minimum=1, maximum=1024),
        Setting("max_images", "Most images per request", "int", base.max_images, minimum=1, maximum=200),
        Setting("max_image_mb", "Largest image (MiB)", "int", base.max_image_mb, minimum=1, maximum=64),
        Setting("max_inflight", "Chats at once", "int", base.max_inflight, minimum=1, maximum=256,
                help="More than this many at once get 429 with Retry-After."),
        Setting("data_path", "Data folder", "text", "", restart=True,
                help=f"Where stored data goes. Empty = {base.state_dir}. Applies after a restart; files already stored are not moved."),
    ]


def make_config(base: Settings) -> Config | None:
    """None, so nothing is changeable at run time, unless SERVICE_ADMIN_PASSWORD is set."""
    return Config(base.state_dir / "settings.json", schema(base)) if base.admin_password else None


def live(base: Settings, config: Config | None):
    return LiveSettings(base, config, FIELDS) if config else base
```

- [ ] **Step 5: Write `pyproject.toml`.**

```toml
[project]
name = "conversationgateway"
version = "1.0.0"
description = "One HTTP contract for chat models (Anthropic, OpenAI-compatible including Gemini, Scuti model services)"
requires-python = ">=3.11"
dependencies = [
    "mcp==1.28.0",
    "pydantic==2.13.4",
    "uvicorn==0.49.0",
    "python-dotenv==1.2.2",
    "httpx>=0.27",
    "anthropic[bedrock,vertex]>=0.40",
    "openai>=1.66",
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 6: Fix the config test.** In the copied `tests/test_config.py` change the expected default port to 29407 and drop assertions about removed fields. Add:

```python
def test_limit_defaults():
    s = Settings()
    assert (s.port, s.max_messages, s.max_text, s.max_tools, s.max_images, s.max_image_mb, s.max_inflight) == (29407, 500, 400000, 128, 20, 16, 16)
```

- [ ] **Step 7: Allow the new sibling in the shared check.** `tools/check_sync.py` is shared and byte-identical, so do not edit it in this task. Task 11 adds `ConversationGateway` to every copy at once. Until then `python tools/check_sync.py` in this repo exits 0 because the file equals Bard's.

- [ ] **Step 8: Run and commit.**

Run: `uv sync` then `uv run pytest -q`
Expected: config, admin_api, tokens, env_file tests pass. If a copied test fails, stop and report.

```bash
git add -A && git commit -m "feat: scaffold, shared admin files and settings"
```

---

### Task 2: Request contract

**Files:**
- Create: `src/contract.py`, `tests/helpers.py`, `tests/test_contract.py`

**Interfaces:**
- Consumes: `GatewayError`.
- Produces: `Limits(max_messages, max_text, max_tools, max_images, max_image_bytes)`, `Limits.from_settings(settings)`, `ChatRequest` (frozen dataclass: `gateway, model, system, messages, tools, tool_choice, schema, reasoning, max_tokens, temperature, cache, stream` and property `uses -> set[str]` over `images tools reasoning schema`), `ChatResult(content, reasoning, reasoning_state, stop_reason, usage, model)`, `parse_request(data, limits) -> ChatRequest`.

- [ ] **Step 1: Write the failing tests `tests/test_contract.py`.**

```python
import pytest

from src.contract import Limits, parse_request
from src.errors import GatewayError
from tests.helpers import LIMITS, chat

PNG = "aGVsbG8="


def refused(**fields):
    with pytest.raises(GatewayError) as error:
        chat(**fields)
    assert error.value.status == 422 and error.value.code == "invalid_request"
    return error.value.message


def test_string_content_is_one_text_block():
    request = chat()
    assert request.messages == [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}]
    assert request.uses == set() and request.tool_choice is None and request.cache is False and request.stream is False


def test_full_request_is_normalized():
    request = chat(
        system="Be brief", model="m", max_tokens=100, temperature=0.5, cache=True, stream=True,
        messages=[
            {"role": "user", "content": [{"type": "text", "text": "Look"}, {"type": "image", "media_type": "image/png", "data": PNG}]},
            {"role": "assistant", "content": [{"type": "tool_call", "id": "c1", "name": "get_time", "arguments": {}}], "reasoning_state": "x"},
            {"role": "tool", "content": [{"type": "tool_result", "id": "c1", "text": "12:00"}]},
        ],
        tools=[{"name": "get_time"}], reasoning={"effort": "low"})
    assert request.messages[2]["content"][0]["is_error"] is False
    assert request.tools == [{"name": "get_time", "description": "", "parameters": {"type": "object", "properties": {}}}]
    assert request.tool_choice == "auto"
    assert request.reasoning == {"effort": "low", "budget_tokens": None}
    assert request.uses == {"images", "tools", "reasoning"}


def test_reasoning_defaults_to_medium_when_empty():
    assert chat(reasoning={}).reasoning == {"effort": "medium", "budget_tokens": None}


def test_unknown_fields_are_refused():
    assert "unexpected" in refused(unexpected=1)
    refused(messages=[{"role": "user", "content": [{"type": "text", "text": "x", "extra": 1}]}])


@pytest.mark.parametrize("fields", [
    {"messages": []},
    {"messages": [{"role": "system", "content": "x"}]},
    {"messages": [{"role": "user", "content": [{"type": "tool_call", "id": "a", "name": "n", "arguments": {}}]}]},
    {"messages": [{"role": "user", "content": [{"type": "text", "text": ""}]}]},
    {"messages": [{"role": "user", "content": [{"type": "image", "media_type": "image/tiff", "data": PNG}]}]},
    {"messages": [{"role": "user", "content": "x", "reasoning_state": "s"}]},
    {"tools": [{"name": "bad name"}]},
    {"tools": [{"name": "a"}, {"name": "a"}]},
    {"tool_choice": "required"},
    {"tools": [{"name": "a"}], "tool_choice": {"name": "b"}},
    {"tools": [{"name": "a"}], "schema": {"name": "s", "schema": {}}},
    {"reasoning": {"effort": "extreme"}},
    {"reasoning": {"budget_tokens": 0}},
    {"max_tokens": 0}, {"max_tokens": True}, {"temperature": 3}, {"cache": "yes"}, {"stream": 1},
])
def test_bad_requests(fields):
    refused(**fields)


def test_limits():
    small = Limits(max_messages=1, max_text=5, max_tools=1, max_images=1, max_image_bytes=4)
    base = {"gateway": "g", "messages": [{"role": "user", "content": "Hi"}]}
    for body in (
        {**base, "messages": base["messages"] * 2},
        {**base, "messages": [{"role": "user", "content": "toolong"}]},
        {**base, "tools": [{"name": "a"}, {"name": "b"}]},
        {**base, "messages": [{"role": "user", "content": [{"type": "image", "media_type": "image/png", "data": "A" * 8}]}]},
    ):
        with pytest.raises(GatewayError) as error:
            parse_request(body, small)
        assert error.value.status == 422


def test_gateway_is_required():
    with pytest.raises(GatewayError):
        parse_request({"messages": [{"role": "user", "content": "x"}]}, LIMITS)
```

`tests/helpers.py`:

```python
from src.contract import Limits, parse_request

LIMITS = Limits(max_messages=500, max_text=400_000, max_tools=128, max_images=20, max_image_bytes=16 * 1024 * 1024)


def chat(gateway: str = "g", **fields):
    """A parsed ChatRequest; keyword arguments are request fields."""
    return parse_request({"gateway": gateway, "messages": [{"role": "user", "content": "Hi"}], **fields}, LIMITS)
```

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_contract.py -q`. Expected: ImportError on `src.contract`.

- [ ] **Step 3: Write `src/contract.py`.**

```python
"""The chat request: validated and normalized once, so adapters never re-check shapes."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.errors import GatewayError

TOP = {"gateway", "model", "system", "messages", "tools", "tool_choice", "schema", "reasoning", "max_tokens",
       "temperature", "cache", "stream"}
BLOCKS = {  # role -> block type -> allowed keys
    "user": {"text": {"type", "text"}, "image": {"type", "media_type", "data"}},
    "assistant": {"text": {"type", "text"}, "tool_call": {"type", "id", "name", "arguments"}},
    "tool": {"tool_result": {"type", "id", "text", "is_error"}},
}
MEDIA = {"image/png", "image/jpeg", "image/webp", "image/gif"}
EFFORTS = ("low", "medium", "high")
NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")
MAX_STATE = 1_000_000


@dataclass(frozen=True)
class Limits:
    max_messages: int
    max_text: int
    max_tools: int
    max_images: int
    max_image_bytes: int

    @classmethod
    def from_settings(cls, s: Any) -> "Limits":
        return cls(s.max_messages, s.max_text, s.max_tools, s.max_images, s.max_image_mb * 1024 * 1024)


@dataclass(frozen=True)
class ChatRequest:
    gateway: str
    model: str | None
    system: str | None
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    tool_choice: Any
    schema: dict[str, Any] | None
    reasoning: dict[str, Any] | None
    max_tokens: int | None
    temperature: float | None
    cache: bool
    stream: bool

    @property
    def uses(self) -> set[str]:
        used: set[str] = set()
        types = {b["type"] for m in self.messages for b in m["content"]}
        if "image" in types:
            used.add("images")
        if self.tools or types & {"tool_call", "tool_result"}:
            used.add("tools")
        if self.reasoning:
            used.add("reasoning")
        if self.schema:
            used.add("schema")
        return used


@dataclass
class ChatResult:
    content: list[dict[str, Any]]
    stop_reason: str = "end"
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    reasoning: str | None = None
    reasoning_state: str | None = None


def bad(message: str) -> GatewayError:
    return GatewayError(422, "invalid_request", f"Invalid chat request: {message}")


def _text(value: Any, label: str, limit: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not empty):
        raise bad(f"{label} must be text" + ("" if empty else " and not empty") + ".")
    if len(value) > limit:
        raise bad(f"{label} is longer than {limit} characters.")
    return value


def _blocks(role: str, content: Any, limits: Limits, images: list[int]) -> list[dict[str, Any]]:
    if isinstance(content, str) and role != "tool":
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list) or not content:
        raise bad(f"the content of a {role} message must be text or a list of blocks.")
    out = []
    for block in content:
        kind = block.get("type") if isinstance(block, dict) else None
        allowed = BLOCKS[role].get(kind)
        if allowed is None:
            raise bad(f"a {role} message cannot hold a '{kind}' block.")
        if set(block) - allowed:
            raise bad(f"unexpected field in a {kind} block.")
        if kind == "text":
            out.append({"type": "text", "text": _text(block.get("text"), "text", limits.max_text)})
        elif kind == "image":
            if block.get("media_type") not in MEDIA:
                raise bad("an image media_type must be image/png, image/jpeg, image/webp or image/gif.")
            data = _text(block.get("data"), "image data", limits.max_image_bytes * 4 // 3 + 4)
            # shortcut: size is estimated from the base64 length and the base64 is not decoded here; upstream rejects bad data.
            if len(data) * 3 // 4 > limits.max_image_bytes:
                raise bad("an image is larger than the limit.")
            images[0] += 1
            out.append({"type": "image", "media_type": block["media_type"], "data": data})
        elif kind == "tool_call":
            name = block.get("name")
            if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(block.get("arguments"), dict):
                raise bad("a tool_call needs a valid name and an arguments object.")
            out.append({"type": "tool_call", "id": _text(block.get("id"), "tool_call id", 200), "name": name, "arguments": block["arguments"]})
        else:
            is_error = block.get("is_error", False)
            if not isinstance(is_error, bool):
                raise bad("is_error must be true or false.")
            out.append({"type": "tool_result", "id": _text(block.get("id"), "tool_result id", 200),
                        "text": _text(block.get("text", ""), "tool_result text", limits.max_text, empty=True), "is_error": is_error})
    return out


def _tools(value: Any, limits: Limits) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limits.max_tools:
        raise bad(f"tools must be a list of at most {limits.max_tools}.")
    out, seen = [], set()
    for tool in value:
        if not isinstance(tool, dict) or set(tool) - {"name", "description", "parameters"}:
            raise bad("a tool has only name, description and parameters.")
        name = tool.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in seen:
            raise bad("tool names must be unique and match [A-Za-z0-9_.-]{1,64}.")
        seen.add(name)
        parameters = tool.get("parameters", {"type": "object", "properties": {}})
        if not isinstance(parameters, dict):
            raise bad("tool parameters must be a JSON schema object.")
        out.append({"name": name, "description": _text(tool.get("description", ""), "tool description", 4000, empty=True), "parameters": parameters})
    return out


def parse_request(data: Any, limits: Limits) -> ChatRequest:
    if not isinstance(data, dict):
        raise bad("the body must be a JSON object.")
    if set(data) - TOP:
        raise bad(f"unexpected field '{sorted(set(data) - TOP)[0]}'.")
    gateway = data.get("gateway")
    if not isinstance(gateway, str) or not gateway:
        raise bad("gateway is required.")
    raw = data.get("messages")
    if not isinstance(raw, list) or not 1 <= len(raw) <= limits.max_messages:
        raise bad(f"messages must be a list of 1 to {limits.max_messages}.")
    images, messages = [0], []
    for item in raw:
        if not isinstance(item, dict) or set(item) - {"role", "content", "reasoning_state"} or item.get("role") not in BLOCKS:
            raise bad("each message has a role (user, assistant or tool), content and for assistants an optional reasoning_state.")
        message = {"role": item["role"], "content": _blocks(item["role"], item.get("content"), limits, images)}
        if "reasoning_state" in item:
            if item["role"] != "assistant":
                raise bad("reasoning_state belongs on assistant messages.")
            message["reasoning_state"] = _text(item["reasoning_state"], "reasoning_state", MAX_STATE)
        messages.append(message)
    if images[0] > limits.max_images:
        raise bad(f"at most {limits.max_images} images.")
    tools = _tools(data.get("tools"), limits)
    choice = data.get("tool_choice")
    if choice is not None:
        names = {t["name"] for t in tools}
        valid = choice in ("auto", "none", "required") or (isinstance(choice, dict) and set(choice) == {"name"} and choice["name"] in names)
        if not tools or not valid:
            raise bad("tool_choice needs tools and must be auto, none, required or {\"name\": <a tool>}.")
    elif tools:
        choice = "auto"
    schema = data.get("schema")
    if schema is not None:
        if (not isinstance(schema, dict) or set(schema) - {"name", "schema", "strict"} or not isinstance(schema.get("name"), str)
                or not NAME.fullmatch(schema["name"]) or not isinstance(schema.get("schema"), dict)
                or not isinstance(schema.get("strict", False), bool)):
            raise bad("schema is {\"name\", \"schema\", \"strict\"?} with a JSON schema object.")
        if tools:
            raise bad("send either tools or a schema, not both.")
        schema = {"name": schema["name"], "schema": schema["schema"], "strict": schema.get("strict", False)}
    reasoning = data.get("reasoning")
    if reasoning is not None:
        if not isinstance(reasoning, dict) or set(reasoning) - {"effort", "budget_tokens"}:
            raise bad("reasoning is {\"effort\"?, \"budget_tokens\"?}.")
        effort, budget = reasoning.get("effort"), reasoning.get("budget_tokens")
        if effort is not None and effort not in EFFORTS:
            raise bad("reasoning effort must be low, medium or high.")
        if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= 200000):
            raise bad("reasoning budget_tokens must be a whole number from 1 to 200000.")
        reasoning = {"effort": effort or (None if budget else "medium"), "budget_tokens": budget}
    max_tokens, temperature = data.get("max_tokens"), data.get("temperature")
    if max_tokens is not None and (isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 1_000_000):
        raise bad("max_tokens must be a whole number from 1 to 1000000.")
    if temperature is not None and (isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2):
        raise bad("temperature must be a number from 0 to 2.")
    for key in ("cache", "stream"):
        if not isinstance(data.get(key, False), bool):
            raise bad(f"{key} must be true or false.")
    model = data.get("model")
    if model is not None:
        model = _text(model, "model", 200)
    system = data.get("system")
    if system is not None:
        system = _text(system, "system", limits.max_text)
    return ChatRequest(gateway, model, system, messages, tools, choice, schema, reasoning, max_tokens,
                       None if temperature is None else float(temperature), data.get("cache", False), data.get("stream", False))
```

- [ ] **Step 4: Run and commit.** Run: `uv run pytest tests/test_contract.py -q`. Expected: all pass. Fix the code, not the tests, unless a test contradicts the spec.

```bash
git add -A && git commit -m "feat: chat request contract"
```

---

### Task 3: Failure mapping and base gateway

**Files:**
- Create: `src/failure.py`, `src/gateways/base.py`, `src/gateways/__init__.py` (registry filled in later tasks), `tests/test_failure.py`

**Interfaces:**
- Consumes: `GatewayError`, `ChatRequest`, `ChatResult`.
- Produces: `scrub(text, secrets) -> str`, `upstream_error(status, text, retry_after=None, secrets=()) -> GatewayError`, `SECRET_KEYS`, `BaseGateway` (attributes `provider, defaults, forwards_images, id, entry, model, timeout, capabilities, secrets`; methods `can(cap)`, `validate(request)`, `guard()`, `error_from(exc)`, abstract `complete/stream/probe`).

- [ ] **Step 1: Write the failing tests `tests/test_failure.py`.**

```python
import pytest

from src.failure import scrub, upstream_error


def test_scrub_hides_secrets_and_shortens():
    assert scrub("bad key sk-secret here", ["sk-secret"]) == "bad key *** here"
    assert len(scrub("x " * 1000, [])) <= 500


@pytest.mark.parametrize("status,text,expect", [
    (402, "pay up", (402, "quota")),
    (400, "Your credit balance is too low", (402, "quota")),
    (429, "You exceeded your current quota", (402, "quota")),
    (429, "slow down", (429, "rate_limit")),
    (401, "nope", (502, "auth")),
    (403, "nope", (502, "auth")),
    (500, "boom", (502, "unavailable")),
    (529, "overloaded", (502, "unavailable")),
    (400, "bad field", (422, None)),
    (404, "no such model", (422, None)),
    (413, "big", (413, None)),
    (418, "teapot", (502, None)),
])
def test_status_mapping(status, text, expect):
    error = upstream_error(status, text)
    assert (error.status, error.kind) == expect


def test_retry_after_is_copied_and_limited():
    assert upstream_error(429, "x", "7").retry_after == 7
    assert upstream_error(429, "x", "9999").retry_after == 60
    assert upstream_error(429, "x", None).retry_after == 1


def test_message_never_holds_the_secret():
    assert "sk-123" not in upstream_error(401, "key sk-123 rejected", secrets=["sk-123"]).message
```

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_failure.py -q`. Expected: ImportError.

- [ ] **Step 3: Write `src/failure.py`.**

```python
"""Upstream status and text to a GatewayError a caller can act on. Never retries."""
from __future__ import annotations

import math
from typing import Iterable

from src.errors import GatewayError

QUOTA_WORDS = ("credit", "quota", "billing", "insufficient", "balance", "exceeded your current")
SECRET_KEYS = ("api_key", "token", "aws_access_key_id", "aws_secret_access_key")


def scrub(text: str, secrets: Iterable[str], limit: int = 500) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return " ".join(str(text).split())[:limit]


def _wait(value: str | None) -> int:
    try:
        return max(1, min(60, math.ceil(float(value))))
    except (TypeError, ValueError):
        return 1


def upstream_error(status: int, text: str, retry_after: str | None = None, secrets: Iterable[str] = ()) -> GatewayError:
    message = scrub(text, secrets) or "The model service refused the request."
    quota = any(word in text.lower() for word in QUOTA_WORDS)
    if status == 402 or (status in (400, 429) and quota):
        return GatewayError(402, "gateway_quota", message, kind="quota")
    if status in (401, 403):
        return GatewayError(502, "gateway_auth", message, kind="auth")
    if status == 429:
        return GatewayError(429, "gateway_rate_limit", message, kind="rate_limit", retry_after=_wait(retry_after))
    if status == 413:
        return GatewayError(413, "too_large", message)
    if status in (400, 404, 422):
        return GatewayError(422, "gateway_refused", message)
    if status >= 500:
        return GatewayError(502, "gateway_unavailable", message, kind="unavailable")
    return GatewayError(502, "gateway_error", message)
```

- [ ] **Step 4: Write `src/gateways/base.py`.**

```python
"""What every adapter shares: capabilities, the HTTP client, and the safe mapping of failures."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx

from src.contract import ChatRequest, ChatResult
from src.errors import GatewayError
from src.failure import SECRET_KEYS, upstream_error

CAPABILITIES = ("streams", "images", "tools", "reasoning", "schema")


class BaseGateway:
    provider = ""
    defaults = {name: True for name in CAPABILITIES}
    forwards_images = False  # True: the upstream service decides about images, so the gateway does not pre-refuse them

    def __init__(self, gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.id, self.entry = gateway_id, entry
        self.model = str(entry.get("model", ""))
        self.timeout = float(entry.get("timeout_s", 300))
        self.capabilities = {**self.defaults, **{k: bool(v) for k, v in (entry.get("capabilities") or {}).items() if k in self.defaults}}
        self.secrets = [str(entry[k]) for k in SECRET_KEYS if entry.get(k)]
        # shortcut: the client lives as long as the process and is not closed on shutdown.
        self.http = httpx.AsyncClient(transport=transport, follow_redirects=False, timeout=self.timeout)

    def can(self, capability: str) -> bool:
        return self.capabilities[capability]

    def validate(self, request: ChatRequest) -> None:
        """Adapter-specific refusals (raise GatewayError 422). Capabilities are checked by the service."""

    def error_from(self, error: Exception) -> GatewayError:
        status = getattr(error, "status_code", None)
        if status is None:
            if "Timeout" in type(error).__name__:
                return GatewayError(504, "gateway_timeout", "The model service took too long to answer.", kind="unavailable")
            if isinstance(error, (httpx.HTTPError, ConnectionError)) or "Connection" in type(error).__name__:
                return GatewayError(502, "gateway_unreachable", "The model service could not be reached.", kind="unavailable")
            return GatewayError(502, "gateway_bad_reply", "The model service sent an unusable reply.", kind="unavailable")
        headers = getattr(getattr(error, "response", None), "headers", None) or {}
        return upstream_error(status, getattr(error, "message", None) or str(error), headers.get("retry-after"), self.secrets)

    @asynccontextmanager
    async def guard(self) -> AsyncIterator[None]:
        """Turns any failure inside the block into a GatewayError whose text holds no secret."""
        try:
            yield
        except GatewayError:
            raise
        except Exception as error:
            raise self.error_from(error) from None

    async def complete(self, request: ChatRequest) -> ChatResult:
        raise NotImplementedError

    def stream(self, request: ChatRequest) -> AsyncIterator[tuple]:
        raise NotImplementedError

    async def probe(self) -> str:
        raise NotImplementedError


def truncated(name: str = "The model service") -> GatewayError:
    return GatewayError(502, "gateway_bad_reply", f"{name} ended its reply before completion.", kind="unavailable")
```

- [ ] **Step 5: Write `src/gateways/__init__.py`.**

```python
"""Providers. A new provider is one adapter file plus one line in PROVIDERS."""
from __future__ import annotations

from typing import Any

import httpx

from src.gateways.base import BaseGateway

PROVIDERS: dict[str, type[BaseGateway]] = {}  # filled in by tasks 4 to 6


def build_gateway(gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> BaseGateway:
    return PROVIDERS[entry["provider"]](gateway_id, entry, transport)
```

- [ ] **Step 6: Run and commit.** Run: `uv run pytest tests/test_failure.py -q`. Expected: pass.

```bash
git add -A && git commit -m "feat: failure mapping and base gateway"
```

---

### Task 4: Anthropic adapter

**Files:**
- Create: `src/gateways/anthropic.py`, `tests/test_anthropic.py`
- Modify: `src/gateways/__init__.py` (register)

**Interfaces:**
- Consumes: `BaseGateway`, `ChatRequest`, `ChatResult`, `truncated`.
- Produces: `AnthropicGateway` (`provider = "anthropic"`), pure functions `message_params(request, model, default_max) -> dict`, `build_result(body, schema_name) -> ChatResult`.
- Entry fields: `auth` (`key` default, `bedrock`, `vertex`), `api_key`, `base_url`, `aws_region`, `aws_access_key_id`, `aws_secret_access_key`, `project_id`, `region`, `model`, `default_max_tokens` (default 4096).

- [ ] **Step 1: Write the failing tests `tests/test_anthropic.py`.**

```python
import json

import httpx
import pytest

from src.errors import GatewayError
from src.gateways import build_gateway
from tests.helpers import chat

ENTRY = {"provider": "anthropic", "auth": "key", "api_key": "sk-ant-secret", "model": "claude-x", "timeout_s": 5}
MESSAGE = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-x", "stop_sequence": None,
           "content": [{"type": "text", "text": "Hello"}], "stop_reason": "end_turn",
           "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 4, "cache_creation_input_tokens": 2}}


def gateway(handler, entry=ENTRY):
    return build_gateway("claude", entry, httpx.MockTransport(handler))


def capture(reply=MESSAGE):
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), key=request.headers.get("x-api-key"), body=json.loads(request.content))
        return httpx.Response(200, json=reply)

    return seen, handler


def sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


async def test_complete_maps_request_and_reply():
    seen, handler = capture()
    result = await gateway(handler).complete(chat(system="Be brief", max_tokens=100, temperature=0.3))
    assert seen["url"].endswith("/v1/messages") and seen["key"] == "sk-ant-secret"
    assert seen["body"] == {"model": "claude-x", "max_tokens": 100, "temperature": 0.3, "system": "Be brief",
                            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}]}
    assert result.content == [{"type": "text", "text": "Hello"}] and result.stop_reason == "end"
    assert result.usage == {"input_tokens": 16, "output_tokens": 5, "cached_input_tokens": 4, "reasoning_tokens": 0}


async def test_default_max_tokens_and_model_override():
    seen, handler = capture()
    await gateway(handler).complete(chat(model="other"))
    assert seen["body"]["max_tokens"] == 4096 and seen["body"]["model"] == "other"


async def test_images_tools_and_results_are_mapped():
    seen, handler = capture()
    await gateway(handler).complete(chat(
        messages=[
            {"role": "user", "content": [{"type": "text", "text": "x"}, {"type": "image", "media_type": "image/png", "data": "aGk="}]},
            {"role": "assistant", "content": [{"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}}]},
            {"role": "tool", "content": [{"type": "tool_result", "id": "c1", "text": "ok", "is_error": True}]},
        ],
        tools=[{"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}], tool_choice="required"))
    body = seen["body"]
    assert body["messages"][0]["content"][1] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "aGk="}}
    assert body["messages"][1]["content"] == [{"type": "tool_use", "id": "c1", "name": "t", "input": {"a": 1}}]
    assert body["messages"][2] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "ok", "is_error": True}]}
    assert body["tools"] == [{"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    assert body["tool_choice"] == {"type": "any"}


async def test_tool_call_reply_and_stop_reason():
    reply = {**MESSAGE, "stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "c9", "name": "t", "input": {"x": 1}}]}
    _, handler = capture(reply)
    result = await gateway(handler).complete(chat(tools=[{"name": "t"}]))
    assert result.content == [{"type": "tool_call", "id": "c9", "name": "t", "arguments": {"x": 1}}] and result.stop_reason == "tool_call"


async def test_thinking_is_returned_and_state_is_echoed():
    reply = {**MESSAGE, "content": [{"type": "thinking", "thinking": "hmm", "signature": "sig"}, {"type": "text", "text": "A"}]}
    seen, handler = capture(reply)
    g = gateway(handler)
    result = await g.complete(chat(reasoning={"effort": "low"}, temperature=0.5))
    assert seen["body"]["thinking"] == {"type": "enabled", "budget_tokens": 1024} and "temperature" not in seen["body"]
    assert result.reasoning == "hmm" and json.loads(result.reasoning_state) == [{"type": "thinking", "thinking": "hmm", "signature": "sig"}]
    await g.complete(chat(messages=[{"role": "user", "content": "q"}, {"role": "assistant", "content": "A", "reasoning_state": result.reasoning_state},
                                    {"role": "user", "content": "again"}], reasoning={"effort": "low"}))
    assert seen["body"]["messages"][1]["content"][0] == {"type": "thinking", "thinking": "hmm", "signature": "sig"}


async def test_budget_tokens_wins_over_effort():
    seen, handler = capture()
    await gateway(handler).complete(chat(reasoning={"effort": "low", "budget_tokens": 3000}, max_tokens=8000))
    assert seen["body"]["thinking"]["budget_tokens"] == 3000


async def test_schema_uses_a_forced_tool_and_returns_json_text():
    reply = {**MESSAGE, "stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "c", "name": "out", "input": {"a": 1}}]}
    seen, handler = capture(reply)
    result = await gateway(handler).complete(chat(schema={"name": "out", "schema": {"type": "object"}}))
    assert seen["body"]["tool_choice"] == {"type": "tool", "name": "out"}
    assert seen["body"]["tools"][0]["input_schema"] == {"type": "object"}
    assert result.content == [{"type": "text", "text": '{"a": 1}'}] and result.stop_reason == "end"


def test_schema_with_reasoning_is_refused():
    with pytest.raises(GatewayError) as error:
        gateway(lambda r: None).validate(chat(schema={"name": "o", "schema": {}}, reasoning={"effort": "low"}))
    assert error.value.status == 422


async def test_cache_adds_breakpoints():
    seen, handler = capture()
    await gateway(handler).complete(chat(system="S", cache=True, tools=[{"name": "a"}, {"name": "b"}]))
    body = seen["body"]
    assert body["system"] == [{"type": "text", "text": "S", "cache_control": {"type": "ephemeral"}}]
    assert "cache_control" not in body["tools"][0] and body["tools"][1]["cache_control"] == {"type": "ephemeral"}
    assert body["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.parametrize("status,expect", [(429, ("rate_limit", 429)), (401, ("auth", 502)), (529, ("unavailable", 502)), (402, ("quota", 402))])
async def test_errors_are_classified_and_secret_free(status, expect):
    def handler(request):
        return httpx.Response(status, json={"type": "error", "error": {"type": "x", "message": "bad sk-ant-secret"}}, headers={"retry-after": "3"})

    with pytest.raises(GatewayError) as error:
        await gateway(handler).complete(chat())
    assert (error.value.kind, error.value.status) == expect and "sk-ant-secret" not in error.value.message


async def test_stream_text_thinking_and_tool_call():
    events = [
        {"type": "message_start", "message": {**MESSAGE, "content": [], "usage": {"input_tokens": 10, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hm"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Hel"}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "lo"}},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "c1", "name": "t", "input": {}}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "{\"a\":"}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "1}"}},
        {"type": "content_block_stop", "index": 2},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 9}},
        {"type": "message_stop"},
    ]
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=sse(events), headers={"content-type": "text/event-stream"})

    items = [i async for i in gateway(handler).stream(chat(stream=True, reasoning={"effort": "low"}, tools=[{"name": "t"}]))]
    assert seen["body"]["stream"] is True
    assert [i[:2] for i in items[:4]] == [("reasoning", "hm"), ("text", "Hel"), ("text", "lo"), ("tool_call", "c1")]
    assert [i[3] for i in items if i[0] == "tool_call"] == ["", "{\"a\":", "1}"]
    done = items[-1][1]
    assert items[-1][0] == "done" and done.stop_reason == "tool_call" and done.usage["output_tokens"] == 9
    assert done.content == [{"type": "text", "text": "Hello"}, {"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}}]
    assert done.reasoning == "hm"


async def test_truncated_stream_is_an_error():
    events = [{"type": "message_start", "message": {**MESSAGE, "content": []}},
              {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}]
    with pytest.raises(GatewayError) as error:
        [i async for i in gateway(lambda r: httpx.Response(200, content=sse(events))).stream(chat(stream=True))]
    assert error.value.status == 502 and error.value.kind == "unavailable"


def test_capabilities_and_override():
    assert gateway(lambda r: None).capabilities == {"streams": True, "images": True, "tools": True, "reasoning": True, "schema": True}
    assert gateway(lambda r: None, {**ENTRY, "capabilities": {"images": False}}).can("images") is False
```

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_anthropic.py -q`. Expected: KeyError `anthropic` (not registered).

- [ ] **Step 3: Write `src/gateways/anthropic.py`.**

```python
"""Provider `anthropic`: the Messages API through the official SDK. Auth variants: key (also gateways such as
OpenRouter, LiteLLM, Helicone, Portkey, OmniRoute through base_url), bedrock and vertex."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from anthropic import AsyncAnthropic, AsyncAnthropicBedrock, AsyncAnthropicVertex

from src.contract import ChatRequest, ChatResult
from src.errors import GatewayError
from src.gateways.base import BaseGateway, truncated

BUDGETS = {"low": 1024, "medium": 4096, "high": 16384}
DEFAULT_MAX_TOKENS = 4096
STOP = {"end_turn": "end", "stop_sequence": "end", "pause_turn": "end", "max_tokens": "max_tokens", "tool_use": "tool_call", "refusal": "refusal"}
EPHEMERAL = {"type": "ephemeral"}


def _blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for b in blocks:
        kind = b["type"]
        if kind == "text":
            out.append({"type": "text", "text": b["text"]})
        elif kind == "image":
            out.append({"type": "image", "source": {"type": "base64", "media_type": b["media_type"], "data": b["data"]}})
        elif kind == "tool_call":
            out.append({"type": "tool_use", "id": b["id"], "name": b["name"], "input": b["arguments"]})
        else:
            out.append({"type": "tool_result", "tool_use_id": b["id"], "content": b["text"], "is_error": b["is_error"]})
    return out


def _thinking(state: str) -> list[dict[str, Any]]:
    try:
        blocks = json.loads(state)
    except ValueError:
        blocks = None
    if not isinstance(blocks, list) or not all(isinstance(b, dict) for b in blocks):
        raise GatewayError(422, "invalid_reasoning_state", "reasoning_state is not a value this gateway returned.")
    return blocks


def message_params(request: ChatRequest, model: str, default_max: int) -> dict[str, Any]:
    messages = []
    for m in request.messages:
        content = _blocks(m["content"])
        if m["role"] == "assistant" and m.get("reasoning_state"):
            content = _thinking(m["reasoning_state"]) + content
        messages.append({"role": "assistant" if m["role"] == "assistant" else "user", "content": content})
    params: dict[str, Any] = {"model": request.model or model, "max_tokens": request.max_tokens or default_max, "messages": messages}
    if request.system:
        params["system"] = [{"type": "text", "text": request.system, "cache_control": EPHEMERAL}] if request.cache else request.system
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in request.tools]
    if request.schema:
        tools = [{"name": request.schema["name"], "description": "Reply with this structure.", "input_schema": request.schema["schema"]}]
        params["tool_choice"] = {"type": "tool", "name": request.schema["name"]}
    elif tools:
        choice = request.tool_choice
        params["tool_choice"] = ({"type": "auto"} if choice == "auto" else {"type": "any"} if choice == "required"
                                 else {"type": "none"} if choice == "none" else {"type": "tool", "name": choice["name"]})
    if tools:
        if request.cache:
            tools[-1]["cache_control"] = EPHEMERAL
        params["tools"] = tools
    if request.cache and messages:
        messages[-1]["content"][-1]["cache_control"] = EPHEMERAL
    if request.reasoning:
        budget = request.reasoning["budget_tokens"] or BUDGETS[request.reasoning["effort"]]
        params["thinking"] = {"type": "enabled", "budget_tokens": budget}  # Anthropic allows no temperature here
    elif request.temperature is not None:
        params["temperature"] = request.temperature
    return params


def build_result(body: dict[str, Any], schema_name: str | None = None) -> ChatResult:
    content, thoughts, state = [], [], []
    for b in body.get("content") or []:
        kind = b.get("type")
        if kind == "text":
            content.append({"type": "text", "text": b.get("text") or ""})
        elif kind == "tool_use":
            if schema_name and b.get("name") == schema_name:
                content.append({"type": "text", "text": json.dumps(b.get("input") or {})})
            else:
                content.append({"type": "tool_call", "id": b["id"], "name": b["name"], "arguments": b.get("input") or {}})
        elif kind == "thinking":
            thoughts.append(b.get("thinking") or "")
            state.append({"type": "thinking", "thinking": b.get("thinking") or "", "signature": b.get("signature") or ""})
        elif kind == "redacted_thinking":
            state.append({"type": "redacted_thinking", "data": b.get("data") or ""})
    stop = STOP.get(body.get("stop_reason"), "end")
    if schema_name and stop == "tool_call":
        stop = "end"
    u = body.get("usage") or {}
    cached = u.get("cache_read_input_tokens") or 0
    created = u.get("cache_creation_input_tokens") or 0
    usage = {"input_tokens": (u.get("input_tokens") or 0) + cached + created, "output_tokens": u.get("output_tokens") or 0,
             "cached_input_tokens": cached, "reasoning_tokens": 0}
    return ChatResult(content, stop, usage, str(body.get("model") or ""), "".join(thoughts) or None, json.dumps(state) if state else None)


class AnthropicGateway(BaseGateway):
    provider = "anthropic"

    def __init__(self, gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(gateway_id, entry, transport)
        auth = entry.get("auth", "key")
        options = {"http_client": self.http, "max_retries": 0}
        if auth == "bedrock":
            self.client = AsyncAnthropicBedrock(aws_region=entry["aws_region"], aws_access_key=entry["aws_access_key_id"],
                                                aws_secret_key=entry["aws_secret_access_key"], **options)
        elif auth == "vertex":
            self.client = AsyncAnthropicVertex(project_id=entry["project_id"], region=entry["region"], **options)
        else:
            self.client = AsyncAnthropic(api_key=entry["api_key"], base_url=entry.get("base_url"), **options)
        self.default_max = int(entry.get("default_max_tokens", DEFAULT_MAX_TOKENS))

    def validate(self, request: ChatRequest) -> None:
        if request.schema and request.reasoning:
            raise GatewayError(422, "schema_with_reasoning", "Anthropic cannot force a structured reply while it reasons. Send one of them.")

    def _params(self, request: ChatRequest) -> dict[str, Any]:
        return message_params(request, self.model, self.default_max)

    async def complete(self, request: ChatRequest) -> ChatResult:
        async with self.guard():
            message = await self.client.messages.create(**self._params(request))
            return build_result(message.model_dump(), request.schema and request.schema["name"])

    async def stream(self, request: ChatRequest) -> AsyncIterator[tuple]:
        schema_name = request.schema and request.schema["name"]
        blocks: dict[int, dict[str, Any]] = {}
        usage: dict[str, Any] = {}
        meta: dict[str, Any] = {"model": "", "stop_reason": None}
        finished = False
        async with self.guard():
            stream = await self.client.messages.create(**self._params(request), stream=True)
            async for event in stream:
                kind = event.type
                if kind == "message_start":
                    usage.update(event.message.usage.model_dump())
                    meta["model"] = event.message.model
                elif kind == "content_block_start":
                    block = event.content_block.model_dump()
                    block["_json"] = ""
                    blocks[event.index] = block
                    if block["type"] == "tool_use" and block["name"] != schema_name:
                        yield "tool_call", block["id"], block["name"], ""
                elif kind == "content_block_delta":
                    block, delta = blocks[event.index], event.delta
                    if delta.type == "text_delta":
                        block["text"] = (block.get("text") or "") + delta.text
                        yield "text", delta.text
                    elif delta.type == "thinking_delta":
                        block["thinking"] = (block.get("thinking") or "") + delta.thinking
                        yield "reasoning", delta.thinking
                    elif delta.type == "signature_delta":
                        block["signature"] = delta.signature
                    elif delta.type == "input_json_delta":
                        block["_json"] += delta.partial_json
                        yield (("text", delta.partial_json) if block["name"] == schema_name
                               else ("tool_call", block["id"], block["name"], delta.partial_json))
                elif kind == "message_delta":
                    meta["stop_reason"] = event.delta.stop_reason
                    usage.update({k: v for k, v in event.usage.model_dump().items() if v is not None})
                elif kind == "message_stop":
                    finished = True
            if not finished:
                raise truncated()
        content = []
        for index in sorted(blocks):
            block = dict(blocks[index])
            if block["type"] == "tool_use":
                block["input"] = json.loads(block.pop("_json") or "{}")
            content.append(block)
        yield "done", build_result({"content": content, "stop_reason": meta["stop_reason"], "usage": usage, "model": meta["model"]}, schema_name)

    async def probe(self) -> str:
        async with self.guard():
            if self.entry.get("auth", "key") == "key":
                await self.client.models.list(limit=1)
            else:  # Bedrock and Vertex have no model list: ask for one token
                await self.client.messages.create(model=self.model, max_tokens=1, messages=[{"role": "user", "content": "ping"}])
        return "The provider accepted the credentials."
```

Note `_json` and non-API keys never leave `stream`: the `content` handed to `build_result` has `_json` popped for tool blocks; remove `_json` from text and thinking blocks too (`block.pop("_json", None)`) before building if a test shows them leaking into results.

- [ ] **Step 4: Register.** In `src/gateways/__init__.py` add `from src.gateways.anthropic import AnthropicGateway` and set `PROVIDERS["anthropic"] = AnthropicGateway` (build the dict literal once all three exist; for now `PROVIDERS = {"anthropic": AnthropicGateway}`).

- [ ] **Step 5: Run and commit.** Run: `uv run pytest tests/test_anthropic.py -q`. Expected: all pass. If the SDK rejects a call or parses an event differently, fix the adapter and keep the tests' expectations.

```bash
git add -A && git commit -m "feat: anthropic adapter"
```

---

### Task 5: OpenAI adapter (chat, responses, azure, Gemini)

**Files:**
- Create: `src/gateways/openai.py`, `tests/test_openai.py`
- Modify: `src/gateways/__init__.py`

**Interfaces:**
- Produces: `OpenAIGateway` (`provider = "openai"`), `chat_params(request, model, entry)`, `chat_result(body)`, `responses_params(request, model, entry)`, `responses_result(body)`.
- Entry fields: `auth` (`key` default, `azure`), `api` (`chat` or `responses`; default `chat`), `api_key`, `base_url`, `azure_endpoint`, `api_version`, `model`, `max_tokens_param` (`max_tokens` default, or `max_completion_tokens`), `stream_usage` (default true).

- [ ] **Step 1: Write the failing tests `tests/test_openai.py`.**

```python
import json

import httpx
import pytest

from src.errors import GatewayError
from src.gateways import build_gateway
from tests.helpers import chat

CHAT = {"provider": "openai", "api": "chat", "api_key": "sk-secret", "base_url": "https://compat.test/v1", "model": "m", "timeout_s": 5}
RESPONSES = {"provider": "openai", "api": "responses", "api_key": "sk-secret", "model": "gpt-x", "timeout_s": 5}
COMPLETION = {"id": "c", "object": "chat.completion", "created": 1, "model": "m",
              "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Hello"}}],
              "usage": {"prompt_tokens": 11, "completion_tokens": 6, "total_tokens": 17,
                        "prompt_tokens_details": {"cached_tokens": 3}, "completion_tokens_details": {"reasoning_tokens": 2}}}


def gateway(handler, entry=CHAT):
    return build_gateway("g", entry, httpx.MockTransport(handler))


def capture(reply):
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), auth=request.headers.get("authorization"), body=json.loads(request.content))
        return httpx.Response(200, json=reply)

    return seen, handler


def sse(chunks):
    return ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode()


async def test_chat_request_and_reply():
    seen, handler = capture(COMPLETION)
    result = await gateway(handler).complete(chat(system="Be brief", max_tokens=50, temperature=0.2))
    assert seen["url"] == "https://compat.test/v1/chat/completions" and seen["auth"] == "Bearer sk-secret"
    assert seen["body"] == {"model": "m", "max_tokens": 50, "temperature": 0.2,
                            "messages": [{"role": "system", "content": "Be brief"}, {"role": "user", "content": "Hi"}]}
    assert result.content == [{"type": "text", "text": "Hello"}] and result.stop_reason == "end"
    assert result.usage == {"input_tokens": 11, "output_tokens": 6, "cached_input_tokens": 3, "reasoning_tokens": 2}


async def test_max_completion_tokens_option():
    seen, handler = capture(COMPLETION)
    await gateway(handler, {**CHAT, "max_tokens_param": "max_completion_tokens"}).complete(chat(max_tokens=9))
    assert seen["body"]["max_completion_tokens"] == 9 and "max_tokens" not in seen["body"]


async def test_chat_tools_images_results_schema_reasoning():
    seen, handler = capture(COMPLETION)
    await gateway(handler).complete(chat(
        messages=[
            {"role": "user", "content": [{"type": "text", "text": "x"}, {"type": "image", "media_type": "image/png", "data": "aGk="}]},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}, {"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}}]},
            {"role": "tool", "content": [{"type": "tool_result", "id": "c1", "text": "42"}]},
        ],
        tools=[{"name": "t", "description": "d"}], tool_choice={"name": "t"}, reasoning={"effort": "high"}, temperature=0.4))
    body = seen["body"]
    assert body["messages"][0]["content"] == [{"type": "text", "text": "x"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGk="}}]
    assert body["messages"][1] == {"role": "assistant", "content": "ok",
                                   "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{\"a\": 1}"}}]}
    assert body["messages"][2] == {"role": "tool", "tool_call_id": "c1", "content": "42"}
    assert body["tools"] == [{"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}}]
    assert body["tool_choice"] == {"type": "function", "function": {"name": "t"}}
    assert body["reasoning_effort"] == "high" and "temperature" not in body


async def test_chat_schema_becomes_response_format():
    seen, handler = capture(COMPLETION)
    await gateway(handler).complete(chat(schema={"name": "out", "schema": {"type": "object"}, "strict": True}))
    assert seen["body"]["response_format"] == {"type": "json_schema", "json_schema": {"name": "out", "schema": {"type": "object"}, "strict": True}}


async def test_chat_tool_call_and_reasoning_reply():
    reply = {**COMPLETION, "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "reasoning_content": "thinking...",
        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{\"a\": 1}"}},
                       {"id": "c2", "type": "function", "function": {"name": "t", "arguments": "not json"}}]}}]}
    _, handler = capture(reply)
    result = await gateway(handler).complete(chat(tools=[{"name": "t"}]))
    assert result.content == [{"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}},
                              {"type": "tool_call", "id": "c2", "name": "t", "arguments": {"_raw": "not json"}}]
    assert result.stop_reason == "tool_call" and result.reasoning == "thinking..."


@pytest.mark.parametrize("finish,expect", [("length", "max_tokens"), ("content_filter", "refusal"), ("stop", "end")])
async def test_chat_stop_reasons(finish, expect):
    reply = {**COMPLETION, "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": "x"}}]}
    _, handler = capture(reply)
    assert (await gateway(handler).complete(chat())).stop_reason == expect


async def test_chat_stream_text_reasoning_and_tool_call():
    chunks = [
        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [{"index": 0, "delta": {"role": "assistant", "reasoning_content": "hm"}, "finish_reason": None}]},
        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [{"index": 0, "delta": {"content": "Hel"}, "finish_reason": None}]},
        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [{"index": 0, "delta": {"content": "lo"}, "finish_reason": None}]},
        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {"name": "t", "arguments": "{\"a\":"}}]}, "finish_reason": None}]},
        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": "1}"}}]}, "finish_reason": "tool_calls"}]},
        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}},
    ]
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=sse(chunks), headers={"content-type": "text/event-stream"})

    items = [i async for i in gateway(handler).stream(chat(stream=True, tools=[{"name": "t"}]))]
    assert seen["body"]["stream"] is True and seen["body"]["stream_options"] == {"include_usage": True}
    assert [i[:2] for i in items if i[0] in ("reasoning", "text")] == [("reasoning", "hm"), ("text", "Hel"), ("text", "lo")]
    assert [i[3] for i in items if i[0] == "tool_call"] == ["{\"a\":", "1}"]
    done = items[-1][1]
    assert done.content == [{"type": "text", "text": "Hello"}, {"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}}]
    assert done.stop_reason == "tool_call" and done.usage["output_tokens"] == 7 and done.reasoning == "hm"


async def test_stream_usage_can_be_turned_off():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=sse([]))

    with pytest.raises(GatewayError):
        [i async for i in gateway(handler, {**CHAT, "stream_usage": False}).stream(chat(stream=True))]
    assert "stream_options" not in seen["body"]


async def test_chat_truncated_stream_is_an_error():
    chunk = {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [{"index": 0, "delta": {"content": "x"}, "finish_reason": None}]}
    with pytest.raises(GatewayError) as error:
        [i async for i in gateway(lambda r: httpx.Response(200, content=sse([chunk]))).stream(chat(stream=True))]
    assert error.value.kind == "unavailable"


RESP = {"id": "r", "object": "response", "created_at": 1, "status": "completed", "model": "gpt-x", "parallel_tool_calls": True,
        "tool_choice": "auto", "tools": [], "output": [
            {"id": "rs", "type": "reasoning", "summary": [{"type": "summary_text", "text": "plan"}]},
            {"id": "m", "type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": "Hello", "annotations": []}]},
            {"id": "f", "type": "function_call", "call_id": "c1", "name": "t", "arguments": "{\"a\": 1}", "status": "completed"}],
        "usage": {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13, "input_tokens_details": {"cached_tokens": 2}, "output_tokens_details": {"reasoning_tokens": 1}}}


async def test_responses_request_and_reply():
    seen, handler = capture(RESP)
    result = await gateway(handler, RESPONSES).complete(chat(
        system="S", max_tokens=80, reasoning={"effort": "low"}, tools=[{"name": "t", "description": "d"}],
        messages=[{"role": "user", "content": [{"type": "text", "text": "x"}, {"type": "image", "media_type": "image/png", "data": "aGk="}]},
                  {"role": "assistant", "content": [{"type": "text", "text": "ok"}, {"type": "tool_call", "id": "c0", "name": "t", "arguments": {}}]},
                  {"role": "tool", "content": [{"type": "tool_result", "id": "c0", "text": "42"}]}]))
    body = seen["body"]
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert body["instructions"] == "S" and body["max_output_tokens"] == 80 and body["reasoning"] == {"effort": "low", "summary": "auto"}
    assert body["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "x"}, {"type": "input_image", "image_url": "data:image/png;base64,aGk="}]},
        {"role": "assistant", "content": "ok"},
        {"type": "function_call", "call_id": "c0", "name": "t", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "c0", "output": "42"}]
    assert body["tools"] == [{"type": "function", "name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}]
    assert result.content == [{"type": "text", "text": "Hello"}, {"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}}]
    assert result.reasoning == "plan" and result.stop_reason == "tool_call"
    assert result.usage == {"input_tokens": 9, "output_tokens": 4, "cached_input_tokens": 2, "reasoning_tokens": 1}


async def test_responses_schema_and_incomplete():
    seen, handler = capture({**RESP, "status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []})
    result = await gateway(handler, RESPONSES).complete(chat(schema={"name": "out", "schema": {"type": "object"}}))
    assert seen["body"]["text"] == {"format": {"type": "json_schema", "name": "out", "schema": {"type": "object"}, "strict": False}}
    assert result.stop_reason == "max_tokens"


async def test_responses_stream():
    created = {"type": "response.created", "sequence_number": 0, "response": {**RESP, "status": "in_progress", "output": []}}
    events = [
        created,
        {"type": "response.output_item.added", "sequence_number": 1, "output_index": 0, "item": {"id": "f", "type": "function_call", "call_id": "c1", "name": "t", "arguments": "", "status": "in_progress"}},
        {"type": "response.function_call_arguments.delta", "sequence_number": 2, "item_id": "f", "output_index": 0, "delta": "{\"a\": 1}"},
        {"type": "response.reasoning_summary_text.delta", "sequence_number": 3, "item_id": "rs", "output_index": 0, "summary_index": 0, "delta": "plan"},
        {"type": "response.output_text.delta", "sequence_number": 4, "item_id": "m", "output_index": 1, "content_index": 0, "delta": "Hello"},
        {"type": "response.completed", "sequence_number": 5, "response": RESP},
    ]
    body = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
    items = [i async for i in gateway(lambda r: httpx.Response(200, content=body, headers={"content-type": "text/event-stream"}), RESPONSES).stream(chat(stream=True, tools=[{"name": "t"}]))]
    assert items[0] == ("tool_call", "c1", "t", "") and items[1] == ("tool_call", "c1", "t", "{\"a\": 1}")
    assert ("reasoning", "plan") in items and ("text", "Hello") in items
    assert items[-1][0] == "done" and items[-1][1].stop_reason == "tool_call"


async def test_responses_stream_without_completion_is_an_error():
    body = f"event: response.created\ndata: {json.dumps({'type': 'response.created', 'sequence_number': 0, 'response': {**RESP, 'status': 'in_progress', 'output': []}})}\n\n".encode()
    with pytest.raises(GatewayError):
        [i async for i in gateway(lambda r: httpx.Response(200, content=body), RESPONSES).stream(chat(stream=True))]


async def test_azure_client_is_used():
    seen = {}

    def handler(request):
        seen["url"], seen["key"] = str(request.url), request.headers.get("api-key")
        return httpx.Response(200, json=COMPLETION)

    entry = {"provider": "openai", "auth": "azure", "api": "chat", "azure_endpoint": "https://res.openai.azure.com", "api_version": "2024-10-21", "api_key": "az-secret", "model": "dep", "timeout_s": 5}
    await gateway(handler, entry).complete(chat())
    assert "res.openai.azure.com" in seen["url"] and "api-version=2024-10-21" in seen["url"] and seen["key"] == "az-secret"


@pytest.mark.parametrize("status,kind", [(429, "rate_limit"), (401, "auth"), (503, "unavailable")])
async def test_errors_are_classified_and_secret_free(status, kind):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "bad sk-secret", "type": "x"}}, headers={"retry-after": "2"})

    with pytest.raises(GatewayError) as error:
        await gateway(handler).complete(chat())
    assert error.value.kind == kind and "sk-secret" not in error.value.message


def test_no_key_is_allowed_for_a_local_server():
    g = gateway(lambda r: None, {"provider": "openai", "api": "chat", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen", "timeout_s": 5})
    assert g.provider == "openai"
```

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_openai.py -q`. Expected: KeyError `openai`.

- [ ] **Step 3: Write `src/gateways/openai.py`.**

```python
"""Provider `openai`: OpenAI and every OpenAI-compatible server (Gemini, Groq, Together, Ollama, vLLM, ...) plus Azure.
`api: responses` uses the Responses API (GPT, Azure); `api: chat` uses Chat Completions (all compatible servers)."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from openai import AsyncAzureOpenAI, AsyncOpenAI

from src.contract import ChatRequest, ChatResult
from src.errors import GatewayError
from src.gateways.base import BaseGateway, truncated

FINISH = {"stop": "end", "length": "max_tokens", "tool_calls": "tool_call", "function_call": "tool_call", "content_filter": "refusal"}


def _effort(reasoning: dict[str, Any]) -> str:
    if reasoning["effort"]:
        return reasoning["effort"]
    budget = reasoning["budget_tokens"]
    return "low" if budget <= 2048 else "medium" if budget <= 8192 else "high"


def _args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return {"_raw": str(raw)}
    return value if isinstance(value, dict) else {"_raw": str(raw)}


def _data_url(block: dict[str, Any]) -> str:
    return f"data:{block['media_type']};base64,{block['data']}"


def chat_params(request: ChatRequest, model: str, entry: dict[str, Any]) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": request.system}] if request.system else []
    for m in request.messages:
        blocks = m["content"]
        if m["role"] == "tool":
            messages += [{"role": "tool", "tool_call_id": b["id"], "content": b["text"]} for b in blocks]
        elif m["role"] == "assistant":
            text = "".join(b["text"] for b in blocks if b["type"] == "text")
            out: dict[str, Any] = {"role": "assistant", "content": text or None}
            calls = [{"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b["arguments"])}}
                     for b in blocks if b["type"] == "tool_call"]
            if calls:
                out["tool_calls"] = calls
            messages.append(out)
        else:
            parts = [{"type": "text", "text": b["text"]} if b["type"] == "text"
                     else {"type": "image_url", "image_url": {"url": _data_url(b)}} for b in blocks]
            messages.append({"role": "user", "content": parts[0]["text"] if len(parts) == 1 and parts[0]["type"] == "text" else parts})
    params: dict[str, Any] = {"model": request.model or model, "messages": messages}
    if request.tools:
        params["tools"] = [{"type": "function", "function": t} for t in request.tools]
        choice = request.tool_choice
        params["tool_choice"] = choice if isinstance(choice, str) else {"type": "function", "function": {"name": choice["name"]}}
    if request.schema:
        params["response_format"] = {"type": "json_schema", "json_schema": {
            "name": request.schema["name"], "schema": request.schema["schema"], "strict": request.schema["strict"]}}
    if request.reasoning:
        params["reasoning_effort"] = _effort(request.reasoning)
    elif request.temperature is not None:
        params["temperature"] = request.temperature
    if request.max_tokens:
        params[entry.get("max_tokens_param", "max_tokens")] = request.max_tokens
    return params


def _usage(u: dict[str, Any]) -> dict[str, int]:
    return {"input_tokens": u.get("prompt_tokens") or u.get("input_tokens") or 0,
            "output_tokens": u.get("completion_tokens") or u.get("output_tokens") or 0,
            "cached_input_tokens": ((u.get("prompt_tokens_details") or u.get("input_tokens_details") or {}).get("cached_tokens")) or 0,
            "reasoning_tokens": ((u.get("completion_tokens_details") or u.get("output_tokens_details") or {}).get("reasoning_tokens")) or 0}


def chat_result(body: dict[str, Any]) -> ChatResult:
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = [{"type": "text", "text": message["content"]}] if message.get("content") else []
    for index, call in enumerate(message.get("tool_calls") or []):
        function = call.get("function") or {}
        content.append({"type": "tool_call", "id": call.get("id") or f"call_{index}", "name": function.get("name") or "",
                        "arguments": _args(function.get("arguments"))})
    stop = FINISH.get(choice.get("finish_reason"), "end")
    return ChatResult(content, stop, _usage(body.get("usage") or {}), str(body.get("model") or ""),
                      message.get("reasoning_content") or message.get("reasoning") or None)


def responses_params(request: ChatRequest, model: str, entry: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for m in request.messages:
        blocks = m["content"]
        if m["role"] == "tool":
            items += [{"type": "function_call_output", "call_id": b["id"], "output": b["text"]} for b in blocks]
        elif m["role"] == "assistant":
            text = "".join(b["text"] for b in blocks if b["type"] == "text")
            if text:
                items.append({"role": "assistant", "content": text})
            items += [{"type": "function_call", "call_id": b["id"], "name": b["name"], "arguments": json.dumps(b["arguments"])}
                      for b in blocks if b["type"] == "tool_call"]
        else:
            items.append({"role": "user", "content": [{"type": "input_text", "text": b["text"]} if b["type"] == "text"
                                                       else {"type": "input_image", "image_url": _data_url(b)} for b in blocks]})
    params: dict[str, Any] = {"model": request.model or model, "input": items}
    if request.system:
        params["instructions"] = request.system
    if request.tools:
        params["tools"] = [{"type": "function", **t} for t in request.tools]
        choice = request.tool_choice
        params["tool_choice"] = choice if isinstance(choice, str) else {"type": "function", "name": choice["name"]}
    if request.schema:
        params["text"] = {"format": {"type": "json_schema", "name": request.schema["name"], "schema": request.schema["schema"],
                                     "strict": request.schema["strict"]}}
    if request.reasoning:
        params["reasoning"] = {"effort": _effort(request.reasoning), "summary": "auto"}
    elif request.temperature is not None:
        params["temperature"] = request.temperature
    if request.max_tokens:
        params["max_output_tokens"] = request.max_tokens
    return params


def responses_result(body: dict[str, Any]) -> ChatResult:
    content, thoughts = [], []
    for item in body.get("output") or []:
        kind = item.get("type")
        if kind == "message":
            content += [{"type": "text", "text": part["text"]} for part in item.get("content") or [] if part.get("type") == "output_text"]
        elif kind == "function_call":
            content.append({"type": "tool_call", "id": item.get("call_id") or item.get("id"), "name": item.get("name") or "",
                            "arguments": _args(item.get("arguments"))})
        elif kind == "reasoning":
            thoughts += [s.get("text") or "" for s in item.get("summary") or []]
    reason = (body.get("incomplete_details") or {}).get("reason")
    stop = ("tool_call" if any(b["type"] == "tool_call" for b in content) else
            "max_tokens" if body.get("status") == "incomplete" and reason == "max_output_tokens" else
            "refusal" if body.get("status") == "incomplete" and reason == "content_filter" else "end")
    return ChatResult(content, stop, _usage(body.get("usage") or {}), str(body.get("model") or ""), "\n".join(t for t in thoughts if t) or None)


class OpenAIGateway(BaseGateway):
    provider = "openai"

    def __init__(self, gateway_id: str, entry: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(gateway_id, entry, transport)
        self.api = entry.get("api", "chat")
        options = {"http_client": self.http, "max_retries": 0}
        if entry.get("auth") == "azure":
            self.client = AsyncAzureOpenAI(azure_endpoint=entry["azure_endpoint"], api_version=entry["api_version"],
                                           api_key=entry["api_key"], **options)
        else:  # a local server (Ollama, vLLM) may need no key; the SDK wants a non-empty one
            self.client = AsyncOpenAI(api_key=entry.get("api_key") or "none", base_url=entry.get("base_url"), **options)

    async def complete(self, request: ChatRequest) -> ChatResult:
        async with self.guard():
            if self.api == "responses":
                response = await self.client.responses.create(**responses_params(request, self.model, self.entry))
                return responses_result(response.model_dump())
            completion = await self.client.chat.completions.create(**chat_params(request, self.model, self.entry))
            return chat_result(completion.model_dump())

    def stream(self, request: ChatRequest) -> AsyncIterator[tuple]:
        return self._responses_stream(request) if self.api == "responses" else self._chat_stream(request)

    async def _chat_stream(self, request: ChatRequest) -> AsyncIterator[tuple]:
        params = chat_params(request, self.model, self.entry)
        if self.entry.get("stream_usage", True):
            params["stream_options"] = {"include_usage": True}
        text: list[str] = []
        thoughts: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        usage: dict[str, Any] = {}
        finish = None
        model = ""
        async with self.guard():
            stream = await self.client.chat.completions.create(**params, stream=True)
            async for chunk in stream:
                data = chunk.model_dump()
                model = data.get("model") or model
                usage = data.get("usage") or usage
                for choice in data.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        text.append(delta["content"])
                        yield "text", delta["content"]
                    thought = delta.get("reasoning_content") or delta.get("reasoning")
                    if thought:
                        thoughts.append(thought)
                        yield "reasoning", thought
                    for piece in delta.get("tool_calls") or []:
                        slot = calls.setdefault(piece.get("index") or 0, {"id": "", "name": "", "arguments": ""})
                        function = piece.get("function") or {}
                        slot["id"] = piece.get("id") or slot["id"]
                        slot["name"] = function.get("name") or slot["name"]
                        slot["arguments"] += function.get("arguments") or ""
                        yield "tool_call", slot["id"], slot["name"], function.get("arguments") or ""
                    finish = choice.get("finish_reason") or finish
            if finish is None:
                raise truncated()
        message: dict[str, Any] = {"content": "".join(text) or None, "reasoning_content": "".join(thoughts) or None,
                                   "tool_calls": [{"id": c["id"], "function": {"name": c["name"], "arguments": c["arguments"]}}
                                                  for _, c in sorted(calls.items())]}
        yield "done", chat_result({"choices": [{"message": message, "finish_reason": finish}], "usage": usage, "model": model})

    async def _responses_stream(self, request: ChatRequest) -> AsyncIterator[tuple]:
        params = responses_params(request, self.model, self.entry)
        calls: dict[str, tuple[str, str]] = {}
        final = None
        async with self.guard():
            stream = await self.client.responses.create(**params, stream=True)
            async for event in stream:
                kind = event.type
                if kind == "response.output_text.delta":
                    yield "text", event.delta
                elif kind == "response.reasoning_summary_text.delta":
                    yield "reasoning", event.delta
                elif kind == "response.output_item.added" and event.item.type == "function_call":
                    calls[event.item.id] = (event.item.call_id, event.item.name)
                    yield "tool_call", event.item.call_id, event.item.name, ""
                elif kind == "response.function_call_arguments.delta":
                    call_id, name = calls.get(event.item_id, ("", ""))
                    yield "tool_call", call_id, name, event.delta
                elif kind in ("response.completed", "response.incomplete"):
                    final = event.response.model_dump()
                elif kind in ("response.failed", "error"):
                    raise GatewayError(502, "gateway_unavailable", "The model service stopped answering.", kind="unavailable")
            if final is None:
                raise truncated()
        yield "done", responses_result(final)

    async def probe(self) -> str:
        async with self.guard():
            if self.entry.get("auth") != "azure":
                await self.client.models.list()
            else:  # Azure lists deployments differently: ask for a few tokens
                await self.complete_ping()
        return "The provider accepted the credentials."

    async def complete_ping(self) -> None:
        from src.contract import ChatRequest as Request
        ping = Request(self.id, None, None, [{"role": "user", "content": [{"type": "text", "text": "ping"}]}], [], None, None, None,
                       16, None, False, False)
        await self.complete(ping)
```

- [ ] **Step 4: Register.** In `src/gateways/__init__.py` import `OpenAIGateway` and add `"openai": OpenAIGateway` to `PROVIDERS`.

- [ ] **Step 5: Run and commit.** Run: `uv run pytest tests/test_openai.py tests/test_anthropic.py -q`. Expected: all pass. Fix adapter details (SDK field names, SSE shapes) without weakening the assertions.

```bash
git add -A && git commit -m "feat: openai adapter (chat, responses, azure)"
```

---

### Task 6: Scuti adapter (CNV model services)

**Files:**
- Create: `src/gateways/scuti.py`, `tests/test_scuti.py`
- Modify: `src/gateways/__init__.py`

**Interfaces:**
- Produces: `ScutiGateway` (`provider = "scuti"`, `forwards_images = True`, `defaults = {"streams": True, "images": False, "tools": False, "reasoning": False, "schema": False}`), `chat_body(entry, request, stream)`.
- Wire format (CNV services, verified in their READMEs): `POST {url}/v1/chat`; body `messages` (`system|user|assistant|tool`, string `content`, assistant `tool_calls: [{id, name, arguments}]`, tool `tool_name`), `tools: [{name, description, parameters}]`, `schema`, `thinking` (bool), `temperature`, `max_tokens`, `project`, `stream`. Reply `content`, `thinking`, `tool_calls`, `finish_reason` (`stop|tool_calls|length`), `model`, `usage {input_tokens, output_tokens}`. Stream lines `{"type": "content"|"thinking", "text"}`, `{"type": "done", ...body}`, `{"type": "error", "status", ...}`. Services not supporting a field answer 422. Header `X-Internal-Token`. Health `GET /health` with `ready`.
- Images: forwarded as `images: [<base64>, ...]` on the user message. This is a guess (Ollama style) because no CNV service documents image input; keep it in one place (`_user_message`) so it is easy to change.

- [ ] **Step 1: Write the failing tests `tests/test_scuti.py`.**

```python
import json

import httpx
import pytest

from src.errors import GatewayError
from src.gateways import build_gateway
from tests.helpers import chat

ENTRY = {"provider": "scuti", "url": "http://127.0.0.1:29200", "token": "mini_tok", "model": "minicpm", "timeout_s": 5,
         "capabilities": {"tools": True, "reasoning": True, "schema": True}, "project": "demo"}
PLAIN = {"provider": "scuti", "url": "http://127.0.0.1:29202", "model": "lfm3", "timeout_s": 5}
BODY = {"content": "Hello", "thinking": "hm", "tool_calls": [], "finish_reason": "stop", "model": "minicpm", "fallback": False,
        "usage": {"input_tokens": 12, "output_tokens": 3}, "duration_ms": 5}


def gateway(handler, entry=ENTRY):
    return build_gateway("minicpm", entry, httpx.MockTransport(handler))


def capture(reply=BODY):
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), token=request.headers.get("x-internal-token"), body=json.loads(request.content))
        return httpx.Response(200, json=reply)

    return seen, handler


async def test_request_and_reply():
    seen, handler = capture()
    result = await gateway(handler).complete(chat(system="Be brief", max_tokens=64, temperature=0.1, reasoning={"effort": "low"}))
    assert seen["url"] == "http://127.0.0.1:29200/v1/chat" and seen["token"] == "mini_tok"
    assert seen["body"] == {"messages": [{"role": "system", "content": "Be brief"}, {"role": "user", "content": "Hi"}],
                            "thinking": True, "temperature": 0.1, "max_tokens": 64, "project": "demo"}
    assert result.content == [{"type": "text", "text": "Hello"}] and result.reasoning == "hm" and result.stop_reason == "end"
    assert result.usage == {"input_tokens": 12, "output_tokens": 3, "cached_input_tokens": 0, "reasoning_tokens": 0}


async def test_thinking_is_off_unless_asked_when_the_service_supports_it():
    seen, handler = capture()
    await gateway(handler).complete(chat())
    assert seen["body"]["thinking"] is False


async def test_plain_services_get_no_extra_fields():
    seen, handler = capture()
    await gateway(handler, PLAIN).complete(chat())
    assert seen["body"] == {"messages": [{"role": "user", "content": "Hi"}]} and seen["token"] is None


async def test_tools_results_and_schema():
    reply = {**BODY, "content": "", "finish_reason": "tool_calls", "tool_calls": [{"id": "c9", "name": "t", "arguments": {"x": 1}}]}
    seen, handler = capture(reply)
    result = await gateway(handler).complete(chat(
        tools=[{"name": "t", "description": "d"}],
        messages=[{"role": "user", "content": "q"},
                  {"role": "assistant", "content": [{"type": "text", "text": "ok"}, {"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}}]},
                  {"role": "tool", "content": [{"type": "tool_result", "id": "c1", "text": "42"}]}]))
    body = seen["body"]
    assert body["messages"][1] == {"role": "assistant", "content": "ok", "tool_calls": [{"id": "c1", "name": "t", "arguments": {"a": 1}}]}
    assert body["messages"][2] == {"role": "tool", "tool_name": "t", "content": "42"}
    assert body["tools"] == [{"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}]
    assert result.content == [{"type": "tool_call", "id": "c9", "name": "t", "arguments": {"x": 1}}] and result.stop_reason == "tool_call"
    seen2, handler2 = capture()
    await gateway(handler2).complete(chat(schema={"name": "o", "schema": {"type": "object"}}))
    assert seen2["body"]["schema"] == {"type": "object"}


async def test_images_are_forwarded_and_the_service_decides():
    seen, handler = capture()
    await gateway(handler, PLAIN).complete(chat(messages=[{"role": "user", "content": [
        {"type": "text", "text": "look"}, {"type": "image", "media_type": "image/png", "data": "aGk="}]}]))
    assert seen["body"]["messages"][0] == {"role": "user", "content": "look", "images": ["aGk="]}

    def refuse(request):
        return httpx.Response(422, json={"detail": "images is not supported"})

    with pytest.raises(GatewayError) as error:
        await gateway(refuse, PLAIN).complete(chat())
    assert error.value.status == 422 and "images is not supported" in error.value.message


def test_model_override_is_refused():
    with pytest.raises(GatewayError) as error:
        gateway(lambda r: None).validate(chat(model="other"))
    assert error.value.status == 422 and error.value.code == "model_unsupported"


@pytest.mark.parametrize("status,kind,out", [(429, "rate_limit", 429), (401, "auth", 502), (503, "unavailable", 502)])
async def test_errors(status, kind, out):
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: httpx.Response(status, json={"detail": "secret mini_tok"}, headers={"retry-after": "2"})).complete(chat())
    assert (error.value.kind, error.value.status) == (kind, out) and "mini_tok" not in error.value.message


async def test_unreachable_service():
    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(GatewayError) as error:
        await gateway(down).complete(chat())
    assert error.value.status == 502 and error.value.kind == "unavailable"


async def test_stream_relays_pieces_then_done():
    lines = [{"type": "thinking", "text": "hm"}, {"type": "content", "text": "Hel"}, {"type": "content", "text": "lo"},
             {"type": "done", **{**BODY, "content": "Hello", "tool_calls": [{"id": "c1", "name": "t", "arguments": {"a": 1}}], "finish_reason": "tool_calls"}}]
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content="\n".join(map(json.dumps, lines)).encode(), headers={"content-type": "application/x-ndjson"})

    items = [i async for i in gateway(handler).stream(chat(stream=True, tools=[{"name": "t"}]))]
    assert seen["body"]["stream"] is True
    assert items[:3] == [("reasoning", "hm"), ("text", "Hel"), ("text", "lo")]
    assert items[3] == ("tool_call", "c1", "t", "{\"a\": 1}")
    assert items[-1][0] == "done" and items[-1][1].stop_reason == "tool_call"


async def test_stream_error_line_and_truncation():
    error_line = json.dumps({"type": "error", "status": 502, "message": "secret mini_tok"})
    with pytest.raises(GatewayError) as error:
        [i async for i in gateway(lambda r: httpx.Response(200, content=error_line.encode())).stream(chat(stream=True))]
    assert error.value.status == 502 and "mini_tok" not in error.value.message
    with pytest.raises(GatewayError):
        [i async for i in gateway(lambda r: httpx.Response(200, content=json.dumps({"type": "content", "text": "x"}).encode())).stream(chat(stream=True))]


async def test_probe():
    assert "ready" in (await gateway(lambda r: httpx.Response(200, json={"status": "ok", "ready": True})).probe()).lower()
    with pytest.raises(GatewayError) as error:
        await gateway(lambda r: httpx.Response(200, json={"status": "ok", "ready": False})).probe()
    assert error.value.status == 503


def test_capabilities():
    assert gateway(lambda r: None, PLAIN).capabilities == {"streams": True, "images": False, "tools": False, "reasoning": False, "schema": False}
    assert gateway(lambda r: None).capabilities["tools"] is True and gateway(lambda r: None).forwards_images is True
```

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_scuti.py -q`. Expected: KeyError `scuti`.

- [ ] **Step 3: Write `src/gateways/scuti.py`.**

```python
"""Provider `scuti`: a CNV model service (CNV_MiniCPM52B_Model, CNV_BitNet2B_Model, CNV_LFM3_Model, CNV_SparkX26_Model)
through POST /v1/chat. A service refuses fields it does not support with 422; that refusal goes to the caller."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from src.contract import ChatRequest, ChatResult
from src.errors import GatewayError
from src.failure import scrub, upstream_error
from src.gateways.base import BaseGateway, truncated

NAME = "The model service"
FINISH = {"stop": "end", "tool_calls": "tool_call", "length": "max_tokens"}


def _user_message(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"role": "user", "content": "\n".join(b["text"] for b in blocks if b["type"] == "text")}
    images = [b["data"] for b in blocks if b["type"] == "image"]
    if images:
        out["images"] = images  # a guess (Ollama style): no CNV service documents image input yet
    return out


def chat_body(entry: dict[str, Any], request: ChatRequest, can_think: bool, stream: bool) -> dict[str, Any]:
    names = {b["id"]: b["name"] for m in request.messages for b in m["content"] if b["type"] == "tool_call"}
    messages: list[dict[str, Any]] = [{"role": "system", "content": request.system}] if request.system else []
    for m in request.messages:
        blocks = m["content"]
        if m["role"] == "tool":
            for b in blocks:
                row: dict[str, Any] = {"role": "tool", "content": b["text"]}
                if b["id"] in names:
                    row["tool_name"] = names[b["id"]]
                messages.append(row)
        elif m["role"] == "assistant":
            out: dict[str, Any] = {"role": "assistant", "content": "".join(b["text"] for b in blocks if b["type"] == "text")}
            calls = [{"id": b["id"], "name": b["name"], "arguments": b["arguments"]} for b in blocks if b["type"] == "tool_call"]
            if calls:
                out["tool_calls"] = calls
            messages.append(out)
        else:
            messages.append(_user_message(blocks))
    body: dict[str, Any] = {"messages": messages}
    if request.tools:
        body["tools"] = request.tools
    if request.schema:
        body["schema"] = request.schema["schema"]
    if can_think:
        body["thinking"] = bool(request.reasoning)
    elif request.reasoning:
        body["thinking"] = True  # the caller asked: the service answers 422 if it cannot
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.max_tokens:
        body["max_tokens"] = request.max_tokens
    if entry.get("project"):
        body["project"] = entry["project"]
    if stream:
        body["stream"] = True
    return body


def _result(body: dict[str, Any]) -> ChatResult:
    content = [{"type": "text", "text": body["content"]}] if body.get("content") else []
    for index, call in enumerate(body.get("tool_calls") or []):
        content.append({"type": "tool_call", "id": call.get("id") or f"call_{index}", "name": call.get("name") or "",
                        "arguments": call.get("arguments") or {}})
    u = body.get("usage") or {}
    return ChatResult(content, FINISH.get(body.get("finish_reason"), "end"),
                      {"input_tokens": u.get("input_tokens") or 0, "output_tokens": u.get("output_tokens") or 0,
                       "cached_input_tokens": 0, "reasoning_tokens": 0},
                      str(body.get("model") or ""), body.get("thinking") or None)


class ScutiGateway(BaseGateway):
    provider = "scuti"
    defaults = {"streams": True, "images": False, "tools": False, "reasoning": False, "schema": False}
    forwards_images = True

    def validate(self, request: ChatRequest) -> None:
        if request.model:
            raise GatewayError(422, "model_unsupported", "A model service runs one model; leave model out.")

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self.entry["token"]} if self.entry.get("token") else {}

    def _failure(self, status: int, text: str, headers: httpx.Headers) -> GatewayError:
        try:
            detail = json.loads(text).get("detail", text)
        except (ValueError, AttributeError):
            detail = text
        return upstream_error(status, detail if isinstance(detail, str) else json.dumps(detail), headers.get("retry-after"), self.secrets)

    def _body(self, request: ChatRequest, stream: bool) -> dict[str, Any]:
        return chat_body(self.entry, request, self.can("reasoning"), stream)

    async def complete(self, request: ChatRequest) -> ChatResult:
        async with self.guard():
            reply = await self.http.post(f"{self.entry['url']}/v1/chat", json=self._body(request, False), headers=self._headers())
            if reply.status_code >= 400:
                raise self._failure(reply.status_code, reply.text, reply.headers)
            try:
                body = reply.json()
            except ValueError:
                body = None
            if not isinstance(body, dict):
                raise GatewayError(502, "gateway_bad_reply", f"{NAME} sent an unusable reply.", kind="unavailable")
            return _result(body)

    async def stream(self, request: ChatRequest) -> AsyncIterator[tuple]:
        async with self.guard():
            async with self.http.stream("POST", f"{self.entry['url']}/v1/chat", json=self._body(request, True), headers=self._headers()) as reply:
                if reply.status_code >= 400:
                    raise self._failure(reply.status_code, (await reply.aread()).decode("utf-8", "replace"), reply.headers)
                async for line in reply.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except ValueError:
                        raise GatewayError(502, "gateway_bad_reply", f"{NAME} sent an unusable reply.", kind="unavailable") from None
                    kind = item.get("type") if isinstance(item, dict) else None
                    if kind == "content":
                        yield "text", item.get("text") or ""
                    elif kind == "thinking":
                        yield "reasoning", item.get("text") or ""
                    elif kind == "done":
                        result = _result(item)
                        for block in result.content:
                            if block["type"] == "tool_call":
                                yield "tool_call", block["id"], block["name"], json.dumps(block["arguments"])
                        yield "done", result
                        return
                    elif kind == "error":
                        raise GatewayError(502, "gateway_error", scrub(str(item.get("message") or f"{NAME} stopped answering."), self.secrets), kind="unavailable")
                raise truncated(NAME)

    async def probe(self) -> str:
        async with self.guard():
            reply = await self.http.get(f"{self.entry['url']}/health", timeout=10.0)
            if reply.status_code >= 400:
                raise self._failure(reply.status_code, reply.text, reply.headers)
            if reply.json().get("ready") is False:
                raise GatewayError(503, "gateway_not_ready", f"{NAME} is running but not ready (its model is not loaded).")
        return "The model service is reachable and ready."
```

- [ ] **Step 4: Register.** Import `ScutiGateway` and add `"scuti": ScutiGateway` to `PROVIDERS` in `src/gateways/__init__.py`.

- [ ] **Step 5: Run and commit.** Run: `uv run pytest tests/test_scuti.py tests/test_openai.py tests/test_anthropic.py tests/test_failure.py -q`. Expected: all pass.

```bash
git add -A && git commit -m "feat: scuti adapter for CNV model services"
```

---

### Task 7: Gateway store and presets

**Files:**
- Create: `src/store.py`, `src/presets.py`, `tests/test_store.py`
- Read first: `../DecisionGateway/src/store.py` (same shape: locking, `runtime.load`/`runtime.replace`, `_public`, secrets write-only).

**Interfaces:**
- Produces: `GatewayStore(path)` with `all()`, `public()`, `put(gid, data)`, `delete(gid)`; `PROVIDERS` (provider → variant → fields), `SECRETS`, `FORM` (what the page shows), `PRESETS`.

- [ ] **Step 1: Write the failing tests `tests/test_store.py`.**

```python
import pytest

from src.presets import PRESETS
from src.store import ADDRESS, PROVIDERS, GatewayStore


@pytest.fixture
def store(tmp_path):
    return GatewayStore(tmp_path / "gateways.json")


def test_put_validates_and_hides_secrets(store):
    public = store.put("claude", {"provider": "anthropic", "api_key": "sk-1", "model": "claude-x"})
    assert public["has_api_key"] is True and "api_key" not in public and public["auth"] == "key" and public["timeout_s"] == 300
    assert store.all()["claude"]["api_key"] == "sk-1"
    assert "sk-1" not in str(store.public())


def test_update_keeps_secrets_when_left_out(store):
    store.put("claude", {"provider": "anthropic", "api_key": "sk-1", "model": "a"})
    store.put("claude", {"provider": "anthropic", "model": "b"})
    assert store.all()["claude"]["api_key"] == "sk-1" and store.all()["claude"]["model"] == "b"


def test_other_provider_does_not_inherit_old_values(store):
    store.put("x", {"provider": "anthropic", "api_key": "sk-1", "model": "a"})
    with pytest.raises(ValueError):
        store.put("x", {"provider": "openai", "model": "m", "api": "chat"} | {"auth": "azure"})  # azure fields missing, no old key


@pytest.mark.parametrize("gid,data,part", [
    ("Bad Id", {"provider": "scuti", "url": "http://127.0.0.1:1"}, "id"),
    ("a", "text", "object"),
    ("a", {"provider": "nope"}, "provider"),
    ("a", {"provider": "anthropic", "model": "m"}, "API key"),
    ("a", {"provider": "anthropic", "api_key": "k"}, "model"),
    ("a", {"provider": "anthropic", "auth": "bedrock", "model": "m", "aws_region": "us-east-1"}, "AWS"),
    ("a", {"provider": "anthropic", "api_key": "k", "model": "m", "base_url": "http://u:p@host"}, "address"),
    ("a", {"provider": "openai", "api": "weird", "api_key": "k", "model": "m"}, "api"),
    ("a", {"provider": "openai", "api_key": "k", "model": "m", "max_tokens_param": "x"}, "max_tokens_param"),
    ("a", {"provider": "scuti"}, "address"),
    ("a", {"provider": "scuti", "url": "http://127.0.0.1:1", "timeout_s": 0}, "timeout"),
    ("a", {"provider": "scuti", "url": "http://127.0.0.1:1", "capabilities": {"tools": "yes"}}, "capabilities"),
    ("a", {"provider": "scuti", "url": "http://127.0.0.1:1", "capabilities": {"magic": True}}, "capabilities"),
    ("a", {"provider": "scuti", "url": "http://127.0.0.1:1", "max_tokens_limit": 0}, "max_tokens_limit"),
])
def test_bad_entries(store, gid, data, part):
    with pytest.raises(ValueError) as error:
        store.put(gid, data)
    assert part.lower() in str(error.value).lower()


def test_openai_local_server_needs_no_key_but_a_base_url(store):
    store.put("ollama", {"provider": "openai", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen"})
    with pytest.raises(ValueError):
        store.put("nokey", {"provider": "openai", "model": "m"})


def test_scuti_entry(store):
    public = store.put("minicpm", {"provider": "scuti", "url": "http://127.0.0.1:29200/", "token": "t", "project": "demo",
                                   "capabilities": {"tools": True}, "max_tokens_limit": 8192})
    assert public["url"] == "http://127.0.0.1:29200" and public["has_token"] is True and public["capabilities"] == {"tools": True}


def test_delete(store):
    store.put("a", {"provider": "scuti", "url": "http://127.0.0.1:1"})
    assert store.delete("a") is True and store.delete("a") is False and store.all() == {}


def test_every_preset_is_a_valid_entry_once_the_user_fills_the_gaps(store):
    secrets = {"api_key", "token", "aws_access_key_id", "aws_secret_access_key"}
    for name, entry in PRESETS.items():
        assert not secrets & set(entry), f"{name} holds a secret"
        filled = dict(entry)
        for field, _label, _secret, required in PROVIDERS[entry["provider"]][entry.get("auth", "")]:
            if required and not filled.get(field):
                filled[field] = "http://x.test" if field in ADDRESS else "x"
        filled.setdefault("model", "x")
        filled.setdefault("api_key", "x")  # OpenAI itself needs a key; fields a variant does not use are ignored
        store.put(name, filled)
    assert {"gemini", "claude", "gpt", "minicpm", "bitnet", "lfm3", "sparkx"} <= set(PRESETS)
```

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_store.py -q`. Expected: ImportError.

- [ ] **Step 3: Write `src/presets.py`.** Presets hold no secrets. For each Legion gateway (`Applications/Citadel/apps/legion/gateways/anthropic/*.json`, `openai/*.json`), read the file (JSON of env placeholders such as `{CLAUDE_API_KEY}`; never print env values) and take `label`, a literal `base_url` if the file has one (not a placeholder), and the default `model`. Use these exact entries for the ones this plan defines; fill the Legion-derived ones the same way.

```python
"""Starting points for the gateways page: no secrets. A saved gateway is the preset plus the secrets and any edits."""
from __future__ import annotations

PRESETS: dict[str, dict] = {
    "claude": {"provider": "anthropic", "auth": "key", "label": "Claude", "model": "claude-sonnet-5-5"},
    "bedrock": {"provider": "anthropic", "auth": "bedrock", "label": "AWS Bedrock", "model": "anthropic.claude-sonnet-5-5", "aws_region": "us-east-1"},
    "vertex": {"provider": "anthropic", "auth": "vertex", "label": "Google Vertex AI", "model": "claude-sonnet-5-5", "region": "us-east5"},
    "gpt": {"provider": "openai", "auth": "key", "api": "responses", "label": "GPT", "model": "gpt-6.1-sol"},
    "azure": {"provider": "openai", "auth": "azure", "api": "responses", "label": "Azure OpenAI", "model": ""},
    "gemini": {"provider": "openai", "auth": "key", "api": "chat", "label": "Google Gemini",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash"},
    "ollama": {"provider": "openai", "auth": "key", "api": "chat", "label": "Ollama", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen3.5:4b"},
    "minicpm": {"provider": "scuti", "label": "CNV_MiniCPM52B_Model", "url": "http://127.0.0.1:29200", "model": "minicpm",
                "capabilities": {"tools": True, "reasoning": True, "schema": True}, "max_tokens_limit": 8192},
    "bitnet": {"provider": "scuti", "label": "CNV_BitNet2B_Model", "url": "http://127.0.0.1:29201", "model": "bitnet", "max_tokens_limit": 4096},
    "lfm3": {"provider": "scuti", "label": "CNV_LFM3_Model", "url": "http://127.0.0.1:29202", "model": "lfm3", "max_tokens_limit": 4096},
    "sparkx": {"provider": "scuti", "label": "CNV_SparkX26_Model", "url": "http://127.0.0.1:29203", "model": "sparkx", "max_tokens_limit": 4096},
    # Same shape as claude / gpt with their own base_url, taken from the Legion gateway files:
    # anthropic: helicone, litellm, openrouter, portkey, omniroute.  openai: deepinfra, fireworks, groq, opencode, perplexity, together, vllm.
}
```

Add the Legion-derived entries to the dict where the Legion file gives a literal address; where it gives only a placeholder, leave `base_url` out so the page shows an empty field. Do not invent addresses. `gemini` and `gemini-2.5-flash` are unverified; keep the comment `# unverified: confirm against Google's OpenAI-compatibility docs` next to them. The model names of the CNV presets are labels, not sent upstream.

- [ ] **Step 4: Write `src/store.py`.**

```python
"""Gateways, saved in gateways.json in the state folder. Secrets are write-only: they are read for calls and never
returned. shortcut: secrets are stored in clear text because they must be sent as they are; the file is private to
the data folder. Upgrade to a secret store if the host is shared."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from src import runtime
from src.admin_api import MAX_TOKEN, _valid_url
from src.gateways.base import CAPABILITIES

ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
DEFAULT_TIMEOUT = 300
SECRETS = {"api_key": "has_api_key", "token": "has_token", "aws_access_key_id": "has_aws_access_key_id",
           "aws_secret_access_key": "has_aws_secret_access_key"}

# provider -> variant -> (field, label, secret, required). The page draws these; the store checks them.
PROVIDERS: dict[str, dict[str, list[tuple[str, str, bool, bool]]]] = {
    "anthropic": {
        "key": [("api_key", "API key", True, True), ("base_url", "Base address (gateways such as OpenRouter)", False, False)],
        "bedrock": [("aws_region", "AWS region", False, True), ("aws_access_key_id", "AWS access key id", True, True),
                    ("aws_secret_access_key", "AWS secret access key", True, True)],
        "vertex": [("project_id", "Google project id", False, True), ("region", "Region", False, True)],
    },
    "openai": {
        "key": [("api_key", "API key", True, False), ("base_url", "Base address (empty = OpenAI)", False, False)],
        "azure": [("azure_endpoint", "Azure endpoint", False, True), ("api_version", "API version", False, True), ("api_key", "API key", True, True)],
    },
    "scuti": {"": [("url", "Model service address", False, True), ("token", "Token", True, False), ("project", "Project model", False, False)]},
}
FORM = {"providers": PROVIDERS, "choices": {"api": ["chat", "responses"], "max_tokens_param": ["max_tokens", "max_completion_tokens"]}}
ADDRESS = {"base_url", "azure_endpoint", "url"}


class GatewayStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return self._read()

    def _read(self) -> dict[str, dict[str, Any]]:
        try:
            data = runtime.load(self._path).get("gateways", {})
        except (OSError, ValueError, AttributeError):
            return {}
        return data if isinstance(data, dict) else {}

    def public(self) -> list[dict[str, Any]]:
        return [self._public(gid, entry) for gid, entry in sorted(self.all().items())]

    @staticmethod
    def _public(gid: str, entry: dict[str, Any]) -> dict[str, Any]:
        out = {"id": gid, **{k: v for k, v in entry.items() if k not in SECRETS}}
        for secret, flag in SECRETS.items():
            if any(secret == f[0] for variant in PROVIDERS.get(entry.get("provider", ""), {}).values() for f in variant):
                out[flag] = bool(entry.get(secret))
        return out

    def put(self, gid: Any, data: Any) -> dict[str, Any]:
        """Create or update one gateway. Raises ValueError with a message that is safe to show."""
        if not isinstance(gid, str) or not ID.fullmatch(gid):
            raise ValueError("The id must be 1 to 48 characters: lowercase letters, digits, - and _, starting with a letter or digit.")
        if not isinstance(data, dict):
            raise ValueError("Send an object.")
        provider = data.get("provider")
        if provider not in PROVIDERS:
            raise ValueError("The provider must be anthropic, openai or scuti.")
        with self._lock:
            gateways = self._read()
            old = gateways.get(gid, {}) if gateways.get(gid, {}).get("provider") == provider else {}
            entry = self._clean(provider, data, old)
            gateways[gid] = entry
            runtime.replace(self._path, {"gateways": gateways})
        return self._public(gid, entry)

    @staticmethod
    def _clean(provider: str, data: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
        def pick(key: str) -> Any:
            return data.get(key, old.get(key))

        def text(key: str, label: str, required: bool, limit: int = 300) -> str | None:
            value = pick(key)
            if value is None or value == "":
                if required:
                    raise ValueError(f"{label} is required.")
                return None
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError(f"{label} must be text of at most {limit} characters.")
            return value.strip()

        entry: dict[str, Any] = {"provider": provider}
        variants = PROVIDERS[provider]
        if provider != "scuti":
            auth = pick("auth") or "key"
            if auth not in variants:
                raise ValueError("The auth must be " + " or ".join(variants) + ".")
            entry["auth"] = auth
        else:
            auth = ""
        for field, label, secret, required in variants[auth]:
            if provider == "openai" and field == "api_key" and auth == "key":
                required = False
            value = text(field, label, required, MAX_TOKEN if secret else 300)
            if value is None:
                continue
            if field in ADDRESS:
                value = value.rstrip("/")
                if not _valid_url(value):
                    raise ValueError(f"{label}: the address must look like http://host:port, with no user name, query or fragment.")
            entry[field] = value
        if provider == "openai" and auth == "key" and not entry.get("base_url") and not entry.get("api_key"):
            raise ValueError("A key is required for OpenAI itself; a local server needs a base address instead.")
        if provider == "openai":
            api = pick("api") or "chat"
            if api not in ("chat", "responses"):
                raise ValueError("The api must be chat or responses.")
            entry["api"] = api
            param = pick("max_tokens_param")
            if param is not None:
                if param not in ("max_tokens", "max_completion_tokens"):
                    raise ValueError("The max_tokens_param must be max_tokens or max_completion_tokens.")
                entry["max_tokens_param"] = param
            usage = pick("stream_usage")
            if usage is not None:
                if not isinstance(usage, bool):
                    raise ValueError("stream_usage must be true or false.")
                entry["stream_usage"] = usage
        if (model := text("model", "The model", provider != "scuti", 200)) is not None:
            entry["model"] = model
        if (label := text("label", "The label", False, 80)) is not None:
            entry["label"] = label
        timeout = pick("timeout_s") if pick("timeout_s") is not None else DEFAULT_TIMEOUT
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 1800:
            raise ValueError("The timeout must be a whole number of seconds from 1 to 1800.")
        entry["timeout_s"] = timeout
        for key in ("default_max_tokens", "max_tokens_limit"):
            value = pick(key)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1_000_000:
                    raise ValueError(f"{key} must be a whole number from 1 to 1000000.")
                entry[key] = value
        caps = pick("capabilities")
        if caps is not None:
            if not isinstance(caps, dict) or set(caps) - set(CAPABILITIES) or not all(isinstance(v, bool) for v in caps.values()):
                raise ValueError("The capabilities are true or false for: " + ", ".join(CAPABILITIES) + ".")
            entry["capabilities"] = caps
        return entry

    def delete(self, gid: str) -> bool:
        with self._lock:
            gateways = self._read()
            if gid not in gateways:
                return False
            del gateways[gid]
            runtime.replace(self._path, {"gateways": gateways})
            return True
```

- [ ] **Step 5: Run and commit.** Run: `uv run pytest tests/test_store.py -q`. Expected: pass. If the preset test is awkward, simplify the test (keep the assertions: no secrets in presets, every preset saves).

```bash
git add -A && git commit -m "feat: gateway store and presets"
```

---

### Task 8: Chat service

**Files:**
- Create: `src/service.py`, `tests/test_service.py`
- Read first: `../DecisionGateway/src/service.py` (gateway cache keyed by entry, in-flight counter, `_is_reachable`).

**Interfaces:**
- Consumes: `GatewayStore`, `build_gateway`, `ChatRequest`, `ChatResult`, `Limits`.
- Produces: `ChatService(store, settings, transport=None)` with `chat(request) -> dict`, `stream(request) -> AsyncIterator[dict]`, `check(request)`, `gateways() -> list[dict]`, `test(gateway_id) -> str`.

- [ ] **Step 1: Write the failing tests `tests/test_service.py`.**

```python
import json

import httpx
import pytest

from src.config import Settings
from src.errors import GatewayError
from src.service import ChatService
from src.store import GatewayStore
from tests.helpers import chat

BODY = {"content": "Hello", "thinking": None, "tool_calls": [], "finish_reason": "stop", "model": "lfm3",
        "usage": {"input_tokens": 3, "output_tokens": 2}}


@pytest.fixture
def store(tmp_path):
    s = GatewayStore(tmp_path / "gateways.json")
    s.put("lfm3", {"provider": "scuti", "url": "http://127.0.0.1:29202", "model": "lfm3", "max_tokens_limit": 100})
    s.put("minicpm", {"provider": "scuti", "url": "http://127.0.0.1:29200", "capabilities": {"tools": True}})
    return s


def service(store, handler=lambda r: httpx.Response(200, json=BODY), **settings):
    return ChatService(store, Settings(**settings), httpx.MockTransport(handler))


async def refused(coro, code):
    with pytest.raises(GatewayError) as error:
        await coro
    assert error.value.status in (422, 429) and error.value.code == code


async def test_chat_body(store):
    body = await service(store).chat(chat("lfm3"))
    assert body["gateway"] == "lfm3" and body["provider"] == "scuti" and body["model"] == "lfm3"
    assert body["content"] == [{"type": "text", "text": "Hello"}] and body["stop_reason"] == "end" and body["streamed"] is False
    assert body["usage"] == {"input_tokens": 3, "output_tokens": 2, "cached_input_tokens": 0, "reasoning_tokens": 0}
    assert "reasoning" not in body and "reasoning_state" not in body and body["duration_ms"] >= 0


async def test_unknown_gateway(store):
    await refused(service(store).chat(chat("nope")), "unknown_gateway")


async def test_capability_refusals_never_call_the_gateway(store):
    def boom(request):
        raise AssertionError("called")

    svc = service(store, boom)
    await refused(svc.chat(chat("lfm3", tools=[{"name": "t"}])), "tools_unsupported")
    await refused(svc.chat(chat("lfm3", reasoning={"effort": "low"})), "reasoning_unsupported")
    await refused(svc.chat(chat("lfm3", schema={"name": "o", "schema": {}})), "schema_unsupported")
    await refused(svc.chat(chat("lfm3", model="other")), "model_unsupported")
    await refused(svc.chat(chat("lfm3", max_tokens=101)), "max_tokens_too_large")


async def test_scuti_forwards_images_and_the_service_decides(store):
    def refuse(request):
        return httpx.Response(422, json={"detail": "images is not supported"})

    request = chat("lfm3", messages=[{"role": "user", "content": [{"type": "image", "media_type": "image/png", "data": "aGk="}]}])
    with pytest.raises(GatewayError) as error:
        await service(store, refuse).chat(request)
    assert error.value.status == 422 and "images" in error.value.message


async def test_in_flight_cap(store):
    svc = service(store, max_inflight=1)
    svc._inflight = 1
    with pytest.raises(GatewayError) as error:
        await svc.chat(chat("lfm3"))
    assert error.value.status == 429 and error.value.retry_after == 1
    svc._inflight = 0
    await svc.chat(chat("lfm3"))
    assert svc._inflight == 0


async def test_failure_releases_the_slot(store):
    svc = service(store, lambda r: httpx.Response(503, json={"detail": "x"}))
    with pytest.raises(GatewayError):
        await svc.chat(chat("lfm3"))
    assert svc._inflight == 0


async def test_native_stream(store):
    lines = [{"type": "content", "text": "Hel"}, {"type": "content", "text": "lo"}, {"type": "done", **BODY}]
    svc = service(store, lambda r: httpx.Response(200, content="\n".join(map(json.dumps, lines)).encode()))
    out = [x async for x in svc.stream(chat("lfm3", stream=True))]
    assert [x["delta"] for x in out if x["type"] == "text"] == ["Hel", "lo"]
    assert out[-1]["type"] == "done" and out[-1]["streamed"] is True and out[-1]["content"] == [{"type": "text", "text": "Hello"}]


async def test_emulated_stream_when_the_gateway_cannot_stream(tmp_path):
    s = GatewayStore(tmp_path / "g.json")
    s.put("nostream", {"provider": "scuti", "url": "http://127.0.0.1:1", "capabilities": {"streams": False, "tools": True}})
    reply = {**BODY, "thinking": "hm", "content": "Hi", "finish_reason": "tool_calls", "tool_calls": [{"id": "c1", "name": "t", "arguments": {"a": 1}}]}
    out = [x async for x in service(s, lambda r: httpx.Response(200, json=reply)).stream(chat("nostream", stream=True, tools=[{"name": "t"}]))]
    assert [x["type"] for x in out] == ["reasoning", "text", "tool_call", "done"]
    assert out[2] == {"type": "tool_call", "id": "c1", "name": "t", "arguments_delta": "{\"a\": 1}"}
    assert out[-1]["streamed"] is False and out[-1]["reasoning"] == "hm"


async def test_stream_preflight_errors_raise_before_the_first_line(store):
    with pytest.raises(GatewayError):
        await anext(service(store).stream(chat("nope", stream=True)))


async def test_gateways_list_has_capabilities_and_no_secrets(tmp_path):
    s = GatewayStore(tmp_path / "g.json")
    s.put("claude", {"provider": "anthropic", "api_key": "sk-1", "model": "m"})
    s.put("lfm3", {"provider": "scuti", "url": "http://127.0.0.1:29202"})
    rows = {r["id"]: r for r in await service(s, lambda r: httpx.Response(200, json={"ready": True})).gateways()}
    assert rows["claude"]["images"] is True and rows["claude"]["provider"] == "anthropic" and "reachable" not in rows["claude"]
    assert rows["lfm3"]["tools"] is False and rows["lfm3"]["reachable"] is True
    assert "sk-1" not in json.dumps(rows)


async def test_test_unknown_gateway_is_404(store):
    with pytest.raises(GatewayError) as error:
        await service(store).test("nope")
    assert error.value.status == 404
```

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_service.py -q`. Expected: ImportError.

- [ ] **Step 3: Write `src/service.py`.**

```python
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
```

- [ ] **Step 4: Run and commit.** Run: `uv run pytest -q`. Expected: all pass.

```bash
git add -A && git commit -m "feat: chat service"
```

---

### Task 9: HTTP app, admin gateway routes and page

**Files:**
- Create: `src/gateways_api.py`, `src/app.py`, `web/gateways.html`, `tests/test_app.py`, `tests/test_gateways_api.py`
- Read first: `../DecisionGateway/src/app.py`, `../DecisionGateway/src/gateways_api.py`, `../DecisionGateway/web/gateways.html`, `../DecisionGateway/tests/test_app.py`, `../DecisionGateway/tests/test_gateways_api.py`. Copy each and apply the changes below.

**Interfaces:**
- Produces: `build_app(settings, config=None, transport=None) -> Starlette`; routes `POST /api/chat`, `GET /api/gateways`, `POST /api/validate`, `GET /health`; admin `GET /admin/gateways` (returns `{"gateways", "form", "presets"}`), `PUT|DELETE /admin/gateways/{id}`, `POST /admin/gateways/{id}/test`, `GET|PUT /admin/settings`.

- [ ] **Step 1: Write the failing tests `tests/test_app.py`.**

```python
import json

import httpx
import pytest
from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings
from src.store import GatewayStore
from tests.seed import seed_token

TOKEN = {"X-Internal-Token": "tok"}
BODY = {"content": "Hello", "thinking": None, "tool_calls": [], "finish_reason": "stop", "model": "lfm3", "usage": {"input_tokens": 3, "output_tokens": 2}}


def upstream(request):
    if str(request.url).endswith("/health"):
        return httpx.Response(200, json={"ready": True})
    if json.loads(request.content).get("stream"):
        lines = [{"type": "content", "text": "Hel"}, {"type": "content", "text": "lo"}, {"type": "done", **BODY, "content": "Hello"}]
        return httpx.Response(200, content="\n".join(map(json.dumps, lines)).encode())
    return httpx.Response(200, json=BODY)


@pytest.fixture
def settings(tmp_path):
    GatewayStore(tmp_path / "gateways.json").put("lfm3", {"provider": "scuti", "url": "http://127.0.0.1:29202", "token": "secret-tok"})
    return seed_token(Settings(data_dir=tmp_path, admin_password="pw"))


@pytest.fixture
def client(settings):
    return TestClient(build_app(settings, transport=httpx.MockTransport(upstream)))


def post(client, headers=TOKEN, **extra):
    return client.post("/api/chat", headers=headers, json={"gateway": "lfm3", "messages": [{"role": "user", "content": "Hi"}], **extra})


def test_health_needs_no_token(client):
    assert client.get("/health").json() == {"ok": True, "ready": True}


def test_api_needs_a_token(client):
    assert post(client, headers={}).status_code == 401
    assert client.get("/api/gateways").status_code == 401


def test_chat_json(client):
    reply = post(client)
    assert reply.status_code == 200 and reply.json()["content"] == [{"type": "text", "text": "Hello"}]


def test_chat_stream_is_ndjson(client):
    reply = post(client, stream=True)
    lines = [json.loads(line) for line in reply.text.splitlines()]
    assert reply.headers["content-type"].startswith("application/x-ndjson")
    assert [x["type"] for x in lines] == ["text", "text", "done"] and lines[-1]["streamed"] is True


def test_errors_use_the_error_body(client):
    reply = post(client, gateway="nope")
    assert reply.status_code == 422 and reply.json()["error"]["code"] == "unknown_gateway"
    assert client.post("/api/chat", headers=TOKEN, content=b"not json").json()["error"]["code"] == "invalid_request"
    assert post(client, tools=[{"name": "t"}]).json()["error"]["code"] == "tools_unsupported"


def test_upstream_rate_limit_keeps_retry_after(settings):
    app = build_app(settings, transport=httpx.MockTransport(lambda r: httpx.Response(429, json={"detail": "slow"}, headers={"retry-after": "4"})))
    reply = post(TestClient(app))
    assert reply.status_code == 429 and reply.headers["retry-after"] == "4" and reply.json()["error"]["kind"] == "rate_limit"


def test_too_large_body(client):
    reply = client.post("/api/chat", headers={**TOKEN, "content-length": str(65 * 1024 * 1024)}, content=b"{}")
    assert reply.status_code == 413


def test_stream_error_after_start_is_a_line(settings):
    def broken(request):
        return httpx.Response(200, content=json.dumps({"type": "content", "text": "x"}).encode())

    reply = post(TestClient(build_app(settings, transport=httpx.MockTransport(broken))), stream=True)
    lines = [json.loads(line) for line in reply.text.splitlines()]
    assert lines[0]["type"] == "text" and lines[-1]["type"] == "error" and lines[-1]["error"]["kind"] == "unavailable"


def test_gateways_list_has_no_secrets(client):
    reply = client.get("/api/gateways", headers=TOKEN)
    assert reply.status_code == 200 and "secret-tok" not in reply.text
    row = reply.json()["gateways"][0]
    assert row["id"] == "lfm3" and row["has_token"] is True and row["reachable"] is True and row["images"] is False


def test_validate(client):
    ok = client.post("/api/validate", headers=TOKEN, json={"gateway": "lfm3", "messages": [{"role": "user", "content": "Hi"}]})
    assert ok.json() == {"ok": True}
    bad = client.post("/api/validate", headers=TOKEN, json={"gateway": "lfm3", "messages": []})
    assert bad.status_code == 422
    cap = client.post("/api/validate", headers=TOKEN, json={"gateway": "lfm3", "messages": [{"role": "user", "content": "Hi"}], "tools": [{"name": "t"}]})
    assert cap.json()["error"]["code"] == "tools_unsupported"
```

`tests/test_gateways_api.py`: copy DecisionGateway's, and change its payloads to the new entries (`{"provider": "scuti", "url": ..., "token": ...}`, `{"provider": "anthropic", "api_key": ..., "model": ...}`). It must still assert: wrong admin password gives 401; `PUT` returns the public entry without secrets; `GET /admin/gateways` returns `gateways`, `form` (`providers` and `choices`) and `presets` (with `gemini`); `DELETE` of an unknown id is 404; `POST .../test` reports `{"ok": true, "message": ...}` for a Scuti gateway with a ready `/health` and `{"ok": false, "detail": ...}` otherwise; saving a gateway changes what `/api/gateways` returns on the next call (no stale cache).

- [ ] **Step 2: Run to verify failure.** Run: `uv run pytest tests/test_app.py tests/test_gateways_api.py -q`. Expected: ImportError.

- [ ] **Step 3: Write `src/gateways_api.py`.** Copy DecisionGateway's. Change the imports to `from src.service import ChatService` and `from src.store import FORM, GatewayStore`; the `register` signature to `service: ChatService`; the `gateways` route to:

```python
        return JSONResponse({"gateways": await service.gateways(), "form": FORM, "presets": PRESETS})
```

(add `from src.presets import PRESETS`). Delete the DecisionGateway-only `FORM` constant. Leave the `PUT`, `DELETE` and `test` routes as they are.

- [ ] **Step 4: Write `src/app.py`.** Copy DecisionGateway's and apply:

```python
INSTRUCTIONS = "ConversationGateway has no MCP tools. Use POST /api/chat."
MAX_BODY = 64 * 1024 * 1024
```

`CONNECT = {"host": "conversationgateway", "port": 29407, "paths": [{"label": "Chat", "method": "POST", "path": "/api/chat"}, {"label": "Gateways", "method": "GET", "path": "/api/gateways"}, {"label": "Validate a request", "method": "POST", "path": "/api/validate"}, {"label": "Gateways admin page", "method": "GET", "path": "/admin/gateways.html"}, {"label": "Health, no token", "method": "GET", "path": "/health"}]}`.

Replace names: `DecisionService`→`ChatService`, `FastMCP(name="conversationgateway", ...)`, `TokenStore(..., "cg_")`, `register(... service="ConversationGateway" ...)`, the too-large messages say 64 MiB, the JSON error text says `Invalid chat request: the body must be JSON.`. Replace `_error` and the stream error line so every error uses `GatewayError.body()`:

```python
def _error(error: GatewayError) -> JSONResponse:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
    return JSONResponse(error.body(), status_code=error.status, headers=headers)
```

```python
            except GatewayError as error:
                yield (json.dumps({"type": "error", "status": error.status, **error.body()}) + "\n").encode()
```

Replace the routes `/api/decide` and `/api/validate` with:

```python
    def limits() -> Limits:
        return Limits.from_settings(settings)

    @mcp.custom_route("/api/chat", methods=["POST"])
    async def chat(request: Request) -> Response:
        owner = request.headers.get("x-requester-username", "").strip() or "unknown"
        try:
            parsed = parse_request(await body_of(request), limits())
            async with usage.track(owner, "chat"):
                if not parsed.stream:
                    return JSONResponse(await service.chat(parsed))
                items = service.stream(parsed)
                first = await anext(items)  # a pre-flight failure raises here, before the response starts
        except GatewayError as error:
            return _error(error)
        return StreamingResponse(lines(items, first), media_type="application/x-ndjson")

    @mcp.custom_route("/api/validate", methods=["POST"])
    async def validate(request: Request) -> Response:
        try:
            await service.check(parse_request(await body_of(request), limits()))
        except GatewayError as error:
            return _error(error)
        return JSONResponse({"ok": True})
```

Import `Limits, parse_request` from `src.contract`. The `status()` helper lists `f"{r['id']} ({r['provider']})"`. Keep `/health`, `/api/gateways`, the admin registration, `/admin/settings`, the static mount and the middleware as in DecisionGateway.

Note on `usage.track`: its `with` block closes when the non-stream branch returns; for streams it closes after `anext`. This matches DecisionGateway; keep it.

- [ ] **Step 5: Write `web/gateways.html`.** Copy DecisionGateway's and change:
  - Title and intro: `Gateways · ConversationGateway`; text: each gateway is one chat model the service can use: an Anthropic, OpenAI-compatible (including Gemini) or Scuti model service. Callers name a gateway by its id.
  - Table columns: Id, Provider, Model or address, Streams, Images, Tools, Reasoning, Schema, Reachable, actions. Reachable shows `-` when the field is absent.
  - Form: a **Start from** select filled from `data.presets` (choosing one fills id, provider, variant and fields); a **Provider** select (`anthropic`, `openai`, `scuti`); a **Variant** select shown for `anthropic` and `openai` (`auth`); the fields of that variant from `data.form.providers[provider][variant]` (secret fields are password inputs with the `saved (leave empty to keep)` placeholder); for `openai` an **API** select (`chat`, `responses`) and an optional **Token limit parameter** select; common inputs: Model, Label, Timeout (seconds, default 300), Default max tokens, Max tokens limit, and five **capability** selects (`default`, `yes`, `no`) for streams, images, tools, reasoning, schema. A `default` capability is left out of the request.
  - `submit` builds the body from visible inputs only (numbers via `Number`, empty skipped); the `Content-Type`, password header, `call`, `say`, `edit`, `test` and `remove` helpers stay as they are.
  Keep the existing markup rules: labels bound to inputs, `role="status"` area, focus styles, light and dark colors, no horizontal page scroll at 375 px (table in `.wrap`).

- [ ] **Step 6: Run and commit.** Run: `uv run pytest -q` and `uv run python tools/check_sync.py`. Expected: all pass; check_sync exits 0.

```bash
git add -A && git commit -m "feat: HTTP app, gateway admin routes and page"
```

---

### Task 10: Project files, Docker, launchers, tests of the project

**Files:**
- Create from DecisionGateway with renames: `Dockerfile`, `docker-compose.yml`, `.env.example`, `run.bat`, `shell.bat`, `VERSION`, `.github/workflows/test.yml`, `tools/make_zip.py`, `tools/publish_live.py`, `tools/deploy.local.example.ini`, `AGENTS.md`, `CLAUDE.md`, `tests/test_project_files.py`, `tests/test_documentation.py`
- Read first: each file in `../DecisionGateway`.

**Interfaces:** none new.

- [ ] **Step 1: Copy and rename.** In each copied file replace `DecisionGateway`→`ConversationGateway`, `decisiongateway`→`conversationgateway`, `29406`→`29407`, `dg_`→`cg_`, `/api/decide`→`/api/chat`. In `docker-compose.yml` the header comments name Anthropic, OpenAI, Gemini and CNV model services; the network stays `citadel`, the volume `conversationgateway_data`. `.env.example` keeps exactly the five lines of DecisionGateway's (`SERVICE_HOST=127.0.0.1`, `SERVICE_PORT=29407`, `SERVICE_BIND=0.0.0.0`, `SERVICE_ADMIN_PASSWORD=` with their comments) and nothing else: the limits are admin settings. Copy `docs/purpose.md` handling in Task 12.

- [ ] **Step 2: Write `AGENTS.md`.** Same sections as DecisionGateway's with: first paragraph `HTTP service on port 29407 for chat through gateways of provider anthropic, openai (including gemini) and scuti. Holds no model and runs no tools: tool calls go back to the caller. FastMCP supplies an empty shell with no MCP tools; callers use /api/chat, /api/gateways and /api/validate. Environment prefix SERVICE_; caller token prefix cg_.` Rules: keep DecisionGateway's, replacing the gateway-file line with `Gateway entries live in Settings.state_dir / "gateways.json", edited through /admin/gateways.html.`; add `Adapters live in src/gateways/ (one file per provider); request mapping stays in pure functions (message_params, chat_params, responses_params, chat_body) so tests need no network.`; the commit-author rule names the email and the name from `git -C ../Bard config user.name` and does not require a Co-Authored-By line. `CLAUDE.md` is `@AGENTS.md`.

- [ ] **Step 3: Adapt the project tests.** `tests/test_project_files.py` and `tests/test_documentation.py` are DecisionGateway's with names, port and token prefix replaced; they must still pass after Task 12. Expect `test_documentation.py` to fail until Task 12 writes the docs; mark that failure as expected in the commit message and fix it in Task 12.

- [ ] **Step 4: Run and commit.** Run: `uv run pytest -q --deselect tests/test_documentation.py`. Expected: pass.

```bash
git add -A && git commit -m "feat: Docker, launchers and project files"
```

---

### Task 11: Parity edits in the sibling services and shared docs (Claude does this one)

Not for Codex. Done from `AI/ToolServices` after Tasks 1 to 10 are merged.

- [ ] Add `"ConversationGateway"` to `SIBLINGS` in `tools/check_sync.py` of all eight services (Bard, Scribe, Converse, Reader, Lens, Mimic, DecisionGateway, ConversationGateway), keeping the file byte-identical across them; run `python tools/check_sync.py` in each: exit 0. Commit in each repo.
- [ ] Add ConversationGateway rows to `AI/ToolServices/_docs/{GUIDES,HARDWARE,PURPOSES,SHARED-FEATURES,SERVICE-SPECIFIC}.md` (port 29407; group Conversation; the own gateways page and the `/api/chat` routes listed as deviations); next free port becomes 29408.
- [ ] Add ConversationGateway to `.agents/skills/tool-service-parity/audit.py`, `service-docs/docs_audit.py`, `service-groups/purpose_audit.py` and `tool-service-parity/SKILL.md`; run the three audits. The only expected finding is the missing GitHub `origin`.

---

### Task 12: Documentation and final review

**Files:**
- Create: `README.md`, `deployment.md`, `CHANGELOG.md`, `docs/purpose.md`, `docs/guide-cli.md`, `docs/guide-web-ui.md`, `docs/guide-docker-same-device.md`, `docs/guide-docker-deployment-device.md`, `docs/guide-no-docker-same-device.md`
- Read first: the same files in `../DecisionGateway`; the `service-docs` and `service-groups` skills.

- [ ] **Step 1: Write the docs** from DecisionGateway's, replacing its contract text with this service's: the request and response of `POST /api/chat`, streaming lines, capabilities per gateway, the CNV image-field caveat, the error `kind` table, the limits, the provider and variant table with the preset gateways, the privacy statement (nothing stored). `docs/purpose.md`: **Kind:** chat messages → text or tool calls (conversation gateway); **Group:** Conversation; tags from the fixed vocabulary in `service-groups` (use `streaming`, `tool-calls`, `json-schema`, `thinking`, plus the vocabulary's tag for a gateway to external providers; add none that is not in the vocabulary); Input, Output, Runs on (no model; CPU API; needs the providers' keys or CNV services); **Use for:** one chat contract for Anthropic, OpenAI-compatible, Gemini and Scuti models; **Not for:** running tools, sessions, failover or model tiers.
- [ ] **Step 2: List the unverified parts** in `README.md` under a heading `Not verified`: live calls to every provider; Gemini OpenAI-compatible tools and reasoning; the CNV image field; the Docker build.
- [ ] **Step 3: Full check.**

Run: `uv run pytest -q` and `uv run python tools/check_sync.py`
Expected: all tests pass; check_sync exits 0.

- [ ] **Step 4: Read the whole diff** against the spec, section by section, and list any spec requirement with no code or test. Fix gaps with a test first.
- [ ] **Step 5: Commit.**

```bash
git add -A && git commit -m "docs: README, deployment and guides"
```

Report: commit list, test count, anything not verified, and any SDK call you had to change.
