# Batch 1 – Tier 1 Framework Docs Report

Date of verification: 2026-10-12. No commits made. The initial subtask did not edit navigation/configuration; the completed update now wires both successor pages, the Legacy sidebar group, and the Assistants redirect in `sidebars.ts` and `docusaurus.config.ts`.

**Final-state amendment:** the initial illustrative-only and build-failure notes below describe the first handoff, not the completed working tree. The isolated-framework verification section supersedes the import/offline-execution limitations; live vendor calls and full applications remain unverified. Navigation was repaired and subsequent repository builds passed. No PR or commit was created.

## Files and reasons

| File | Change | Reason |
|------|--------|--------|
| `docs/frameworks/openai-assistants-api.md` | **Deleted** (replaced) | Assistants API sunset (Aug 26, 2026 per OpenAI migration guide) |
| `docs/frameworks/openai-responses-and-agents-sdk.md` | New (written earlier in this batch; reviewed, not re-edited) | Responses, Conversations, Agents SDK, migration table/checklist, `AGENT_MODEL` |
| `docs/frameworks/framework-comparison.md` | Rewritten | Current frameworks incl. Claude Agent SDK, Google ADK, PydanticAI, MAF; Legacy/Superseded table; no invented scores |
| `docs/frameworks/microsoft-agent-framework.md` | New | Agents, workflows/executors, checkpointing, HITL, OTel, migration notes |
| `docs/frameworks/llamaindex-agents.md` | Edited | FunctionAgent/ReActAgent/CodeActAgent/AgentWorkflow; removed `OpenAIAgent.from_tools`, hard-coded model IDs; kept query-engine/RAG/interview sections |
| `docs/frameworks/autogen-guide.md` | Warning + `<details>` Legacy | Maintenance mode; successor MAF |
| `docs/frameworks/semantic-kernel.md` | Warning + `<details>` Legacy | MAF named successor |

Not mine: `docs/core-concepts/model-context-protocol.md` was already modified in the working tree; I did not touch it.

## Sources (fetched with curl, 2026-10-12)
- MAF: learn.microsoft.com/en-us/agent-framework/{overview/, workflows/, workflows/executors, workflows/checkpoints, workflows/human-in-the-loop, workflows/observability, user-guide/agents/agent-observability, migration-guide/from-autogen/, migration-guide/from-semantic-kernel/}
- raw.githubusercontent.com/microsoft/autogen/main/README.md (maintenance-mode caution)
- raw.githubusercontent.com/microsoft/semantic-kernel/main/README.md (MAF successor, v1.0 statement)
- LlamaIndex: developers.llamaindex.ai/python/framework/{module_guides/deploying/agents/, understanding/agent/, .../multi_agent/, .../state/, .../human_in_the_loop/}, examples/agent/code_act_agent/, and `llama_index/core/agent/workflow/__init__.py` on GitHub (exports)
- OpenAI / framework-comparison sources are listed in those pages' "Official Sources" sections (verified in the earlier pass of this batch).

## Migrations (before → after)
- Assistants API → Responses + Conversations (+ optional Agents SDK): assistant→prompt/config, thread→conversation, message→item, run→response, run step→item.
- LlamaIndex `OpenAIAgent.from_tools(...).chat()` / `ReActAgent.from_tools` → `FunctionAgent(...)`/`ReActAgent(...)` + `await agent.run(...)`; Agent Runner/Worker vocabulary → AgentWorkflow; hard-coded `gpt-4o`/`claude-…` → `AGENT_MODEL`.
- AutoGen / Semantic Kernel pages: content preserved inside `<details>` with Superseded warnings; added "Current Interview Framing" sections.

## Unverified / limitations
- All code is illustrative and untested; none executed.
- No AutoGen maintenance-mode date and no Semantic Kernel end-of-support date appeared in sources; none claimed.
- MAF: exact orchestration builder names, how pending HITL requests restore after restart, and `enable_sensitive_data` semantics beyond `configure_otel_providers(..., enable_sensitive_data=True)` shown in the docs were not exercised. `make_client()` in the MAF agent snippet is a placeholder.
- LlamaIndex: `ReActAgent` constructor args, and retained `QueryEngineTool`/`SubQuestionQueryEngine`/Router snippets, not re-verified; claim that `OpenAIAgent.from_tools` is absent from current pages means "not found on pages fetched," not an official deprecation notice.
- Pages for Claude Agent SDK, Google ADK, PydanticAI are linked in framework-comparison but their feature claims are high-level.

