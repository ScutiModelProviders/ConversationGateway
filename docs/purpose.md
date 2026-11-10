# Purpose

**Kind:** chat messages → text or tool calls (conversation gateway)

**Tags:** `cpu`, `http`, `streaming`

| | |
|---|---|
| Input | Saved gateway id, chat messages, optional tools, schema, reasoning and base64 images. |
| Output | Normalized text or tool calls, reasoning, token usage and stop reason; JSON or NDJSON. |
| Needs | `CNV_MiniCPM52B_Model`, `CNV_BitNet2B_Model`, `CNV_LFM3_Model` or `CNV_SparkX26_Model`, or an Anthropic or OpenAI-compatible provider (Gemini included), configured as gateways on the admin page. The CNV services put the tool in the Conversation model group. |
| Runs on | CPU API; holds no model. Needs provider credentials or reachable CNV services. |

**Use for:** one chat contract for Anthropic, OpenAI-compatible, Gemini and Scuti models.
**Not for:** running tools, sessions, failover or model tiers.
