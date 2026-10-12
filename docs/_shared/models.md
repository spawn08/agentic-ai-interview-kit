{/*
  MDX PARTIAL -- not a routed doc. Single source of truth for model IDs and token prices.
  Last verified: 2026-10-12 against the vendor URLs listed below (fetched with curl).
  Docusaurus ignores underscore-prefixed paths by default; the parent config should still
  exclude `docs/_shared/**` explicitly so it is never emitted as a page.
*/}

:::note Model and price reference -- verified 2026-10-12
Model IDs, tiers, and prices change often. Every example in this guide reads the model ID from an
environment variable instead of hardcoding it. Prices below are **list prices per 1M tokens in USD**,
checked on **2026-10-12**; treat them as an *assumption to refresh*, never as a constant in code.
:::

**No universal default model.** Snippets in this guide read model IDs from environment variables, and
the value you export must belong to the **same provider SDK the snippet uses**. An Anthropic ID will
not work in an OpenAI snippet, and vice versa. Examples below are scoped per provider; they are not
interchangeable.

```bash
# Anthropic snippets (anthropic SDK, langchain-anthropic)
export AGENT_MODEL="claude-sonnet-5-5"

# OpenAI snippets (openai SDK, langchain-openai)
export AGENT_MODEL="gpt-6.1-sol"
```

Export only the one that matches the provider your snippet imports. When a snippet passes the ID to
LangChain v1 `create_agent` (or `init_chat_model`) as a single string, LangChain expects
`provider:model` form, for example `anthropic:claude-sonnet-5-5` or `openai:gpt-6.1-sol`; build it with
`f"{provider}:{os.environ['AGENT_MODEL']}"` or export the prefixed value. Provider-specific clients
(`ChatAnthropic(model=...)`, `OpenAI().chat.completions.create(model=...)`) take the bare ID.

Embeddings use separate variables, because API and local models are different kinds of ID:

```bash
export AGENT_EMBEDDING_MODEL="<api-embedding-model-id>"        # hosted embedding API (OpenAI, Google, ...)
export AGENT_LOCAL_EMBEDDING_MODEL="<sentence-transformers-model-name>"  # local SentenceTransformer
export AGENT_RERANKER_MODEL="<cross-encoder-reranker-name>"          # local reranker (CrossEncoder)
export AGENT_NLI_MODEL="<nli-cross-encoder-checkpoint>"              # local NLI entailment checker
```

| Tier (prose label) | Example API ID | Input / 1M tok | Output / 1M tok | Source (checked 2026-10-12) |
|---|---|---|---|---|
| Frontier | `claude-fable-5-1` | $10 | $50 | [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), [models overview](https://platform.claude.com/docs/en/models/overview) |
| Strong / general (example model) | `claude-sonnet-5-5` | $2 | $10 | same |
| Fast / cheap | `claude-haiku-5-5` | $0.10 (prompts up to 100K tokens) | $0.50 | same |
| Frontier (OpenAI) | `gpt-6-astra` | $10.00 | $50.00 | [OpenAI pricing](https://developers.openai.com/api/docs/pricing) |
| Strong / general (OpenAI) | `gpt-6.1-sol` | $2.00 | $10.00 | same |
| Fast / cheap (OpenAI) | `gpt-6-luna` | $0.10 | $0.50 | same |
| Embeddings (Google API) | `gemini-embedding-2` | $0.20 (text input) | n/a | [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| Embeddings (OpenAI API) | `text-embedding-3-small` | `<UNVERIFIED>` | n/a | ID confirmed in the [embeddings guide](https://developers.openai.com/api/docs/guides/embeddings); no price on the pricing page |
| Embeddings (local) | any SentenceTransformer name | your own compute cost | n/a | no vendor price |

Anthropic's four current models list a 1M-token context window and 128K max output; Haiku-tier long
prompts (over 100K tokens) are priced higher ($0.50 input / $2.50 output). Batch, Flex, Fast, and
Ultrafast modes on OpenAI use different rates; the table shows **Standard, short-context** rates.

**Unverified placeholders (explicit, not invented):**

| Item | Status |
|---|---|
| OpenAI embedding price (`text-embedding-3-small` and similar) | The embeddings guide (`https://developers.openai.com/api/docs/guides/embeddings`, checked 2026-10-12) confirms the ID `text-embedding-3-small` exists, but **no price appears on the pricing page**. Price is `<UNVERIFIED>`; read it from your own config. |
| Open-weight models (Llama, Mistral, etc.) | Priced by your host or your own GPU cost; no single vendor price. `<UNVERIFIED>` |

**Cost formula used throughout the guide (symbolic, rates from config):**

```python
# p_in / p_out are USD per 1M tokens, loaded from your pricing config -- not defaults.
cost = (in_tokens * p_in + out_tokens * p_out) / 1_000_000
```
