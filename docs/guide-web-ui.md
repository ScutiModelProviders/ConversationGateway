# ConversationGateway: admin web UI

Set SERVICE_ADMIN_PASSWORD and open `http://127.0.0.1:29407/admin/`. Sign in with the admin password. Admin requests use X-Admin-Password; public requests use caller tokens.

## Navigation

Open pages using the tabs below the service name. Overview shows live readiness and request counts since restart. Use **Gateways** to list, add, test and change gateways without leaving the admin page.

| Page | Behavior |
|---|---|
| Overview | Saved gateways and readiness; readiness means a gateway exists |
| Playground | No registered chat operation; use the HTTP examples |
| Access tokens | Create, expire, rate-limit and revoke cg_ caller tokens; new tokens shown once, stored hashed |
| Gateways | The gateway list and editor, including the light, standard, heavy and extreme model of each gateway |
| Runtime & settings | Live limits, defaults and restart-applied Data folder |
| Usage | Aggregate calls, errors and time per requester; reset on restart |
| Connections | Addresses, routes and gateway-page link |

## Gateways

The Models link of an `omniroute` gateway opens OmniRoute's own dashboard (port 20128) in a new tab, because it has no public model list: on the host of the saved address, or on the host you opened this page from when the address is `host.docker.internal` or `localhost`.

The list icon on a gateway row asks the provider for its model names with the saved key and shows them in a filterable list; click a name to copy it. Gateways without a model list (Scuti, Bedrock, Vertex, Azure) have no such button.

Under the Model field, a link opens the provider's page of model names in a new tab. Each saved gateway named like a preset also has a Models button for the same page.

Open `/admin/gateways.html`, enter the password and Load gateways. Start from selects a preset and fills id, provider, variant, fields and capabilities. Provider is anthropic, openai or scuti; Variant selects key/bedrock/vertex or key/azure. Fill empty addresses and deployment/model names locally; addresses are never inferred from environment placeholders.

Choose OpenAI API chat or responses and optionally its token-limit parameter. Common options are model, label, timeout (default 300 seconds), default max tokens and max tokens limit. Capability controls default/yes/no override streams, images, tools, reasoning and schema; default uses adapter defaults. The table shows capabilities and Scuti reachability; paid providers show a dash for reachability.

Save creates or updates the id. Edit loads public fields; saved secrets display a hint. Leaving a secret empty retains it. Test explicitly probes the provider and can cost a request for cloud variants; Delete asks for confirmation. Provider keys and model-service tokens differ from public caller tokens. Secrets remain in password inputs and private saved state; responses return only presence flags.

MiniCPM's preset enables tools, reasoning and schema. Other CNV presets enable streaming only. Images pass through to Scuti using an unverified field; the model service may refuse them. Scuti only accepts automatic tool choice; other values return 422. Output ceilings include omitted max_tokens and reasoning budgets. See [provider details](../README.md#gateways).

## Runtime settings

GET/PUT `/admin/settings` requires the admin password. Saved options override environment defaults.

| Setting | Default | Range |
|---|---|---|
| Messages | 500 | 1–5000 |
| Text block characters | 400000 | 1–5000000 |
| Tools | 128 | 1–1024 |
| Images | 20 | 1–200 |
| Image size MiB | 16 | 1–64 |
| Chats at once | 16 | 1–256; excess 429 with Retry-After |

Data folder applies after restart; settings, gateways and tokens remain in the original state folder and existing files are not moved. No transcripts or results are saved. Usage counts one chat per request, closing its stream measurement after the first item as in DecisionGateway; later stream failures do not update that completed usage entry. X-Requester-Username labels aggregate usage and defaults to unknown.

## Try it: this service's request

Save and Test a gateway, create a caller token, then use [CLI examples](guide-cli.md). `/mcp` has no tools. HTTP routes are `/api/chat`, `/api/gateways` and `/api/validate`. Containers on citadel_core use `http://conversationgateway:29407`.

## Problems

401 on public routes needs a caller token; 401 on admin routes needs the admin password. Empty lists need a saved gateway. A failed Test needs reachable addresses, provider credentials and model readiness. See [deployment problems](guide-docker-same-device.md#problems).