---
sidebar_position: 8
title: "Framework Comparison"
last_verified: 2026-10-12
---

import DiagramEmbed from '@site/src/components/DiagramEmbed';

# Framework Comparison

**Official documentation checked: 2026-10-12.** Compare execution models and operational requirements, not unsupported numerical scores for community size or “production readiness.” The recommendations below are engineering judgments, not benchmark results. Provider support and feature parity depend on the language, adapter, model, and version you deploy.

## Current Options

| Option | Core abstraction | Good starting point when… | Key trade-off / responsibility |
|--------|------------------|---------------------------|--------------------------------|
| [LangChain](https://docs.langchain.com/oss/python/langchain/overview) | High-level agents and integrations; current agents use LangGraph underneath | You need a standard tool-using agent and broad model/data integrations | Higher-level convenience still requires understanding the underlying runtime and adapter behavior |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | Stateful graphs with explicit nodes and edges | You need branching, cycles, durable execution, checkpointing, or human intervention | You design state, routing, persistence, and safe replay; it can be used without LangChain |
| [CrewAI](https://docs.crewai.com/en/introduction) | Role/task-based Crews plus event-driven Flows | Work naturally decomposes into specialist roles, or you want Flows to coordinate deterministic and agentic steps | Crews and Flows are different abstractions; termination, state, and reliability still need design |
| [Microsoft Agent Framework](./microsoft-agent-framework.md) | Agents plus functional and graph-based workflows | You want Microsoft's successor to AutoGen/Semantic Kernel, with explicit orchestration and enterprise integrations | Verify language/provider parity and distinguish session memory from workflow checkpoints |
| [LlamaIndex](./llamaindex-agents.md) | Workflow-based agents and data/query-engine tools | Retrieval over structured or unstructured enterprise data is central | Retrieval quality, source access, ingestion, and tool descriptions dominate correctness |
| [OpenAI Agents SDK](./openai-responses-and-agents-sdk.md) | Agents, tools, handoffs, guardrails, sessions, tracing | You want a small application-side orchestration layer, especially around Responses | SDK orchestration and OpenAI hosted APIs are separate layers; provider portability is adapter-dependent |
| [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) | The agent loop and tools powering Claude Code, exposed through Python/TypeScript SDKs | You need a Claude-powered agent that can work with files, commands, and development workflows | Permissions, subprocess/runtime setup, filesystem scope, and sandboxing are central design concerns |
| [Google ADK](https://google.github.io/adk-docs/) | LLM agents, tools, sessions, and workflow agents | You want Google's agent ecosystem or sequential/parallel/loop orchestration | ADK is designed to be model- and deployment-agnostic, but capabilities vary by integration and runtime |
| [PydanticAI](https://ai.pydantic.dev/) | Typed Python agents, dependencies, tools, and validated structured output | Python type safety, dependency injection, and testable structured results matter | Schema validation is not factual validation; durable execution needs the documented integrations |

### LangChain and LangGraph Are Complementary

Use LangChain's high-level agent API for a standard agent loop. Use LangGraph directly when execution topology and state transitions need explicit control. It is misleading to compare them as unrelated competitors or describe current LangChain only as LCEL chains.

### Crews Are Not the Whole of CrewAI

Crews express role-based collaboration; Flows provide event-driven control, state management, and routing. The historical claim that CrewAI has no branching or cycles should not drive a current framework choice.

### A Provider SDK Is Not a Hosted Agent Service

OpenAI's Responses/Conversations APIs and its Agents SDK have different responsibilities. Likewise, Claude Agent SDK is more than an HTTP client for the Messages API: it exposes a runtime with tools and an agent loop. Ask where code executes, where state lives, and which tools can access the host.

## Decision Guide

| Primary requirement | Evaluate first | Questions to resolve |
|---------------------|----------------|----------------------|
| Standard tool-using agent with many integrations | LangChain; PydanticAI for a typed Python approach | Do you need dynamic model selection, structured output, or explicit dependency injection? |
| Explicit state transitions, pause/resume, review gates | LangGraph; Microsoft Agent Framework | What is checkpointed? How are side effects protected during replay? |
| Role-based collaborative work | CrewAI; Microsoft Agent Framework orchestration patterns | Who owns routing, stop conditions, and review? Would a deterministic workflow be simpler? |
| Retrieval-heavy agentic applications | LlamaIndex, with retrieval tooling from other stacks where needed | How are source permissions, citations, freshness, and retrieval quality evaluated? |
| Responses tools plus lightweight orchestration | OpenAI Agents SDK | Which tools are hosted versus local? Which memory strategy will you use? |
| Filesystem/command-oriented Claude agents | Claude Agent SDK | What are the permission policy, sandbox, allowed directories, and audit trail? |
| Google ecosystem and workflow agents | Google ADK | Which model/runtime integrations support the features your application needs? |
| Typed outputs and Python application integration | PydanticAI | How will dependencies, retries, external tool effects, and validation failures be tested? |

Do not choose a multi-agent design solely because a framework supports it. Start with a single agent or deterministic pipeline, measure failure modes, and add delegation only when it provides a demonstrated benefit.

## Operational Comparison Checklist

For every candidate, verify these against the **specific version and language** you will deploy:

- **State**: conversation history, shared workflow state, and durable checkpoints are different things. Identify storage, tenant isolation, and retention.
- **Human-in-the-loop**: distinguish a prompt asking for confirmation from an actual suspended execution with authenticated approval and resume.
- **Tools**: check schema support, provider compatibility, timeouts, least privilege, and idempotency for external writes.
- **Observability**: confirm model/tool/workflow tracing, correlation, exporter configuration, and sensitive-data redaction. Do not assume a named tracing integration is enabled by default.
- **Durability**: simulate a crash, replay, expired credentials, and duplicate tool calls. No framework makes arbitrary side effects exactly-once automatically.
- **Evaluation**: compare representative tasks, retrieval grounding, tool success, latency, and measured usage. This page does not supply model prices or performance rankings.
- **Portability**: “provider agnostic” is a design goal, not proof that every hosted tool or structured-output feature works on every model.

## Legacy / Superseded Options

<DiagramEmbed src="/diagrams/framework-migration.html" title="Framework migration paths">
  Read each lane as an independent migration, not a chain of replacements. Dashed branches
  distinguish optional application orchestration from the primary replacement API.
  These are conceptual paths: stored state, tool contracts, and regression tests still need migration.
</DiagramEmbed>

| Historical option | Verified status on 2026-10-12 | Current direction / historical reference |
|-------------------|------------------------------|------------------------------------------|
| OpenAI Assistants API | Officially sunset August 26, 2026; no longer available | [Responses, Conversations, and Agents SDK migration](./openai-responses-and-agents-sdk.md) |
| Microsoft AutoGen | Repository states maintenance mode; new development is directed to Microsoft Agent Framework | [Historical AutoGen guide](./autogen-guide.md); use the official migration guide, not a mechanical import rename |
| Microsoft Semantic Kernel | Repository identifies Microsoft Agent Framework as its enterprise-ready successor | [Historical Semantic Kernel guide](./semantic-kernel.md); this does not establish an SDK shutdown date |

The old AutoGen guide uses `ConversableAgent` / `UserProxyAgent`-era examples. Those are not a guide to the newer Microsoft AutoGen AgentChat API, Microsoft Agent Framework, or the separate AG2 project. Preserve that distinction when maintaining existing applications.

## Interview Talking Points

1. Explain the difference between a high-level agent API, a graph runtime, and a hosted model/tool API.
2. Choose a framework for a constrained use case and describe the trade-off, not an unmeasured ranking.
3. Explain how session memory differs from checkpoints and how replay affects external writes.
4. Compare handoff, agent-as-tool, role-based collaboration, and fixed workflow routing.
5. Describe why typed output, guardrails, and approval flows do not replace authorization and evaluation.
6. Outline a migration from a superseded framework, including stored state and regression tests.

## Official Sources

Checked **2026-10-12**: [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview), [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [CrewAI introduction](https://docs.crewai.com/en/introduction), [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/), [LlamaIndex agents](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/), [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/), [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview), [Google ADK](https://google.github.io/adk-docs/), [PydanticAI](https://ai.pydantic.dev/), [AutoGen repository](https://github.com/microsoft/autogen), [Semantic Kernel repository](https://github.com/microsoft/semantic-kernel), and [Assistants migration](https://developers.openai.com/api/docs/assistants/migration).
