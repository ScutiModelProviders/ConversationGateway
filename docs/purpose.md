# Purpose

**Kind:** chat messages → text or tool calls (conversation gateway)

**Group:** Conversation

**Tags:** `cpu`, `http`, `streaming`, `tool-calls`, `json-schema`, `thinking`

| | |
|---|---|
| Input | Saved gateway id, chat messages, optional tools, schema, reasoning and base64 images. |
| Output | Normalized text or tool calls, reasoning, token usage and stop reason; JSON or NDJSON. |
| Needs | Anthropic, OpenAI-compatible providers including Gemini, or CNV_MiniCPM52B_Model, CNV_BitNet2B_Model, CNV_LFM3_Model, CNV_SparkX26_Model. |
| Runs on | CPU API; holds no model. Needs provider credentials or reachable CNV services. |

**Use for:** one chat contract for Anthropic, OpenAI-compatible, Gemini and Scuti models.
**Not for:** running tools, sessions, failover or model tiers.

The current shared vocabulary has no external-provider gateway tag. None is invented here; shared vocabulary and tool-group audit registration belong to Task 11.