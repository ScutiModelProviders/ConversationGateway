# Deploying ConversationGateway

ConversationGateway is one HTTP service on port 29407, with no local model: callers reach it directly or at `http://conversationgateway:29407` on `citadel_core`.

## Ways to run it

| Path | Guide |
|---|---|
| Docker Desktop on this PC | [Docker on this PC](docs/guide-docker-same-device.md) |
| Docker on another machine | [Deployment machine](docs/guide-docker-deployment-device.md) |
| Directly on Windows | [Without Docker](docs/guide-no-docker-same-device.md) |

Once it runs, follow [the admin web UI guide](docs/guide-web-ui.md).
