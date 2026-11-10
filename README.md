# ConversationGateway

One HTTP contract for chat models on port **29407**: Anthropic, OpenAI-compatible providers (including Gemini), and Scuti CNV model services. Callers name a saved gateway. No model runs here; the FastMCP shell has no tools. Tool calls return to the caller for execution.

## API

When an admin password is set, `/api/*` requires a caller token in `X-Internal-Token`. Optional `X-Requester-Username` labels aggregate usage; default `unknown`.

| Method and route | Request | Response |
|---|---|---|
| `POST /api/chat` | Chat body below | Full JSON response or NDJSON |
| `GET /api/gateways` | None | `{gateways: [...]}` with public fields and capabilities |
| `POST /api/validate` | Same chat body | `{ok: true}` or error; no provider call |
| `GET /health` | No token | `{ok: true, ready: boolean}`; ready means a saved gateway exists |

```json
{
  "gateway": "claude",
  "system": "Be brief.",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 1024,
  "stream": false
}
```

| Field | Rule |
|---|---|
| `gateway` | Required saved id |
| `model` | Optional override for Anthropic/OpenAI; Scuti runs one model and refuses overrides |
| `system` | Optional nonempty string; system messages are not allowed in `messages` |
| `messages` | 1–500 messages by default; roles `user`, `assistant`, `tool` |
| `tools` | Up to 128 definitions `{name, description?, parameters?}`; parameters default to an empty object schema |
| `tool_choice` | `auto`, `none`, `required`, or `{name: "tool"}`; requires tools; default `auto` |
| `schema` | `{name, schema, strict?}`; strict defaults false; mutually exclusive with tools |
| `reasoning` | `{effort?: "low" or "medium" or "high", budget_tokens?: integer}`; empty object means medium |
| `max_tokens` | Positive integer, at most 1000000 and the gateway's configured ceiling |
| `temperature` | Number 0–2; Anthropic/OpenAI omit it when reasoning is enabled |
| `cache` | Boolean; Anthropic prompt-cache breakpoints, ignored by other adapters; no response cache |
| `stream` | Boolean; default false |

Unknown fields return 422. Text per block defaults to 400000 characters. A string `content` means one text block. Otherwise use these blocks:

| Role | Blocks |
|---|---|
| user | `{type: "text", text}` or `{type: "image", media_type, data}` |
| assistant | Text or `{type: "tool_call", id, name, arguments: {}}`; optional message `reasoning_state` |
| tool | `{type: "tool_result", id, text, is_error?: false}` |

Images use base64 without a data URL prefix; media types PNG, JPEG, WebP or GIF. Defaults: 20 images, 16 MiB per image, 64 MiB total HTTP body. Scuti forwards images using an **unverified** user-message `images` field and lets the model service return 422. No CNV service currently documents that field.

The caller executes returned tools and sends matching ids in tool-result messages on the next request. Echo Anthropic's opaque `reasoning_state` on the corresponding assistant message so signed thinking survives a tool round trip. Anthropic maps schema output through a forced tool; schema plus reasoning returns 422. Anthropic requires a budget of at least 1024 below max_tokens; omitted max_tokens grows to fit thinking unless the gateway ceiling prevents it. Explicit thinking budget wins over effort for Anthropic; OpenAI uses effort or estimates it from a budget. Scuti maps reasoning to a boolean and rejects non-auto tool_choice because CNV has no matching wire field.

```json
{
  "gateway": "claude", "provider": "anthropic", "model": "claude-sonnet-5-5",
  "content": [{"type": "text", "text": "Hello"}],
  "stop_reason": "end",
  "usage": {"input_tokens": 10, "output_tokens": 2, "cached_input_tokens": 0, "reasoning_tokens": 0},
  "duration_ms": 15, "streamed": false
}
```

Responses may include `reasoning` and `reasoning_state`. Stop reasons are `end`, `max_tokens`, `tool_call`, `refusal`, `error`. Content preserves the order available in the provider response. Usage counts Anthropic input including cache reads and writes; cached input is the read count.

**Streaming.** Content type is `application/x-ndjson`. Native Anthropic/OpenAI SSE and Scuti NDJSON become lines:

```jsonl
{"type":"reasoning","delta":"Let me think"}
{"type":"text","delta":"Hello"}
{"type":"tool_call","id":"c1","name":"get_time","arguments_delta":"{}"}
{"type":"done","gateway":"claude","provider":"anthropic","model":"m","content":[],"stop_reason":"end","usage":{"input_tokens":0,"output_tokens":0,"cached_input_tokens":0,"reasoning_tokens":0},"duration_ms":0,"streamed":true}
```

The done line contains the full response, including accumulated content. Gateways with `streams: false` emit equivalent lines after completion and set `streamed: false`. Errors before the first line return HTTP errors. Later errors end with `{type: "error", status, error: {code, message, kind?}}`. A truncated stream produces an error, never done.

### Gateways

Save gateway entries on `/admin/gateways.html`. Secrets are write-only; public entries expose `has_api_key`, `has_token` and AWS credential presence flags. Omitting a secret on an edit preserves it. Saved entries are private runtime state; protect the data volume because provider credentials must be stored in recoverable form.

| Provider / variant | Fields | Presets |
|---|---|---|
| anthropic / key | API key; optional base URL; model | claude, helicone, litellm, openrouter, portkey, omniroute |
| anthropic / bedrock | AWS region, access key id, secret access key; model | bedrock |
| anthropic / vertex | Google project id, region; model; host Google credentials | vertex |
| openai / key | API key or custom base URL; model; `api: chat` or `responses` | gpt (responses), gemini, deepinfra, fireworks, groq, ollama, opencode, perplexity, together, vllm |
| openai / azure | Azure endpoint, API version, API key, deployment model; API selection | azure (responses) |
| scuti | Model-service URL; optional token and project | minicpm 29200, bitnet 29201, lfm3 29202, sparkx 29203 |

