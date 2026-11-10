# ConversationGateway design

Date: 2026-11-10. Status: draft for review.

## Goal

A tool service that gives callers one fixed HTTP contract for chat models: messages, tool calls, reasoning, images, structured output, streaming. Callers name a saved gateway; the service translates to Anthropic, OpenAI-compatible (including Google Gemini) or Scuti model services (group CNV). It is the chat counterpart of DecisionGateway and a model backend for Citadel Legion, without Legion's harness.

## Non-goals

- No tool execution, no MCP client, no tool-calling loop. Tool calls go back to the caller, who runs them and sends results in the next request (pass-through).
- No transcripts, sessions or memory. Stateless.
- No failover between gateways, no model tiers (`light`/`standard`/`heavy`). Both stay in Legion.
- No response cache.
- No agents, delegation, cancellation channel or context breakdown.

## Service

- Location `AI/ToolServices/ConversationGateway`, own git repo, branch `main`.
- Port **29407**. Environment prefix `SERVICE_`. Caller token prefix `cg_`.
- Same skeleton as DecisionGateway: Starlette plus an empty `FastMCP` shell, shared admin files byte-identical to Bard, an own `web/gateways.html` page and `/admin/gateways` routes, gateway entries in `gateways.json` in the state folder, `api_key` and `token` write-only.
- Docker pattern, launchers, `tools/check_sync.py` and docs follow `tool-service-parity`, `service-layout`, `service-docs`, `service-groups`. Group: Conversation.
- Official SDKs `anthropic` and `openai` are used for those providers (Bedrock, Vertex and Azure variants come with them). Scuti uses async `httpx`. Tests inject `httpx.MockTransport` through the SDK `http_client`.

## Routes

| Route | Purpose |
|---|---|
| `POST /api/chat` | Chat. JSON reply, or NDJSON when `stream: true`. |
| `GET /api/gateways` | Saved gateways with capabilities. No secrets. |
| `POST /api/validate` | Validate a request body without calling a model. |
| `GET /health` | Unauthenticated. |

Public routes sit under `/api/` so the shared token middleware guards them unchanged.

## Gateways

An entry has `id`, `provider`, `label`, `model` and provider fields. The caller sends `gateway: "<id>"`. Providers:

| Provider | Variants | Fields | Preset gateways |
|---|---|---|---|
| `anthropic` | `auth: key` | `api_key`, `base_url` | claude, helicone, litellm, openrouter, portkey, omniroute |
| | `auth: bedrock` | `aws_region`, `aws_access_key_id`, `aws_secret_access_key` | bedrock |
| | `auth: vertex` | `project_id`, `region` | vertex |
| `openai` | `auth: key` | `api_key`, `base_url`, `api: responses \| chat` | gpt (responses), deepinfra, fireworks, groq, ollama, opencode, perplexity, together, vllm, **gemini** (chat) |
| | `auth: azure` | `azure_endpoint`, `api_version`, `api_key` | azure |
| `scuti` | none | `url`, `token` | minicpm, bitnet, lfm3, sparkx |

- Presets are templates in the gateway page dropdown, with no secrets. Callers only ever see saved ids.
- `gemini` is an `openai` entry with `api: chat` and the Google OpenAI-compatible `base_url`.
- Model names are not hardcoded; each entry holds `model`, and a request may override it.
- Scuti presets: MiniCPM52B 29200, BitNet2B 29201, LFM3 29202, SparkX26 29203.

### Capabilities

Each entry has `streams`, `images`, `tools`, `reasoning`, `schema`, set by adapter defaults and editable per entry.

- A request using a capability the gateway lacks gets 422 and the gateway is not called. Never a silent drop.
- Exception, `scuti`: images are forwarded and the model service decides. Its 422 passes to the caller unchanged. No CNV service documents image input today, so the wire field for images is unverified.
- Scuti defaults: MiniCPM52B `tools`, `reasoning`, `schema`; BitNet2B, LFM3 and SparkX26 none of them. `streams` true for all CNV services.
- A request with `stream: true` to a gateway without `streams` is emulated; the final line says `"streamed": false`.

## Request, `POST /api/chat`

```json
{
  "gateway": "claude",
  "model": "optional override",
  "system": "optional string",
  "messages": [
    {"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image", "media_type": "image/png", "data": "<base64>"}]},
    {"role": "assistant", "content": [{"type": "tool_call", "id": "c1", "name": "get_time", "arguments": {}}], "reasoning_state": "opaque"},
    {"role": "tool", "content": [{"type": "tool_result", "id": "c1", "text": "12:00", "is_error": false}]}
  ],
  "tools": [{"name": "get_time", "description": "...", "parameters": {"type": "object", "properties": {}}}],
  "tool_choice": "auto",
  "schema": {"name": "x", "schema": {}},
  "reasoning": {"effort": "medium", "budget_tokens": 2048},
  "max_tokens": 1024,
  "temperature": 0.2,
  "cache": true,
  "stream": false
}
```

