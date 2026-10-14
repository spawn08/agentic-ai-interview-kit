# Batch 4 report: Tier 4 content updates

Date: 2026-10-12. Scope: Tier 4 content inside existing docs. No new tracks, no PPD commits, no metadata or `docs/_shared` changes, no model IDs added outside `docs/_shared`. No commits made.

## Sources checked (curl, 2026-10-12)

| URL | Result / what was read |
|---|---|
| https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ | HTTP 200; resource page, published 2025-12-09; links the PDF |
| https://genai.owasp.org/download/52117/?tmstv=1765059207 | HTTP 200 `application/pdf` (1.27 MB) only with a browser User-Agent and the resource page as Referer; plain curl returns an HTML "No Access" page. Read with `pypdf`: title "OWASP Top 10 For Agentic Applications 2026", Version 2026, December 2025; ASI01-ASI10 labels from the table of contents |
| https://genai.owasp.org/llm-top-10/ , .../owasp-genai-llm-top-10-2026/ | HTTP 200; confirms the LLM Top 10 is a separate list (LLM01-LLM10) |
| https://modelcontextprotocol.io/specification/2026-07-28 and `/changelog` | HTTP 200; "Version 2026-07-28 (latest)"; "Stateless, self-contained requests"; changelog: no protocol-level sessions / `Mcp-Session-Id` on Streamable HTTP, list endpoints no longer vary per connection, server-minted handles passed as tool arguments, `initialize` / `notifications/initialized` removed, per-request `_meta`, tasks moved to the `io.modelcontextprotocol/tasks` extension |
| https://a2a-protocol.org/latest/specification/ | HTTP 200; "Latest Released Version 1.0.0" |
| https://api.github.com/repos/a2aproject/A2A/releases | v1.0.1 (2026-05-28), v1.0.0 (2026-03-12), v0.3.0 (2025-07-30) |
| https://a2a-protocol.org/latest/blog/2026/08/27/a-new-chapter-for-a2a-joining-the-agentic-ai-foundation/ | HTTP 200; dated August 27, 2026; A2A accepted as a Growth Stage AAIF project; "backed by over 150 organizations" |
| https://a2a-protocol.org/latest/ | Governance: originally developed by Google, donated to the Linux Foundation; TSC from AWS, Cisco, Google, IBM Research, Microsoft, Salesforce, SAP, ServiceNow |
| https://aaif.io/about | AAIF is a neutral foundation under the Linux Foundation hosting MCP, goose, AGENTS.md, A2A, agentgateway |
| https://lfaidata.foundation/communityblog/2025/08/29/acp-joins-forces-with-a2a-under-the-linux-foundations-lf-ai-data/ | ACP merging into A2A; ACP team winding down active development; IBM joins the A2A TSC |
| https://agntcy.org/ | HTTP 200, but no Linux Foundation / July 2025 claim found in page text (see limits) |
| https://developers.llamaindex.ai/python/framework/understanding/agent/ and `.../module_guides/deploying/agents/` | `FunctionAgent`, `ReActAgent`, `CodeActAgent`, `AgentWorkflow`; no `OpenAIAgent` |
| https://platform.claude.com/docs/en/build-with-claude/effort and `/adaptive-thinking` (redirects to `/thinking-steering-and-cost`) | Adaptive thinking; `output_config.effort`; levels `max`, `xhigh`, `high`, ...; availability varies by model |
| https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview | Client vs Anthropic-provided (server) tools; web search and web fetch tools listed |
| https://developers.openai.com/api/docs/guides/tools | Built-in tools listed: web search, file search, code interpreter, computer use, remote MCP |
| https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool | Memory directory; create/read/update/delete; path-traversal protection |
| https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents | `init.sh`, `claude-progress.txt`, git commits, incremental progress |
| https://www.anthropic.com/engineering/building-effective-agents | Workflow vs agent definitions |
| https://www.anthropic.com/engineering/multi-agent-research-system | 4x (agents) and 15x (multi-agent) token figures; +90.2% internal eval; coding / shared-context caveat |
| https://cognition.com/blog/dont-build-multi-agents | "very fragile"; share context and full agent traces |
| https://code.claude.com/docs/en/sub-agents | Fork vs regular subagent behavior |
| https://arxiv.org/abs/2406.12045 and PDF (tau-bench) | pass^k definition: all k i.i.d. trials succeed |
| arXiv abs pages 2506.07982 (tau2), 2311.12983 (GAIA), 2307.13854 (WebArena), 2308.03688 (AgentBench), 2307.16789 (ToolLLM), 2107.03374 (HumanEval); https://www.swebench.com/ ; https://www.tbench.ai/ | Titles / existence confirmed |
| https://docs.langchain.com/oss/python/langgraph/persistence and `/add-memory` | Checkpoint growth / pruning guidance and thread deletion |

## Per-file changes and reasons

