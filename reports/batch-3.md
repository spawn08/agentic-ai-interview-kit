# Batch 3 report: model-ID and token-price centralization

Date: 2026-10-12. Scope: Tier 3 (MODEL/COST) across all existing docs. No new tracks, no Tier 4 additions, no metadata changes, no PPD commits. Tier 2 import/parser sections were not touched structurally; edits were line-level replacements.

## Shared partial

- Created `docs/_shared/models.md` (MDX partial, not a routed doc), dated 2026-10-12.
- Imported and rendered in `docs/index.md` under a new `## Model and Price Reference` section (`<ModelsReference />`).
- **Parent action:** the docs config (`docusaurus.config.ts`) should exclude `docs/_shared/**` (e.g. `docs: { exclude: ['**/_shared/**'] }`) so it never routes. Underscore-prefixed paths are already ignored by default for `.md`/`.mdx` files, and `npm run build` passes today; the explicit exclude is a safety net. I did not edit the config.

## Sources checked (curl, 2026-10-12)

| URL | Date checked | Result |
|---|---|---|
| https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-12 | HTTP 200; per-1M-token input/output rates for four current models read into the partial |
| https://platform.claude.com/docs/en/models/overview | 2026-10-12 | HTTP 200; model API IDs, 1M context / 128K max output read |
| https://developers.openai.com/api/docs/pricing | 2026-10-12 | HTTP 200; Standard-tier per-1M rates read |
| https://developers.openai.com/api/docs/guides/embeddings | 2026-10-12 | HTTP 200; embedding model ID confirmed, no price on this page |
| https://ai.google.dev/gemini-api/docs/pricing | 2026-10-12 | HTTP 200; embedding text-input rate read |
| https://platform.openai.com/docs/pricing, https://openai.com/api/pricing/ | 2026-10-12 | Redirect/blocked for curl; superseded by developers.openai.com above |

## Discrepancies and placeholders

- **Discrepancy:** every prior doc price (e.g. $2.50/$10 and $5/$15 per 1M, $0.15/$0.60) and every model ID (gpt-4o family, o1-preview/mini, gpt-4-turbo, gpt-3.5-turbo, claude-3-5/4 snapshot IDs) did not match the current vendor pages; all were removed rather than updated, because prices must come from config.
- **Placeholder (unverified):** OpenAI embedding price -- not on the pricing page; documented as `<UNVERIFIED>` in the partial. Open-weight model prices: `<UNVERIFIED>` (host-dependent).
- **Placeholder (config):** `projects/llm-gateway` `pricing.json` values are `<from vendor pricing page>`; the gateway loads them explicitly via `load_pricing()` and has no defaults.
- Model-ID examples in the partial come from the vendor pages above; I could not independently confirm each ID resolves in a live API call (no API keys), only that vendor pages list them.

## Conventions applied

- Python snippets: `import os` plus `MODEL = os.environ["AGENT_MODEL"]` (also `AGENT_MODEL_FAST`, `AGENT_EMBEDDING_MODEL`, `AGENT_MODEL_REASONING`, `AGENT_MODEL_ALT`, `AGENT_MODEL_ALT_FAST`, `AGENT_RERANKER_MODEL`, `AGENT_BASE_MODEL`, `AGENT_PPL_MODEL`) per independently runnable snippet. Routing dictionaries use one env-backed variable per tier so tier semantics are preserved.
- `.env`/bash/JSON/YAML/Mermaid: placeholders like `<fast-tier model id>` or env names.
- Prose: tier labels (frontier / standard / fast-tier / second-provider).
- Prices: symbolic `cost = (in_tokens*p_in + out_tokens*p_out) / 1_000_000`, with `p_in`, `p_out` per-1M rates labelled as assumptions from config. Business prices (human review labor, infra, budgets) left as-is.
- Left untouched: the `<details><summary>Legacy` block in `foundations/reasoning-models.md`; vendor/product names that are not model IDs (LlamaIndex, Claude Agent SDK, ChatGPT-for-Autodesk title); tokenizer algorithm names (BERT WordPiece).

