# Framework Migration Diagram Report

Date: 2026-10-12. Skill: archify, type `architecture` (parallel migration lanes, no single path), `quality_profile: showcase`, `animation: none`.

## Artifacts
| Path | SHA-256 |
|------|---------|
| `diagrams/framework-migration.json` (spec, 3535 bytes) | `13a0568e61354140cab56fab2bb457855e9e7ccf5bd562373c8c93eb9fa806ce` |
| `static/diagrams/framework-migration.html` (809961 bytes) | `54d44e41fe188532f6b176dc370b8024b8049c43aed523a47a2d0ca81183204e` |

## Content (10 nodes, 6 edges, two groups)
- Legacy / superseded (top): Assistants API; AutoGen / Semantic Kernel; `create_react_agent`; `OpenAIAgent / ReActAgent` (sublabel: legacy `OpenAIAgent`; `ReActAgent.from_tools`).
- Current (below): Responses + Conversations (optional OpenAI Agents SDK); Microsoft Agent Framework (agents + graph workflows, checkpoints, HITL); LangChain `create_agent` + middleware (dashed branch to LangGraph `StateGraph` for custom orchestration); AgentWorkflow (FunctionAgent / ReActAgent / CodeActAgent).

## Source refs (facts)
- `reports/batch-1-frameworks.md`: migrations, AutoGen maintenance mode, MAF successor, LlamaIndex mapping, "no SK end-of-support date".
- `docs/frameworks/framework-comparison.md`: Legacy/Superseded table, Assistants sunset, MAF as successor.
- `docs/frameworks/openai-responses-and-agents-sdk.md`: assistant/thread/run mapping.
- `docs/frameworks/microsoft-agent-framework.md`, `autogen-guide.md`: workflows, checkpoints, HITL.
- `docs/frameworks/langchain-overview.md`, `docs/design-patterns/react-pattern.md`, `docs/implementations/basic-react-agent.md`: `create_agent` replaces `langgraph.prebuilt.create_react_agent`; `StateGraph` for custom topologies.
- `docs/frameworks/llamaindex-agents.md` (line 12, 69): older material used `OpenAIAgent` and `ReActAgent.from_tools`; current docs use `FunctionAgent`, `ReActAgent`, `CodeActAgent`, `AgentWorkflow`.

Per-node `sources` fields were not embedded: Archify requires a 40-hex pinned `meta.repository` revision, and the working tree is dirty (sources uncommitted), so a pin would be inaccurate.

## Revision note
Semantic correction (new authored revision, not polish): the legacy LlamaIndex node was labelled `OpenAIAgent.from_tools`, which implied a single API. The two legacy APIs per the docs are `OpenAIAgent` and `ReActAgent.from_tools`; the node now says so. `ReActAgent` also exists in the current AgentWorkflow node (as the current constructor), so the legacy sublabel names `from_tools` explicitly to avoid confusion. The node's sublabel renders small (min projected text 7.6px at 1440×900, above the 6px threshold).

## Claims deliberately avoided
No deprecation dates beyond the existing docs. Semantic Kernel is not called obsolete; the node says only that a successor path (MAF) exists. The LlamaIndex mapping is "not found on current pages", not an official deprecation.

## Verification
- `validate architecture --quality showcase`: ok, 9/9 checks, 0 errors, 0 warnings.
- `deliver`: ok, 9/9 checks, 0 errors, 0 warnings; hashes above (spec 3535 B, artifact 809961 B).
- `visual-check` (receipt `reports/diagrams-browser/framework-migration.visual-check.json`, artifact sha matches above): status pass, automated browser evidence. Containment (no overflow, scroll size equals viewport) at 1440×900, 1600×1000, 1920×1080, 2048×1320, light theme; light and dark screenshots were captured at 1440×900 and 2048×1320. Perceptual review: **pending**; I had no image-capable review, so dark-theme appearance is not visually confirmed.
- Final browser capture evidence is retained under `reports/diagrams-browser/framework-migration.visual-check.{json,html}` with all four light/dark PNGs. The JSON records the original artifact path; sibling screenshot filenames resolve from the moved HTML report. Perceptual review remains unperformed.
- Geometry control used: `labelDy` on the 6 edges.
- Limitation: LlamaIndex `ReActAgent` constructor and other snippets remain unverified, per batch 1; the legacy label means "not found on current pages", not an official deprecation.
