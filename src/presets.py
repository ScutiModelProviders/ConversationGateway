"""Starting points for the gateways page: no secrets. A saved gateway is the preset plus the secrets and any edits."""
from __future__ import annotations

PRESETS: dict[str, dict] = {
    "claude": {"provider": "anthropic", "auth": "key", "label": "Claude", "model": "claude-sonnet-5-5"},
    "bedrock": {"provider": "anthropic", "auth": "bedrock", "label": "AWS Bedrock", "model": "anthropic.claude-sonnet-5-5", "aws_region": "us-east-1"},
    "vertex": {"provider": "anthropic", "auth": "vertex", "label": "Google Vertex AI", "model": "claude-sonnet-5-5", "region": "us-east5"},
    "gpt": {"provider": "openai", "auth": "key", "api": "responses", "label": "GPT", "model": "gpt-6.1-sol"},
    "azure": {"provider": "openai", "auth": "azure", "api": "responses", "label": "Azure OpenAI", "model": ""},
    # unverified: confirm against Google's OpenAI-compatibility docs
    "gemini": {"provider": "openai", "auth": "key", "api": "chat", "label": "Google Gemini",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash"},
    "ollama": {"provider": "openai", "auth": "key", "api": "chat", "label": "Ollama", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen3.5:4b"},
    "minicpm": {"provider": "scuti", "label": "CNV_MiniCPM52B_Model", "url": "http://127.0.0.1:29200", "model": "minicpm",
                "capabilities": {"tools": True, "reasoning": True, "schema": True}, "max_tokens_limit": 8192},
    "bitnet": {"provider": "scuti", "label": "CNV_BitNet2B_Model", "url": "http://127.0.0.1:29201", "model": "bitnet", "max_tokens_limit": 4096},
    "lfm3": {"provider": "scuti", "label": "CNV_LFM3_Model", "url": "http://127.0.0.1:29202", "model": "lfm3", "max_tokens_limit": 4096},
    "sparkx": {"provider": "scuti", "label": "CNV_SparkX26_Model", "url": "http://127.0.0.1:29203", "model": "sparkx", "max_tokens_limit": 4096},
    # Same shape as claude / gpt with their own base_url, taken from the Legion gateway files:
    # anthropic: helicone, litellm, openrouter, portkey, omniroute.  openai: deepinfra, fireworks, groq, opencode, perplexity, together, vllm.
}

# Literal metadata from Legion templates; placeholder addresses remain unset.
PRESETS.update({
  "helicone": {
    "provider": "anthropic",
    "auth": "key",
    "label": "Helicone",
    "model": "claude-sonnet-5-5",
    "base_url": "https://anthropic.helicone.ai"
  },
  "litellm": {
    "provider": "anthropic",
    "auth": "key",
    "label": "LiteLLM",
    "model": "claude-sonnet-5-5"
  },
  "omniroute": {
    "provider": "anthropic",
    "auth": "key",
    "label": "OmniRoute",
    "model": "combo/standard"
  },
  "openrouter": {
    "provider": "anthropic",
    "auth": "key",
    "label": "OpenRouter",
    "model": "openrouter/free",
    "base_url": "https://openrouter.ai/api"
  },
  "portkey": {
    "provider": "anthropic",
    "auth": "key",
    "label": "Portkey",
    "model": "claude-sonnet-5-5",
    "base_url": "https://api.portkey.ai/v1"
  },
  "deepinfra": {
    "provider": "openai",
    "auth": "key",
    "label": "DeepInfra",
    "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "api": "chat",
    "base_url": "https://api.deepinfra.com/v1/openai"
  },
  "fireworks": {
    "provider": "openai",
    "auth": "key",
    "label": "Fireworks",
    "model": "accounts/fireworks/models/llama-v3p1-70b-instruct",
    "api": "chat",
    "base_url": "https://api.fireworks.ai/inference/v1"
  },
  "groq": {
    "provider": "openai",
    "auth": "key",
    "label": "Groq",
    "model": "llama-3.3-70b-versatile",
    "api": "chat",
    "base_url": "https://api.groq.com/openai/v1"
  },
  "opencode": {
    "provider": "openai",
    "auth": "key",
    "label": "OpenCode Zen",
    "model": "deepseek-v4.1-flash-free",
    "api": "chat",
    "base_url": "https://opencode.ai/zen/v1"
  },
  "perplexity": {
    "provider": "openai",
    "auth": "key",
    "label": "Perplexity",
    "model": "sonar",
    "api": "chat",
    "base_url": "https://api.perplexity.ai"
  },
  "together": {
    "provider": "openai",
    "auth": "key",
    "label": "Together AI",
    "model": "meta-llama/Llama-4-Maverick",
    "api": "chat",
    "base_url": "https://api.together.xyz/v1"
  },
  "vllm": {
    "provider": "openai",
    "auth": "key",
    "label": "vLLM",
    "model": "",
    "api": "chat"
  }
})
