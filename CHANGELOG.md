# Changelog

## Unreleased

### Copy works on plain http and inside a frame

The Copy buttons for a new token and for the addresses now fall back to a hidden text box when the browser refuses the clipboard API (plain http pages, framed pages such as ServiceHub). It is the same fallback the model services already had.

### Playground works behind a path-prefix proxy

The Try it panel built its request URLs from the page origin, so behind ServiceHub (`/s/<id>/`) it called the hub's root and got 404 Not Found. It now resolves routes against the service root (`../` from the admin page). Same-origin checking is unchanged.


- Enforce output ceilings on omitted limits, validate reasoning budgets and malformed field types, bound chunked bodies and preserve stream failure kinds.
- Accumulate thinking signatures; normalize refusals; close upstream streams and retired clients, retaining active requests through edits.
- Reject unsupported Scuti tool-choice modes instead of dropping them.

- One normalized chat contract for Anthropic, OpenAI Chat Completions/Responses, Azure and Scuti CNV services, including Gemini-compatible presets.
- Pass-through tools, signed reasoning state, images, structured output and native/emulated streaming.
- Saved gateways with write-only secrets, provider variants, capabilities, token ceilings and connectivity checks.
- Shared admin page, caller tokens, request limits and in-flight concurrency cap on port 29407.
- Async httpx2-to-httpx SDK transport bridge; Anthropic temperature sent through extra_body and x-api-key set explicitly for installed SDK compatibility.
- Docker/Windows launchers and operator guides. Live providers, Gemini tools/reasoning, CNV image field and Docker build remain unverified.

## 1.0.0 - 2026-11-10

- Initial ConversationGateway service.