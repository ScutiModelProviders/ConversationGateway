# ConversationGateway

HTTP chat gateway on port 29407. SERVICE_ environment prefix; cg_ caller tokens.

## Commands

Use uv; Windows UV_CACHE_DIR=D:/User/.uv-cache and UV_LINK_MODE=copy. Test: uv run pytest -q.

## Rules

- Follow implementation plan Tasks 1–10 and 12. Skip Task 11.
- Shared files remain byte-identical to Bard; stop if copied tests fail.
- No secret-file reads, real network tests, pushes, remotes or publish_live.py execution.
