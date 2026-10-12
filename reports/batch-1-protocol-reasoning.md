# Batch 1 – Tier 1 Protocol + Reasoning Report

Date of verification: 2026-10-12 (docs fetched live with curl). No commits; no files outside the owned set plus this report.

## Files
| File | Change |
|---|---|
| `docs/core-concepts/model-context-protocol.md` | Already rewritten earlier in the working tree for 2026-07-28; this pass re-verified claims against live docs, added a legacy→current migration flowchart (Mermaid), corrected the server identity key (`io.modelcontextprotocol/serverInfo`), added an Official Sources section. Interview section preserved. |
| `docs/foundations/reasoning-models.md` | Rewrote intro and "Controlling Reasoning Depth"; interview, routing, planning sections preserved (answers updated for effort levels). Removed unsupported 3-5x / 1.5-2x cost multipliers; no model IDs or prices (env vars). |

## Sources (curl, 2026-10-12)
- MCP: `modelcontextprotocol.io/specification/latest` (HTTP 200, redirects to `/specification/2026-07-28`), `/specification/2026-07-28/changelog`, `/community/feature-lifecycle`, `/docs/learn/versioning`, extension overview pages for Tasks and Apps, `aaif.io/about`.
- Anthropic: `platform.claude.com/docs/en/build-with-claude/{effort, adaptive-thinking (redirects to thinking-steering-and-cost), extended-thinking}`.
- OpenAI: `platform.openai.com/docs/guides/reasoning` (redirects to `developers.openai.com/api/docs/guides/reasoning`).

## Verified claims
- MCP latest = 2026-07-28; per-request `_meta` version/capabilities; `server/discover` MUST; MRTR `input_required`; `ttlMs`/`cacheScope`; `subscriptions/listen`; SSE `Last-Event-ID` removal; `Mcp-Method`/`Mcp-Name` headers; `logLevel` in `_meta`; Tasks moved to `io.modelcontextprotocol/tasks` extension; DCR deprecated for Client ID Metadata Documents; RFC 9207 `iss`; twelve-month minimum deprecation window with ninety-day security floor.
- Anthropic: effort is `output_config.effort` (not in `thinking`), levels low/medium/high/xhigh/max with per-model availability and defaults; adaptive thinking `{"type":"adaptive"}`; manual `enabled`+`budget_tokens` deprecated on 4.6 family and rejected on 4.7+.
- OpenAI: `reasoning.effort` values are model-dependent (none/minimal/low/medium/high/xhigh/max); some models reject `none`/`minimal` (HTTP 400); Responses usage `output_tokens_details.reasoning_tokens`; `max_output_tokens` includes reasoning; `incomplete` status.

## Migrations
- MCP: initialize/session model → per-request `_meta`; HTTP+SSE → Streamable HTTP; roots/sampling/logging → tool args / provider APIs / stderr+OTel (deprecated, not removed); Tasks → optional extension; DCR → Client ID Metadata Documents.
- Reasoning: Anthropic `budget_tokens` → adaptive + `output_config.effort` (Legacy `<details>` only); OpenAI `reasoning_effort`-only guidance → model-dependent `reasoning.effort`; hardcoded model IDs → `OPENAI_REASONING_MODEL` / `ANTHROPIC_MODEL`.

## Unverified / placeholders
- SDK support for 2026-07-28 (per SDK) and whether the installed Anthropic Python SDK types `output_config` as a keyword: unverified.
- Chat Completions reasoning-token usage field name and Anthropic thinking `display` parameter placement: not verified (page says only that a display setting exists).
- MCP Apps details beyond the overview URL returning 200: not read in depth. All code is illustrative and not executed.
