# Batch 2 – Tier 2 Migration Docs Report

Date of verification: 2026-10-12. No commits. Config/navigation (`sidebars.ts`, `docusaurus.config.ts`) untouched. Out of scope per request: model prices (parent later), Tier 4 files/framing/metadata.

## Sources (fetched via curl, 2026-10-12, HTTP 200 unless noted)
- https://docs.langchain.com/oss/python/migrate/langchain-v1 (create_agent, `system_prompt`, middleware replaces hooks, legacy -> `langchain-classic`)
- https://docs.langchain.com/oss/python/langchain/agents
- https://docs.langchain.com/oss/python/langchain/middleware/overview
- https://docs.langchain.com/oss/python/langchain/structured-output (`ProviderStrategy` auto for supporting models, else `ToolStrategy`; JSON-schema dicts need explicit strategy)
- https://docs.langchain.com/oss/python/langchain/mcp (`langchain.mcp.MCPAdapter`, `langchain[mcp]>=1.4.0`, beta)
- https://docs.langchain.com/oss/python/integrations/vectorstores/chroma (`langchain-chroma`, `from langchain_chroma import Chroma`)
- https://docs.langchain.com/oss/python/integrations/vectorstores (FAISS listed only as "N/A", no package page; `/vectorstores/faiss` = 404)
- https://docs.langchain.com/oss/python/integrations/document_loaders (`PyPDFLoader` still listed under `langchain-community`)
- https://docs.langchain.com/oss/python/integrations/retrievers (no BM25 page; `/retrievers/bm25` = 404)
- https://developers.openai.com/api/docs/guides/structured-outputs (`client.chat.completions.parse`; no `beta.` path shown)
- Installed latest into scratch venv `/tmp/lcv` (Python 3.12.10): langchain 1.4.4, langchain-core 1.6.9, langchain-classic 1.0.8, langchain-community 0.4.2, langchain-chroma 1.1.0, langchain-text-splitters 1.1.3, langgraph 1.2.14, langchain-openai 1.7.0, openai (has both `chat.completions.parse` and `beta.chat.completions.parse`).

## Per-file changes
| File | Before | After | Reason |
|---|---|---|---|
| frameworks/langchain-overview.md | `AgentExecutor`/`create_tool_calling_agent`, `ChatOpenAI("gpt-4o")`, community FAISS | Rewritten around `create_agent`, middleware (`dynamic_prompt`, `wrap_tool_call`, built-ins), structured output (`response_format`, Provider/ToolStrategy), `create_agent` vs `StateGraph` table, `langchain-classic` boundary section, one collapsed Legacy `AgentExecutor` example; `init_chat_model(os.environ["AGENT_MODEL"])`; `InMemoryVectorStore` | v1 migration guide |
| frameworks/langgraph-deep-dive.md | AgentExecutor baseline; `ChatOpenAI gpt-4o` | `create_agent`+middleware vs `StateGraph` framing; `init_chat_model` env | v1 |
| design-patterns/react-pattern.md | Thought/Action text framing; `langgraph.prebuilt.create_react_agent`, `ChatOpenAI` | Native tool calls primary; comparison table; interview point (reliability, parallel calls, schema validation); ONE collapsed Legacy text-parsed example; `create_agent(system_prompt=...)` | v1 |
| core-concepts/planning-and-reasoning.md | `create_react_agent`, `ChatOpenAI` | `create_agent`, `init_chat_model`; note that Act = native tool call | v1 |
| core-concepts/agent-architectures.md | `create_react_agent(prompt=...)` x2 blocks | `create_agent(system_prompt=...)`, env model | v1 (`prompt`→`system_prompt`) |
| core-concepts/tools-and-function-calling.md | `langchain-mcp-adapters` `MultiServerMCPClient`; hard-coded model IDs | `langchain.mcp.MCPAdapter` + `create_agent`; `AGENT_MODEL` | MCP page; no new IDs |
| foundations/rag-basics.md | `langchain.text_splitter`, `langchain_community` FAISS/vectorstores, `langchain.retrievers`, OpenAI embeddings/model IDs | `langchain_text_splitters`, `langchain_chroma`, `langchain_classic.retrievers`, `init_embeddings(AGENT_EMBEDDINGS)`; loaders and `BM25Retriever` stay in `langchain-community` with comments | partner packages verified |
| implementations/rag-agent-with-tools.md | same community/ChatOpenAI patterns, install line | partner packages, env models, updated `pip install`, explanatory note | same |
| foundations/prompting-techniques.md | `client.beta.chat.completions.parse`, `gpt-4o` | `client.chat.completions.parse`, note on `responses.parse`; `AGENT_MODEL` | OpenAI doc |
| interview-questions/coding-challenges.md | Ch.2 and Ch.5 text-parsed ReAct | Ch.2 native tool calls + schema validation + parallel calls (runnable); Ch.5 native-loop; legacy parser removed (see Verification-gap pass); single historical example lives in react-pattern | requirement |
| interview-questions/framework-qa.md, agent-architecture-qa.md, projects/customer-support-agent.md, projects/research-agent.md, implementations/basic-react-agent.md | `AgentExecutor` baselines | reframed as `create_agent`/middleware vs `StateGraph` (basic-react-agent also: env model, `create_agent` info box) | AgentExecutor in 8 files total incl. langchain-overview and langgraph-deep-dive |