- `content` may be a string, shorthand for one text block.
- Roles `user`, `assistant`, `tool`. The system prompt goes only in `system`.
- `tool_choice`: `auto`, `none`, `required`, or `{"name": "..."}`. Default `auto` when `tools` is set.
- `tools` and `schema` are mutually exclusive (the common ground with MiniCPM).
- `reasoning.effort` (`low`, `medium`, `high`) maps to OpenAI `reasoning_effort` or an Anthropic thinking budget. `budget_tokens` wins where the provider takes it. Absent means provider default.
- `cache: true` adds Anthropic `cache_control`; ignored by other providers. `usage.cached_input_tokens` reports what the provider served from cache.
- `reasoning_state` is an opaque string the gateway returns on assistant output (Anthropic thinking blocks with signatures). The caller echoes it on that assistant message in the next request so tool use with thinking keeps working.
- Unknown fields give 422.

## Response

```json
{
  "gateway": "claude", "provider": "anthropic", "model": "...",
  "content": [{"type": "text", "text": "..."}, {"type": "tool_call", "id": "c1", "name": "...", "arguments": {}}],
  "reasoning": "thinking or summary text when returned",
  "reasoning_state": "opaque or absent",
  "stop_reason": "end",
  "usage": {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "reasoning_tokens": 0},
  "duration_ms": 0,
  "streamed": false
}
```

`stop_reason` is one of `end`, `max_tokens`, `tool_call`, `refusal`, `error`; adapters map `end_turn`/`stop`, `length`, `tool_use`/`tool_calls`. Content blocks keep provider order.

## Streaming

`stream: true` returns NDJSON lines: `{"type":"text","delta":"..."}`, `{"type":"reasoning","delta":"..."}`, `{"type":"tool_call","id","name","arguments_delta"}`, then `{"type":"done", ...full response body...}`. An error before the first line is an HTTP error; after it, a `{"type":"error",...}` line. A truncated upstream stream ends in an error line, never a `done`. Anthropic and OpenAI stream natively through the SDKs; Scuti through its `/v1/chat` NDJSON; the rest emulated.

## Errors

Body `{"error": {"code", "message", "kind"}}`. `kind` follows Legion's failure kinds:

| kind | When |
|---|---|
| `rate_limit` | upstream 429; copies `Retry-After` |
| `quota` | upstream 402, or 400/429 with credit or quota wording |
| `auth` | upstream 401 or 403 |
| `unavailable` | 5xx, transport failure, malformed stream |

Own statuses: 422 bad body or capability mismatch, 401/403 shared middleware, 429 in-flight cap with `Retry-After`, 502 other upstream error, 504 upstream timeout. The gateway never retries and never fails over. Secrets are scrubbed from every message.

## Limits (admin settings, defaults)

Messages at most 500; text per block at most 400,000 characters; tools at most 128; images at most 20, each at most 16 MiB; body at most 64 MiB; `max_tokens` capped by a per-gateway ceiling; in-flight cap 16; upstream timeout 300 s.

## Privacy and logs

Nothing stored. Logs carry gateway id, model, status, token counts and duration only, never prompts, replies or tool arguments.

## Testing

`httpx.MockTransport` only; no network, no keys. Cover: request and response mapping per adapter and variant, tool-call round trip, `reasoning_state` echo, native and emulated streaming, truncated stream, capability refusals, Scuti image pass-through of upstream 422, error classification, secret scrubbing, limits, gateway admin routes, shared-file parity (`tools/check_sync.py` exit 0).

## Docs and parity

README, `deployment.md`, `docs/` guides, `docs/purpose.md` (group Conversation), `.env.example`, `AGENTS.md`, `CHANGELOG.md`. Add ConversationGateway to `tools/check_sync.py` of all eight tool services, the `AI/ToolServices/_docs/` tables (GUIDES, HARDWARE, PURPOSES, SHARED-FEATURES, SERVICE-SPECIFIC), and the audit scripts under `.agents/skills/`. Next free tool port after this: 29408. The own gateways page is listed as a deviation in SERVICE-SPECIFIC, as for DecisionGateway.

## Unverified at design time

Live calls to every provider; Gemini OpenAI-compatible behavior for tools and reasoning; the image wire field for CNV services; Docker build.
