# Admin page

Shared admin files copied byte-identical from Bard. Limits: 500 messages, 400000 characters per text block, 128 tools, 20 images, 16 MiB per image, 16 chats in flight.

<!-- Task 2: Normalized messages, images, tools, schema and reasoning with request limits and unknown-field rejection. -->

<!-- Task 3: Upstream failures carry safe error kinds and bounded Retry-After; no retries. -->

<!-- Task 4: Anthropic Messages: tools, signed thinking state, schema via forced tool, cache breakpoints and native SSE. -->

<!-- Task 5: OpenAI Chat Completions, Responses and Azure; compatible servers including Gemini; native SSE and tool mapping. -->

<!-- Task 6: CNV chat and NDJSON, tools and thinking; images forwarded using unverified images field. Scuti refuses model overrides. -->

<!-- Task 7: Saved gateways validate provider variants, preserve omitted secrets, expose presence flags, and offer provider presets. -->

<!-- Task 8: Chat service checks capabilities and token ceilings, caps concurrency, shapes replies and emulates streaming. -->

<!-- Task 9: Authenticated chat, gateway listing and validation routes; own preset/variant gateway admin page; 64 MiB request bodies. -->

Docker and Windows launchers use port 29407. Docker build remains unverified.