New non-doc files: `examples/langchain-v1/{requirements.txt,check_doc_imports.py,test_doc_examples.py}`.

## Verification-gap pass (2026-10-12, second round)

### Historical text-parser example: exactly ONE
- Kept: `design-patterns/react-pattern.md`, collapsed `<details>` "Legacy: the historical text-parsed format" (only historical example in the kit; heading anchor `#native-tool-calls-vs-text-parsed-react`).
- Removed: collapsed Legacy `parse_react_output` block in `interview-questions/coding-challenges.md`, replaced by a link to the react-pattern anchor. `core-concepts/planning-and-reasoning.md` has no legacy example; its note now links to the same anchor. Native tool-call content is unchanged on all three pages.
- Guarded by `test_coding_challenges_has_no_legacy_text_parser`.

### coding-challenges.md Python syntax ("blocks 7/8")
- Root cause: the solutions for Challenge 7 (LLM judge) and 8 (research assistant) contain `cleaned.startswith("```")` inside Python strings. CommonMark renders them correctly (a closing fence must start at column <=3), but the old checker's `` ```python\n(.*?)``` `` regex ended the block at that inner backtick run, so blocks 8/9 were truncated ("unterminated string literal"). An earlier audit "all parse" was invalid because its extractor was naive.
- Fixes: (1) `check_doc_imports.py` now uses a CommonMark line-based fence parser (closing fence >= opener length, <=3 spaces indent; unclosed fence raises). (2) The two snippets now build the marker at runtime (`FENCE = "`" * 3` with an explanatory comment) so even naive renderers/checkers cannot split them; educational logic unchanged.
- Executing every block (not just parsing) exposed one real pre-existing bug: Challenge 6 `mock_embed` used character-frequency vectors, which could not separate routes (technical query routed to billing, `AssertionError`). Replaced by a keyword-presence embedder (comment explains why) and added a default-route assertion. All 8 challenge blocks now exec offline with their own asserts (`test_every_coding_challenge_block_runs`).

### FastMCP -> MCPServer (core-concepts/tools-and-function-calling.md)
Sources (curl, 2026-10-12, HTTP 200):
- https://py.sdk.modelcontextprotocol.io/migration/ ("FastMCP renamed to MCPServer": `from mcp.server.mcpserver import MCPServer`; `mcp.server.fastmcp` raises ModuleNotFoundError)
- https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md (uses `from mcp.server import MCPServer`; `mcp[cli]`)
- https://pypi.org/pypi/mcp/json (mcp 2.3.0), https://pypi.org/pypi/fastmcp/json (fastmcp 4.1.0, separate project), https://gofastmcp.com/getting-started/quickstart (fastmcp's own docs)
Verified locally: `mcp 2.3.0`; `mcp.server.MCPServer is mcp.server.mcpserver.MCPServer` -> True; `MCPServer.run(transport='stdio'|'sse'|'streamable-http')`. Decision: snippet uses the official SDK path from the migration guide (`mcp.server.mcpserver.MCPServer`); the shorter `mcp.server` alias is identical. Added a note that the maintained standalone `fastmcp` (`from fastmcp import FastMCP`) is a distinct package, not a drop-in for the SDK. Not migrated to fastmcp: the page documents the official SDK, and the langchain MCP adapter only needs the `[mcp]` extra. `test_mcp_server_snippet_runs_on_mcpserver` execs the snippet and calls `calculate_bmi` through `mcp.call_tool`.

### Dependencies / import verification
Fresh scratch venv `/tmp/lcv-b2` (Python 3.12.10): `pip install -r examples/langchain-v1/requirements.txt`. Requirements added: `langchain[mcp]` (pulls fastmcp 4.1.0; `langchain.mcp` failed without it), `mcp>=2`, `ragas` (0.4.3), `datasets` (5.1.0), `langgraph-checkpoint-postgres`, `langgraph-swarm`, `anthropic`, `jinja2`, `langchain-experimental`, `sentence-transformers` (pulls torch 2.14.1), `tavily-python`.
Discrepancies found by running ALL 15 Tier 2 pages (the previous run covered 11 and missed the 4 below):
- `agent-architectures.md:366` `langgraph_swarm`, `tools-and-function-calling.md:183` `anthropic`, `prompting-techniques.md:284` `jinja2`, `rag-basics.md:143` `langchain_experimental`, `rag-basics.md:277` `sentence_transformers`, `research-agent.md:148` `tavily`: not installed -> fixed by adding to requirements (not excluded).
- `tools-and-function-calling.md:427` `from langchain.mcp import MCPAdapter` -> `No module named 'fastmcp'` -> fixed by `langchain[mcp]`.
- `rag-basics.md:444` `from ragas import evaluate` fails with latest `langchain-community 0.4.2` (`ragas 0.4.3` imports removed `langchain_community.chat_models.vertexai`). Works with 0.4.1 -> requirements pin `langchain-community>=0.4,<0.4.2` (loaders/BM25 re-verified there). ragas 0.4.3 is the latest release (PyPI); legacy `ragas.metrics` imports emit a DeprecationWarning (recommends `ragas.metrics.collections`, whose API differs); left as is with an in-snippet comment. Snippet is illustrative (needs LLM credentials).
- Remaining exact exclusions (explained in `PAGE_LOCAL_MODULES` in the checker; nothing else is skipped; the page must mention `<module>.py`; unused entries fail): `basic-react-agent.md`: state, tools, nodes, graph; `rag-agent-with-tools.md`: state, nodes, routing, vectorstore, graph; `research-agent.md`: state, tools, nodes, graph (each page's own multi-file tutorial modules).

Per-file command (run from repo root, `/tmp/lcv-b2/bin/python -W ignore examples/langchain-v1/check_doc_imports.py <page>`), result for every one of the 15 pages: `done, 0 failure(s)`:
langchain-overview, langgraph-deep-dive, react-pattern, planning-and-reasoning, agent-architectures, tools-and-function-calling, rag-basics, prompting-techniques, rag-agent-with-tools, basic-react-agent, coding-challenges, framework-qa, agent-architecture-qa, customer-support-agent, research-agent (docs/<section>/<name>.md).
All-pages run (no args): `done, 0 failure(s)`.

### Tests / build
- `/tmp/lcv-b2/bin/python -m pytest examples/langchain-v1 -q -W ignore`: 16 passed (all 8 challenge blocks exec, import check over all Tier 2 pages, exclusion sanity, MCPServer snippet, `create_agent` fake-model loop).
- `npm run build`: SUCCESS (sidebar issue fixed by parent).

## Unverified / limitations
- No snippet that calls a real model/search API was run (no keys); such snippets are marked illustrative where I added comments; others are import- and syntax-verified only.
- `langchain.mcp.MCPAdapter` (beta) not executed against a server.
- FAISS/BM25: no official partner package page found; FAISS replaced by Chroma/InMemoryVectorStore, BM25 stays in `langchain-community` (hence the `<0.4.2` pin until ragas or community resolves the vertexai break).
- `ToolErrorMiddleware` exists in langchain 1.4.4 but is undocumented in the fetched pages; not referenced.
- Many Tier 1/3 pages still hard-code `gpt-4o`; out of scope. Tier 4 sections untouched.

## Addendum: tool-calling-agent.md reviewer fixes (2026-10-12)
Findings fixed in `docs/implementations/tool-calling-agent.md` (tests in `examples/langchain-v1/test_tool_calling_agent.py`):
- P1 calculator: `eval` with empty builtins is not a sandbox. Replaced by a bounded AST evaluator (numeric constants, unary +/-, `+ - * /` only; no names/attributes/calls/exponent; <=200 chars, <=50 nodes, |value|<=1e12, bool and non-finite rejected; JSON error result).
- P2 validation: the node used to append errors and then ToolNode ran every call anyway (duplicate results). Now all-or-nothing: tool name + Pydantic schema checked; any invalid call -> one error ToolMessage per original call, `route_after_validate` bypasses `tools` via `audit` back to `agent`.
- P2 limit: pending tool calls at the limit are finalized (one ToolMessage each + fallback AIMessage, `finalize_limit` -> END), so the next checkpointed turn is well-formed.
- Budget per turn: `begin_turn` resets `iteration_count` at entry (previously accumulated across turns). Mermaid diagram updated.
- Added a short preferred `create_agent` + `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware`/`wrap_tool_call` block (illustrative, needs credentials only when `build_native_agent()` runs); the StateGraph stays as the educational topology.
Verification (/tmp/lcv-b2): `pytest examples/langchain-v1/test_tool_calling_agent.py` 24 passed; `check_doc_imports.py docs/implementations/tool-calling-agent.md` 0 failures; full `pytest examples/langchain-v1` 125 passed (intermediate run).

## Final ReAct and verification amendment (2026-10-12)

- `docs/design-patterns/react-pattern.md`: replaced both unsafe arithmetic paths with a bounded AST calculator; the primary implementation and customization example now use native `create_agent` with `ModelCallLimitMiddleware`. Loop-policy customization uses `wrap_tool_call` instead of a forked `StateGraph`; the sole historical text parser remains explicitly labeled. Model injection supports offline tests without credentials.
- `examples/langchain-v1/test_react_pattern.py`: 19 tests extract and execute the actual page fences, covering prohibited calculator input, valid arithmetic, native tool calling, model-call limits, well-formed histories, and middleware success/error tracing.
- `docs/implementations/tool-calling-agent.md`: installation now includes `langchain`, required by the preferred middleware example.
- Full offline suite: **144 passed**. Node/content/type/build verification and remaining limitations are consolidated in `reports/update-pass.md`; all earlier suite counts are intermediate results.
- The two native-tool examples never execute model-supplied Python. Validation rejection runs no tools from the rejected batch, and limit exits close outstanding tool-call IDs before returning the final AI message. The custom tool-calling topology retains its explicit validation/audit nodes; ordinary ReAct loop policy is middleware-based.