## Build result
- `npm run build` in the repo: **FAILED**. `sidebars.ts` still references `frameworks/openai-assistants-api` (deleted) and does not list `microsoft-agent-framework` / `openai-responses-and-agents-sdk`. Parent must update `sidebars.ts` (replace the old id; add the two new ids).
- Required `npm ci` first (node_modules was absent).
- Content check: copy of the repo in /tmp with only sidebars patched built successfully (`[SUCCESS] Generated static files`), so the docs themselves compile; no broken-link warnings were reported.

## Tier 1 verification against installed latest (2026-10-12)

Fresh uv venvs, Python 3.12.10, macOS arm64, installed from `examples/tier1/requirements-<framework>.txt` (unpinned).
Every import-check ran `python examples/langchain-v1/check_doc_imports.py <page>` and reported `done, 0 failure(s)`;
every `pytest examples/tier1/<framework>` passed (openai 2, microsoft 4, llamaindex 4, crewai 4).

| Env | Resolved versions | Official sources checked (2026-10-12, HTTP 200) |
|---|---|---|
| openai | openai 3.29.0, openai-agents 0.23.1, pydantic 2.14.1 | https://developers.openai.com/api/docs/guides/conversation-state, https://openai.github.io/openai-agents-python/ |
| microsoft | agent-framework-core 1.21.0, opentelemetry-sdk 1.45.1, opentelemetry-exporter-otlp-proto-grpc 1.45.1 | https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints |
| llamaindex | llama-index-core 0.14.25, llama-index-llms-openai 0.8.2, llama-index-embeddings-openai 0.7.0, llama-index-workflows 2.26.0, openai 2.54.0 | https://developers.llamaindex.ai/python/framework/understanding/agent/ |
| crewai | crewai 1.15.27, crewai-tools 1.15.27, langgraph 1.2.14, langchain-openai 1.7.0, openai 2.54.0, pydantic 2.12.5 | https://docs.crewai.com/concepts/crews, /concepts/processes, /concepts/llms |

Stale APIs found and fixed:
- **llamaindex-agents.md**: `llama_index.question_gen.openai.OpenAIQuestionGenerator` is in `llama-index-question-gen-openai`,
  whose newest release (0.3.1) forces `llama-index-core<0.13`; installing it downgraded core 0.14.25 -> 0.12.52 (this is
  the resolver backtracking trap). Replaced with core's `LLMQuestionGenerator` (verified: builds `SubQuestionQueryEngine`).
  Package removed from requirements.
- **crewai-guide.md**: `Crew(manager_llm=ChatOpenAI(...))` is rejected by crewai 1.15.27 (validation error); now `crewai.LLM`.
  "consensual" process removed: the installed `Process` enum has only `sequential` and `hierarchical`, and the official
  Processes page lists only those.
- **microsoft-agent-framework.md**: install guidance now `agent-framework-core` (umbrella `agent-framework` is the huge
  all-providers meta-package); observability note records that `opentelemetry-sdk` (and the OTLP gRPC exporter when
  `OTEL_EXPORTER_OTLP_*` is set) are NOT installed by core (verified failures without them).
- Every Python fence in the four pages now carries an "Illustrative, untested" comment unless it already had one.

Behaviour exercised offline (not just imports): Responses `conversations.create`/`responses.create` and `@function_tool` +
`Runner.run` against a local fake HTTP server; MSAF `WorkflowBuilder` + `FileCheckpointStorage`, `request_info`/
`response_handler`, checkpoint resume, `configure_otel_providers()`; LlamaIndex index/QueryEngineTool/SubQuestionQueryEngine/
ReActAgent with a scripted LLM; CrewAI Agent/Task/Crew construction (sequential, hierarchical, memory+embedder).
Not verified: the MSAF top-level-`await` checkpoint snippet is only `ast`-parsed by the checker (as intended); `agent.run`
with a real Microsoft provider client, `FunctionAgent`/`CodeActAgent` execution, `crew.kickoff()` and any live model call.
Network was available; no limits hit. Pre-existing conflict confirmed: `llama-index-question-gen-openai` vs core >= 0.13.
