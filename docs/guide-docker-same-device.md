# ConversationGateway: Docker on this PC

Run one service on port 29407. Docker image build has not been run and remains unverified.

## Requirements

- Docker with Compose v2 and the external `citadel_core` network, created by the Citadel stack.
- At least one reachable upstream: Anthropic, OpenAI-compatible (including Gemini), or a Scuti CNV model service.
- Upstream credentials where required, entered only on the gateways page.

## Settings

Copy `.env.example` to `.env` locally and set the admin password. Keep that file private.

| Variable | Default | Effect |
|---|---|---|
| `SERVICE_HOST` | `127.0.0.1` | Native bind address; the image sets `0.0.0.0` |
| `SERVICE_PORT` | `29407` | Native port and Compose's published host port; container port stays 29407 |
| `SERVICE_BIND` | `0.0.0.0` | Docker published bind; use `127.0.0.1` for this machine only |
| `SERVICE_ADMIN_PASSWORD` | Empty | Enables admin and caller token checks; required by Compose and for exposed native binds |

Gateway addresses and credentials, limits and data-folder settings belong on admin pages. The named `conversationgateway_data` volume preserves state under `/data`.

## Start

```bash
docker compose up -d --build
```

## Check

```bash
curl http://127.0.0.1:29407/health
```

First run: set `SERVICE_ADMIN_PASSWORD`, sign in to `/admin/`, create a caller token, then open `/admin/gateways.html`, save a gateway and press **Test**. A model running on the Docker host needs `host.docker.internal` in its gateway address. Ready becomes true when any gateway is saved; it does not prove connectivity.

## Updating

```bash
docker compose up -d --build
```

State survives in the named volume. Restart clears in-memory aggregate usage.

## Problems

| Symptom | Check |
|---|---|
| No gateways / 422 unknown gateway | Save the requested id on `/admin/gateways.html` |
| 401 | Use a valid caller token in `X-Internal-Token`; admin uses its separate password |
| 429 | Caller rate or in-flight limit; honor `Retry-After` |
| 502 / 503 | Test the gateway; verify address, credentials and installed model |
| Image rejected | Check capability flags and base64 data; Scuti image input remains unverified |
| Network missing | Start the Citadel stack that creates `citadel_core` |
| Startup refused | Set the admin password before binding outside loopback |