Presets are templates; placeholder addresses and deployment names must be filled by the operator. Literal external addresses come from Legion templates; Gemini uses the plan's unverified Google compatibility URL. CNV model labels are not sent upstream. URLs must have no credentials, query or fragment. Common options: label, timeout 1–1800 seconds (default 300), default max tokens, max tokens limit and capability overrides. Default output limits apply to every provider; configured ceilings also apply when a request omits max_tokens. Anthropic defaults to 4096 output tokens.

Capabilities `streams`, `images`, `tools`, `reasoning`, `schema` default true for Anthropic/OpenAI. Scuti defaults only streams true; MiniCPM's preset enables tools, reasoning and schema. Other CNV presets leave them false. Capability mismatches return 422 without calling the model; Scuti images are the explicit pass-through exception. Listing probes only Scuti health, with a 3-second limit and 15-second reachability cache. Paid providers are not probed by listing; **Test** checks credentials and may incur a small request for Bedrock, Vertex or Azure. Gateway edits take effect on the next call. Active requests retain their original adapter until completion; clients and upstream streams close on replacement, disconnect or shutdown.

### Errors and limits

Chat errors are `{error: {code, message, kind?}}`. Shared token middleware and admin routes keep their existing `detail` errors. No retries or failover occur.

| kind | Meaning | HTTP status |
|---|---|---|
| rate_limit | Upstream 429 without quota wording; bounded Retry-After | 429 |
| quota | Upstream 402 or 400/429 with quota, credit or billing wording | 402 |
| auth | Upstream 401/403 | 502 |
| unavailable | Transport failure, 5xx, malformed or truncated reply | 502; timeout 504 |

Own errors: 422 invalid body, unknown gateway or capability mismatch; 413 oversized body; 429 in-flight cap with Retry-After 1. Upstream 400/404/422 become 422. Provider secrets are scrubbed from error messages. Caller token rate limits are independent of the default 16 chats in flight.

## Setup

1. Install dependencies with `uv sync`. On Windows set `UV_CACHE_DIR=D:/User/.uv-cache` and `UV_LINK_MODE=copy` before every uv command.
2. Copy `.env.example` to `.env` locally and set `SERVICE_ADMIN_PASSWORD`.
3. Start `run.bat run` or follow a [deployment guide](deployment.md).
4. Sign in at `/admin/` and create a caller token under Access tokens.
5. Open `/admin/gateways.html`, load gateways, choose a preset, fill required fields, save and Test the connection.

## Admin page

Shared navigation provides Overview, Playground, Access tokens, Model connections, Runtime & settings, Usage and Connect & API. No fixed model slots or service-specific Playground operations are registered. Manage gateways on the separate page linked from Connect & API; [web UI guide](docs/guide-web-ui.md).

## Settings and environment

Only startup bind, port and admin-password values belong in `.env.example`; see [Docker settings](docs/guide-docker-same-device.md#settings). Request limits and Data folder belong on Runtime & settings. Defaults and allowed ranges are in the [web UI guide](docs/guide-web-ui.md#runtime-settings). Saved settings override environment defaults. Without an admin password, token checks and admin routes are disabled and startup only permits a loopback bind.

## Limits worth knowing

Health readiness means a gateway is saved, not that inference works. Gateway credentials/settings and hashed caller tokens are persisted; prompts, replies, tool arguments, transcripts, sessions and response caches are never stored. Usage keeps aggregate counters in memory. Diagnostic logs must contain only gateway id, model, status, token counts and duration; no content logging is added.

## Tests

```bash
uv run pytest -q
uv run python tools/check_sync.py
```

Tests use `httpx.MockTransport` only. SDK traffic uses an async httpx2-to-httpx bridge because the installed SDKs require httpx2. No real provider keys or network calls are used by tests.

## Try it from the admin page

After saving a gateway and creating a caller token, use the HTTP API. Replace placeholders locally:

```bash
curl -N -X POST http://127.0.0.1:29407/api/chat -H "X-Internal-Token: <SERVICE_TOKEN>" -H "Content-Type: application/json" -d '{"gateway":"claude","messages":[{"role":"user","content":"Hello"}],"stream":true}'
```

For a runnable asynchronous client and tool round trip, see [CLI examples](docs/guide-cli.md).

## Connect

Containers on `citadel_core` use `http://conversationgateway:29407`; native callers use `http://127.0.0.1:29407`. A container reaching a model on its host uses `host.docker.internal`. Gateway addresses must be reachable from this service's runtime.

## Not verified

- Live calls to every provider, including Bedrock, Vertex and Azure credentials.
- Gemini OpenAI-compatible tools and reasoning.
- CNV image field (`images` on user messages).
- Docker image build and remote deployment.

Task 11 sibling parity registrations and shared documentation remain the user's work.

## Documentation

- [Purpose](docs/purpose.md)
- [Deployment](deployment.md)
- [Changelog](CHANGELOG.md)
- [Admin web UI](docs/guide-web-ui.md)
- [CLI examples](docs/guide-cli.md)
- [Docker on this PC](docs/guide-docker-same-device.md)
- [Docker on another machine](docs/guide-docker-deployment-device.md)
- [Run without Docker](docs/guide-no-docker-same-device.md)
- [Design](docs/superpowers/specs/2026-11-10-conversation-gateway-design.md)
- [Implementation plan](docs/superpowers/plans/2026-11-10-conversation-gateway.md)