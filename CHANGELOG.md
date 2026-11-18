# Changelog

## Unreleased

### Links to each provider's model list

The Gateways page shows a link to the provider's list of model names under the Model field, and a Models button on each saved gateway whose id is a preset (Claude, GPT, OpenRouter, Groq and the others). Scuti services and OmniRoute have no link.

### Presets grouped by provider

The Start from list on the Gateways page groups the presets under Anthropic, OpenAI and compatible, and Scuti model services.

### Neutral dark theme

The admin page's dark theme uses the neutral dark palette with the orange accent again, in place of the blue-navy one from the tabbed redesign. The light theme is unchanged.

### Gateways tab matches the other tabs

The Gateways editor now uses the admin page's colors, type, tables, buttons and form card, and follows the Theme toggle.

### Gateways in the sidebar

The sidebar item that was called Model connections is now Gateways and shows the gateway list and editor, including the light, standard, heavy and extreme models, inside the admin page. `/admin/gateways.html` still works on its own. The admin page and `tools/check_sync.py` now stay in step with DecisionGateway only, not with the tool services.

### Service workspace

Admin now opens to a full-width Overview with live readiness, request activity by requester, service details and caller tokens. Use the tabs below the service name for Playground, settings, connections and access management.

### The gateway owns the model names per tier

A saved gateway can keep a model name for each tier (light, standard, heavy, extreme) on the Gateways page. A caller sends `"tier": "light"` instead of a model id and gets that model; a tier with no name uses the gateway's own model. `model` still overrides, and a request cannot send both. Legion uses this so it no longer keeps model names for Azure and vLLM.

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