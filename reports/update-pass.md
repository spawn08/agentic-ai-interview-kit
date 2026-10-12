# Existing-content update pass — final integration report

Verified: **2026-10-12**. Audit baseline: `main` at `0403f94`.

This pass updates existing content before blueprint Phase B. It adds successor framework pages, examples, shared reference material, and regression prevention, **not new learning tracks**. Batch reports below provide per-file reasons, official-source URLs and check dates, migration before/after details, and unverified items. Earlier handoff blockers and test counts are historical; final-state amendments supersede them.

No commits, pushes, or PRs were created by this agent. The repository already contains changes beyond the audit baseline; the working-tree diff alone is not the entire update pass. Separate PRs and per-page commits remain a delivery operation requiring authorization.

## Deliverables

| Batch | Completed outcome | Detailed report |
|---|---|---|
| 1 — removed/deprecated APIs | Responses/Conversations/Agents SDK successor and Assistants redirect; Microsoft Agent Framework successor; AutoGen/Semantic Kernel Legacy group and warnings; current LlamaIndex workflows; current framework matrix; stateless MCP eras/migration and adaptive reasoning controls | [Frameworks](batch-1-frameworks.md), [protocol/reasoning](batch-1-protocol-reasoning.md), [verification amendment](batch-1-protocol-reasoning-amendment.md) |
| 2 — code migration | `create_agent` + middleware primary; explicit `StateGraph` reserved for topology; native tool calls replace text parsing; current structured output and partner imports; extracted-fence import and executable tests | [Batch 2](batch-2.md) |
| 3 — models, prices, facts | Dated `docs/_shared/models.md`; provider-compatible environment configuration; symbolic/configurable USD-per-million cost math; embedding dimensions measured/configured; context-window framing and current A2A/ACP stewardship | [Batch 3](batch-3.md), [interop](batch-3-interop.md) |
| 4 — framing | Model + harness; workflows vs agents; filesystem/progress memory and retention/deletion; ASI01–ASI10 structural controls; repeated reliability, trajectories, costs and benchmarks; multi-agent counter-position/isolate-vs-fork; four new level-tagged questions per QA page with 30-second/2-minute answers | [Batch 4](batch-4.md) |
| 5 — prevention | Deprecation deny-list and bounded historical exceptions; model-ID lint; every routed page has `last_verified` with 120-day warnings; PR/main/weekly checks; monthly latest-framework examples/import tests and deduplicated failure issue | [Batch 5](batch-5.md) |

The nonexistent Harness track is not linked: harness framing links to the existing context-engineering page. This deliberately respects the no-new-tracks constraint and avoids broken links.

## Final integration and safety corrections

- `docusaurus.config.ts` installs the client-redirects plugin configuration and explicitly excludes `docs/_shared/**` from routing. The shared `.md` partial is imported into the landing page, not emitted as a separate docs route.
- `sidebars.ts` includes both framework successors and groups superseded Microsoft pages under Legacy. The old Assistants slug redirects to the Responses/Agents SDK page.
- The primary ReAct implementation and its customization section use native `create_agent` with `ModelCallLimitMiddleware`; tracing/error policy uses `wrap_tool_call`, not a forked ReAct graph.
- Exactly one historical text-parsed ReAct example remains, labeled in `docs/design-patterns/react-pattern.md`. Current implementations and coding challenges use native tool-call objects; interview answers explain reliability, parallel calls, and schema validation.
- Both reviewed calculator implementations use a bounded AST evaluator, never `eval`: only numeric literals, unary signs and `+ - * /`, with length, node-count and magnitude limits. Names, calls, attributes, powers, booleans and nonfinite values are rejected.
- The custom tool-calling topology validates the entire batch before execution. Any invalid tool name/schema rejects every call in that batch, produces exactly one error result per call, and bypasses tool execution. Iteration-limit exits close pending tool-call IDs and return a final AI message; per-turn limits reset on checkpointed follow-up turns.
- Offline tests extract the real documentation fences rather than testing copied implementations. The final ReAct addition contributes 19 tests; the tool-calling safety file contributes 24.
- CI now checks Tier 1 imports/smokes on PRs too. Tier 1 frameworks use isolated environments because dependency constraints conflict; monthly installs strip all version caps. The pinned Tier 2 job remains separate from the latest-release detection job.

## Diagrams

Three standalone Archify diagrams are embedded through the base-URL-aware `DiagramEmbed` component:

| Diagram | Report |
|---|---|
| Framework migration and legacy/current choices | [Framework diagram](diagrams-framework-migration.md) |
| MCP stateless request, per-request `_meta`, and authorization | [MCP diagram](diagrams-mcp-stateless.md) |
| Model + harness responsibilities and lifecycle | [Harness diagram](diagrams-model-harness.md) |

