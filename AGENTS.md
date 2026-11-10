# ConversationGateway

HTTP chat gateway on port 29407. SERVICE_ environment prefix; cg_ caller tokens.

## Commands

Use uv; Windows UV_CACHE_DIR=D:/User/.uv-cache and UV_LINK_MODE=copy. Test: uv run pytest -q.

## Rules

- Follow implementation plan Tasks 1–10 and 12. Skip Task 11.
- Shared files remain byte-identical to Bard; stop if copied tests fail.
- No secret-file reads, real network tests, pushes, remotes or publish_live.py execution.

<!-- Task 2: Normalized messages, images, tools, schema and reasoning with request limits and unknown-field rejection. -->

<!-- Task 3: Upstream failures carry safe error kinds and bounded Retry-After; no retries. -->

<!-- Task 4: Anthropic Messages: tools, signed thinking state, schema via forced tool, cache breakpoints and native SSE. -->

<!-- Task 5: OpenAI Chat Completions, Responses and Azure; compatible servers including Gemini; native SSE and tool mapping. -->

<!-- Task 6: CNV chat and NDJSON, tools and thinking; images forwarded using unverified images field. Scuti refuses model overrides. -->

<!-- Task 7: Saved gateways validate provider variants, preserve omitted secrets, expose presence flags, and offer provider presets. -->

<!-- Task 8: Chat service checks capabilities and token ceilings, caps concurrency, shapes replies and emulates streaming. -->

<!-- Task 9: Authenticated chat, gateway listing and validation routes; own preset/variant gateway admin page; 64 MiB request bodies. -->
