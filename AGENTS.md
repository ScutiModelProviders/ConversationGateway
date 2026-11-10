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