## Foundational context-window Q and index

- `foundations/llm-fundamentals.md`: removed the model/context-size table and numbers; replaced with advertised-vs-effective context, context rot, compaction, link to context engineering.
- `interview-questions/foundational-qa.md`: same treatment for the context-window answer; cost answer now shows arithmetic instead of a tariff.
- `docs/index.md`: Why Now rewritten as Model + Harness (AutoGen maturity claim removed), linking existing `what-are-agents.md` and `context-engineering.md`.

## Per-file changes (old model-ID lines / price lines removed, env vars introduced)

> **How to read the counts.** The "lines removed" columns were produced by a regex scan of the pre-migration text for model-ID-like and price-like patterns. They are a rough effort indicator, **not an authoritative inventory**: the regex over- and under-matches (multi-line edits, IDs inside prose, prices written as `$x` vs `x/1000`). The authoritative evidence is the file diff (`git diff`) and the regression scan in `examples/langchain-v1/test_pricing.py`. The Reason column states why each file was touched.

| File | Model-ID lines removed | Price lines removed | Env vars used after | Reason |
|---|---|---|---|---|
| `architecture-design/agent-evaluation-platform.md` | 4 | 6 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/agent-memory-system.md` | 1 | 0 | AGENT_EMBEDDING_MODEL | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/agent-orchestration-at-scale.md` | 9 | 0 | AGENT_MODEL, AGENT_MODEL_FAST | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/code-assistant.md` | 2 | 10 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/content-moderation.md` | 2 | 6 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/customer-support-agent.md` | 28 | 24 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/data-layer-design.md` | 5 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/design-principles.md` | 6 | 7 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/devops-agent.md` | 0 | 1 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/document-processing.md` | 0 | 4 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/domain/building-plan-generator.md` | 0 | 2 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/domain/cad-modifier-agent.md` | 0 | 2 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/domain/chatgpt-for-autodesk.md` | 0 | 3 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/domain/design-review-system.md` | 0 | 4 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/domain/rag-engineering-docs.md` | 0 | 3 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/error-handling-and-recovery.md` | 3 | 2 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/hallucination-mitigation.md` | 2 | 13 | AGENT_EMBEDDING_MODEL, AGENT_RERANKER_MODEL | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/healthcare-assistant.md` | 4 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/memory-and-state-management.md` | 1 | 4 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/multi-agent-communication.md` | 1 | 1 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/observability-and-tracing.md` | 1 | 2 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/observability-platform.md` | 4 | 2 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/production-issues-and-debugging.md` | 6 | 2 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/research-agent.md` | 0 | 1 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/tool-registry-design.md` | 1 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/trading-agent.md` | 0 | 1 | - | hardcoded IDs/prices replaced per conventions above |
| `architecture-design/workflow-orchestrator.md` | 2 | 2 | - | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/agent-architectures.md` | 6 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/context-engineering.md` | 2 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/guardrails-and-safety.md` | 2 | 0 | AGENT_MODEL, AGENT_MODEL_FAST | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/memory-systems.md` | 4 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL, AGENT_MODEL_FAST | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/model-context-protocol.md` | 2 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/planning-and-reasoning.md` | 2 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/tools-and-function-calling.md` | 9 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `core-concepts/what-are-agents.md` | 1 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/chain-of-thought.md` | 3 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/human-in-the-loop.md` | 1 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/multi-agent-pattern.md` | 8 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/plan-and-execute.md` | 4 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/react-pattern.md` | 2 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/reflection-pattern.md` | 2 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/self-refinement.md` | 3 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `design-patterns/tool-use-pattern.md` | 2 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `foundations/embeddings-and-vector-stores.md` | 10 | 0 | AGENT_EMBEDDING_MODEL | hardcoded IDs/prices replaced per conventions above |
| `foundations/evaluation-metrics.md` | 6 | 0 | AGENT_MODEL, AGENT_PPL_MODEL | hardcoded IDs/prices replaced per conventions above |
| `foundations/fine-tuning-overview.md` | 4 | 1 | AGENT_BASE_MODEL | hardcoded IDs/prices replaced per conventions above |
| `foundations/llm-fundamentals.md` | 12 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `foundations/prompting-techniques.md` | 8 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `foundations/rag-basics.md` | 7 | 0 | AGENT_EMBEDDINGS, AGENT_EMBEDDING_MODEL, AGENT_MODEL, AGENT_RERANKER_MODEL | hardcoded IDs/prices replaced per conventions above |
| `foundations/reasoning-models.md` | 6 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `frameworks/autogen-guide.md` | 8 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `frameworks/crewai-guide.md` | 2 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `frameworks/framework-comparison.md` | 10 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `frameworks/langchain-overview.md` | 6 | 0 | AGENT_EMBEDDINGS, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `frameworks/langgraph-deep-dive.md` | 1 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `frameworks/llamaindex-agents.md` | 10 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `frameworks/openai-assistants-api.md` | 4 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `frameworks/semantic-kernel.md` | 3 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `implementations/basic-react-agent.md` | 1 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `implementations/evaluation-harness.md` | 1 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `implementations/langgraph-workflow.md` | 1 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `implementations/multi-agent-crew.md` | 2 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `implementations/rag-agent-with-tools.md` | 4 | 0 | AGENT_EMBEDDINGS, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `implementations/tool-calling-agent.md` | 4 | 1 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `index.md` | 1 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `interview-questions/behavioral-and-scenario.md` | 2 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `interview-questions/design-pattern-qa.md` | 2 | 0 | - | hardcoded IDs/prices replaced per conventions above |
| `interview-questions/foundational-qa.md` | 5 | 1 | AGENT_EMBEDDING_MODEL | hardcoded IDs/prices replaced per conventions above |
| `interview-questions/framework-qa.md` | 1 | 0 | AGENT_MODEL, AGENT_MODEL_ALT, AGENT_MODEL_FAST | hardcoded IDs/prices replaced per conventions above |
| `projects/agent-evaluation-framework.md` | 3 | 1 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `projects/code-assistant-agent.md` | 3 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `projects/customer-support-agent.md` | 2 | 0 | AGENT_MODEL_FAST | hardcoded IDs/prices replaced per conventions above |
| `projects/data-pipeline-agent.md` | 1 | 0 | AGENT_MODEL_FAST | hardcoded IDs/prices replaced per conventions above |
| `projects/event-driven-agent.md` | 4 | 9 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `projects/llm-gateway.md` | 27 | 19 | AGENT_EMBEDDING_MODEL, AGENT_MODEL, AGENT_MODEL_ALT, AGENT_MODEL_ALT_FAST, AGENT_MODEL_FAST, AGENT_MODEL_REASONING | hardcoded IDs/prices replaced per conventions above |
| `projects/multi-agent-orchestration.md` | 6 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |
| `projects/production-rag-engine.md` | 11 | 0 | AGENT_EMBEDDING_MODEL, AGENT_MODEL_FAST, AGENT_RERANKER_MODEL | hardcoded IDs/prices replaced per conventions above |
| `projects/research-agent.md` | 3 | 0 | AGENT_MODEL | hardcoded IDs/prices replaced per conventions above |

## Special cases

- `architecture-design/data-layer-design.md`: retired IDs (text-embedding-ada-002, dated gpt-4o/claude snapshots, 1536-dim comments) replaced with env-backed references and model-card wording.
- `projects/llm-gateway.md`: provider `models` lists now use env-backed variables (`MODEL`, `MODEL_FAST`, `MODEL_REASONING`, `MODEL_ALT`, `MODEL_ALT_FAST`); retired gpt-4-turbo, gpt-3.5-turbo, o1-preview, o1-mini, claude-3-5-haiku IDs deleted; `cost_per_1k_*` fields replaced by `price_in_per_1m`/`price_out_per_1m` loaded from `GATEWAY_PRICING_FILE`; cost math uses `/ 1_000_000`; savings table made symbolic.
- `foundations/embeddings-and-vector-stores.md`: model/dimension table replaced by model-class table (dimensions vary; read from model card).

## Verification

- `npm run build` succeeds.
- All Python fences containing `os.environ[` parse (`ast.parse`) and import `os`.
- Residual grep for model IDs outside Legacy details and `_shared`: none (besides vendor/product names listed above).
- Limitation: some price-adjacent business figures (storage, human labor, instance costs) intentionally retained.

## Amendment: Tier 3 review fixes (2026-10-12)

Independent review reproduced the issues below; each row is a before/after for one migration. Rates and model IDs remain config-driven; no tariff was invented, and unverifiable prices stay `<UNVERIFIED>` placeholders, never numeric zero.

| Area | Before | After |
|---|---|---|
| `projects/llm-gateway.md` quickstart `.env` | Only two model variables; curl step used an unset `$AGENT_MODEL_FAST` | Every role (`AGENT_MODEL`, `_FAST`, `_REASONING`, `_ALT`, `_ALT_FAST`), `AGENT_EMBEDDING_MODEL`, Azure keys, pricing file; reader-owned `.env` loaded with `set -a`, `source .env`, `set +a` as separate commands |
| gateway `load_pricing()` | `float("<from vendor pricing page>")` raised a raw `ValueError` | `SystemExit` naming `provider.key`, requiring finite non-negative numbers for openai, anthropic, azure_openai; no fallback value. Placeholders in the docs stay placeholders |
| gateway `MODEL_PROVIDER_MAP` | Dict literal: roles sharing an ID overwrote each other and lost the azure fallback | `build_model_provider_map()` merges with `setdefault` and unique providers; models are not forced to be distinct |
| gateway embedding model | Module-level `os.environ[...]` for a feature only the optional semantic-cache upgrade uses; duplicate `import os` | `get_embedding_model()` reads lazily; duplicate imports removed |
| `_shared/models.md` | Claimed an Anthropic ID as the default, though snippets use OpenAI SDKs | No universal default; env must match the snippet's provider SDK; provider-scoped examples; `provider:model` form explained for `create_agent`; OpenAI embedding row (price `<UNVERIFIED>`) and separate API vs local embedding variables |
| embeddings / vector stores | One `AGENT_EMBEDDING_MODEL` for both API and SentenceTransformer; hardcoded dimension outputs | `AGENT_LOCAL_EMBEDDING_MODEL` for local models; dimensions printed from `len()` / `.shape`, or marked illustrative; same split in `production-rag-engine.md` |
| `architecture-design/data-layer-design.md` | `vector(1536)` and `size=1536` | `vector(${EMBEDDING_DIMENSION})` template with explanation; Qdrant size measured from a real embedding |
| Remaining hardcoded rates | `0.0025/0.01` (multi-agent-orchestration), `0.005/1000`, `0.015/1000` (event-driven-agent), `Field(default=0.01)` (tool-calling-agent), per-1K fields (design-principles), `in_price=0.0` defaults (evaluation-harness) | One unit everywhere: USD per 1M tokens from `PRICING_INPUT_PER_MILLION` / `PRICING_OUTPUT_PER_MILLION`; required, non-negative, no defaults |
| `event-driven-agent` docstring | Derived `$6,000-30,000/hr` | `600,000 x c` per hour, consistent with its cost table |
| `hallucination-mitigation` | Env read in default arguments (import time) | `None` default, resolved lazily in the constructor |

Scan note: besides the files above, a broad scan of docs for decimal tariff constants found only business budgets, probabilities, thresholds and currency-conversion demos, which are intentionally unchanged. Prevention content and Tier 4 were not edited.

Tests: `examples/langchain-v1/test_pricing.py` (offline) extracts and executes the gateway configuration block (valid, missing, invalid, placeholder prices; duplicate-ID merge; lazy embedding model), the tool cost tracker, harness and router fields, the lazy constructors, and scans docs for forbidden tariff patterns and env reads in function defaults.