Artifact validation and automated browser containment/screenshot checks passed as recorded in those reports; sidecars are retained under `reports/diagrams-browser/`. No perceptual image review was performed. MCP authorization failure is a reject-before-execution note, not a chronologically incorrect message after successful execution; Bearer tokens belong in HTTP authorization headers, not `_meta`.

## Verification

Final integration checks use Node/Docusaurus in the repository and the previously verified Python 3.12 environment at `/tmp/lcv-b2`. Each command is run independently after the final documentation edit; failures must be reported, not hidden by a pipeline.

| Command / coverage | Result |
|---|---|
| `npm test` | **35 passed** (content-lint regression tests) |
| `npm run check:content` | **84 pages, 0 errors, 0 warnings**, including Python-fence syntax |
| `npm run typecheck` | Passed |
| `npm run build` | Passed; optimized Docusaurus site generated |
| `/tmp/lcv-b2/bin/python -W ignore examples/langchain-v1/check_doc_imports.py` | **0 failures** across all 29 tracked Tier 2 pages; only explicit, checked page-local tutorial modules are excluded |
| `/tmp/lcv-b2/bin/python -m pytest examples/langchain-v1 -q -W ignore` | **144 passed**, offline |
| `git diff --check` | Passed |
| `git diff --stat` and `git status --short` | Inspected final working-tree changes; untracked new report/test files are also part of the deliverable |

The isolated Tier 1 checks were completed earlier on 2026-10-12: OpenAI **2**, Microsoft **4**, LlamaIndex **4**, CrewAI **4** offline smoke tests passed, with zero page import-check failures in each environment. Resolved versions, precise exercised behavior, and exceptions are recorded in [Batch 1](batch-1-frameworks.md); these are not 14 live provider calls or a final rerun in the Tier 2 environment.

The final 144-test count supersedes intermediate 16/101/125-test runs. Builds passed at batch handoffs and after final integration; the initial sidebar-related build failure in Batch 1 is resolved.

## Official-source discrepancies and remaining limitations

- **MCP:** the verified 2026-07-28 revision is stateless; Tasks are an optional extension, not a blanket addition to core. Roots/sampling/logging are deprecated, not all immediately removed. Full SDK support for that revision was not exercised. Authorization was fetched using normally validated HTTPS; TLS checks were never disabled.
- **Reasoning:** effort values and defaults are model-dependent. Anthropic SDK parameter declarations were checked, not each model's live acceptance. OpenAI Responses uses `reasoning.effort`; older Chat Completions spelling is kept only where applicable. No invented universal effort level is claimed.
- **LlamaIndex/CrewAI/Microsoft:** current installed-package tests exposed and repaired additional stale APIs: core `LLMQuestionGenerator` replaces an integration package that forces old LlamaIndex core; CrewAI uses its own `LLM`, and only verified process enum values are taught; Microsoft core needs explicit observability dependencies. Provider execution, full applications, and all illustrated agent variants remain unverified.
- **A2A:** the specification page reports 1.0.0 while the repository release tag is v1.0.1; both are distinguished. ACP convergence is sourced. AGNTCY's historical stewardship/date claim remains explicitly unverified, not guessed.
- **Models/prices:** IDs and tariffs are centralized and dated, not universal defaults. Unverifiable prices remain visible `<UNVERIFIED>` placeholders, never silently zero; readers must configure provider-compatible IDs and rates. Model-ID lint recognizes known families, not arbitrary future names.
- **Imports are not execution:** the import checker parses/imports fences but never runs them. Selected examples run offline against fakes/local HTTP stubs; real inference, real search/tools, production persistence/deletion integrations and full applications were not tested. Illustrative/pseudocode and page-local multi-file boundaries are disclosed.
- **CI:** workflows are implemented and locally inspected, but GitHub Actions, Linux installation of the macOS-captured Tier 2 freeze, and scheduled issue creation have not been remotely exercised. An uncapped monthly install can correctly fail on the known ragas/langchain-community incompatibility rather than conceal it with a version cap.
- **Freshness:** `last_verified` means the date of audit-scoped review, not certification of every pre-existing claim or live API behavior. Warnings after 120 days are nonfatal and appear in logs/job summaries.
- **Dependencies:** an earlier lockfile consistency check reported 63 dependency vulnerabilities. No out-of-scope dependency upgrades or security-control weakening were performed.

These limitations supplement the per-page/batch reports; the update does not claim live certification or verification of every historical example.