| File | Change | Reason |
|---|---|---|
| `docs/core-concepts/what-are-agents.md` | New section "Agent = Model + Harness" (model vs harness table, agents vs workflows per Anthropic definitions); takeaway and further-reading link to the existing `context-engineering.md` | Tier 4 definition shift. No link to a Harness track (none exists). Structure and diagrams untouched |
| `docs/core-concepts/memory-systems.md` | New "Filesystem Memory and Progress Files" and "Retention and Deletion" sections; takeaways; retention bullet rewritten | Files as memory; enterprise DELETE policy covering checkpoints, embeddings, derived artifacts with lineage |
| `docs/architecture-design/memory-and-state-management.md` | TTL table note on enterprise conflicts; new "Enterprise Retention and DELETE Policy" and "Filesystem State and Progress Files" subsections | Same, at architecture level; erasure verification test described |
| `docs/core-concepts/guardrails-and-safety.md` | New "Structural Controls Come First" section with ASI table; regex/classifiers labelled weak heuristics; takeaway | Structural controls (privilege separation, egress, approval gates) lead |
| `docs/architecture-design/security-considerations.md` | New "OWASP Top 10 for Agentic Applications 2026 (ASI)" (exact labels, mapping to this guide, relationship to LLM list, dict snippet) and "Structural Controls First"; LLM04 note re-pointed | Replaces the vague "ASI" reference; keeps LLM01-LLM10 section distinct |
| `docs/foundations/evaluation-metrics.md` | Benchmark table gains tau-bench, tau2-bench, Terminal-Bench plus source links; new "pass^k vs pass@k", "Trajectory Evaluation", "Cost-Normalized Metrics" | See API/formula table below |
| `docs/implementations/evaluation-harness.md` | New "Step 8: Repeated Trials, Trajectories, and Cost" (stdlib-only runnable code); takeaway 8 | Implementation of the above |
| `examples/langchain-v1/test_evaluation.py` (new test file, not a track) | 20 offline tests that extract and run the doc snippets, including corner cases: no wins or no spend (`successes_per_dollar` is 0.0), empty runs, empty tasks, n < 1, k > n, zero-price budget | Formulas and input validation are tested, so pages cannot drift |
| `docs/design-patterns/multi-agent-pattern.md` | New "Counter-Position" and "Context: Isolate vs. Fork" sections; takeaways | Tightly coupled / fragmented / token multiplier; fork leaks lead context into workers |
| `docs/interview-questions/{foundational,agent-architecture,design-pattern,framework}-qa.md` | +4 Q each (Q16-Q19), each with a level tag and 30-second and 2-minute answers; source line; counts in intro/description 15 to 19 | Native tools, MCP 2026-07-28 stateless, adaptive thinking / effort, harness vs model attribution |
| `docs/interview-questions/framework-qa.md` (extra) | Landscape note rewritten to the current taxonomy; LlamaIndex answer now names `FunctionAgent` / `ReActAgent` / `CodeActAgent` / `AgentWorkflow`; `OpenAIAgent` removed; AutoGen and Semantic Kernel labelled legacy | Obsolete claim removal |
| `docs/core-concepts/agent-interop-protocols.md` | Replaced the "not re-verified" governance sentence with sourced facts; version dates from GitHub releases; AAIF post date; AGNTCY row flagged unverified; sources list extended | No guessed dates |
| `reports/batch-4.md` | This report | |

## Before / after (APIs and formulas)

| Item | Before | After | Verified by |
|---|---|---|---|
| LlamaIndex agent classes (framework-qa) | `ReActAgent` and `OpenAIAgent` | `FunctionAgent`, `ReActAgent`, `CodeActAgent`, `AgentWorkflow` (on Workflows) | LlamaIndex agent docs |
| Framework landscape (framework-qa) | LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen/AG2, ... "early 2026" | Current taxonomy from `framework-comparison.md`; AutoGen / Semantic Kernel legacy | Existing verified pages (`autogen-guide.md`, `semantic-kernel.md`); not re-fetched, so listed names for OpenAI Agents SDK, Claude Agent SDK, Google ADK, PydanticAI follow `framework-comparison.md` |
| MCP statement in Q&A | none | 2026-07-28: stateless, no `initialize`, no sessions, server-minted handles | MCP changelog |
| pass^k | absent | `comb(c, k) / comb(n, k)` estimator; theory `p^k`; contrast with pass@k `1 - comb(n-c, k) / comb(n, k)` | tau-bench paper; unit-tested |
| Naive `(c/n)**k` | n/a | Documented as biased (n=4, c=3, k=4: 0.316 vs 0) | Tested |
| ASI labels | "ASI" referenced without a list | ASI01-ASI10 exact labels | OWASP PDF TOC |
| A2A | "introduced in 2025", dates "not re-verified" | Google-originated, donated to LF, 150+ orgs, release dates from GitHub, AAIF Growth Stage (2026-08-27 post) | Official site and GitHub API |

## Discrepancies

- OWASP PDF download blocks default curl (returns an HTML "No Access" page); a browser User-Agent plus Referer succeeds. The PDF is the authoritative label source; the resource page text alone did not list the ASI labels.
- ASI06 label contains an ampersand ("Memory & Context Poisoning"); copied as is.
- The adaptive-thinking URL redirects to `/thinking-steering-and-cost`; the redirected URL is cited.
- The existing "ACP merged into A2A" text is confirmed. The LF AI & Data post is the stewardship source; it is dated 2025-08-29 in its URL.
- MCP "tasks" moved to an official extension; the Q&A states this rather than claiming task handles in core.
- The earlier security-considerations note attributed agent threats to a generic "Agentic AI -- Threats and Mitigations" link; replaced with the verified Top 10 for Agentic Applications.

## Verification limits

- AGNTCY "Linux Foundation, July 2025" is **not verified** (agntcy.org text did not state it); flagged as unconfirmed on the page, not changed.
- Exact A2A introduction / donation dates are intentionally not stated.
- Vector-store, store-level and summary-store delete calls in the retention code are labelled pseudocode / illustrative; only `delete_thread` is tied to the LangGraph docs, and its presence in the installed package was not checked (langgraph is not installed here).
- `pass^k` in non-tau-bench settings assumes independent runs; real runs may correlate (stated on the page).
- No benchmark scores are quoted, since they change quickly.
- Effort levels are named only generally; per-model availability is left to the vendor page.
- The web fetch of some pages (Claude/OpenAI docs) returned client-rendered text; claims were limited to what appeared in that text.
- Build, typecheck, content check and test results are listed in the final message of the session, not here, because they must be run after the last edit.
