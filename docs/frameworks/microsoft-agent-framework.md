---
sidebar_position: 9
title: "Microsoft Agent Framework"
last_verified: 2026-10-12
---

# Microsoft Agent Framework

**Verified against official documentation: 2026-10-12** ([overview](https://learn.microsoft.com/en-us/agent-framework/overview/), [workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/)). Microsoft Agent Framework (MAF) is the documented successor path for both [AutoGen](./autogen-guide.md) and [Semantic Kernel](./semantic-kernel.md). Its overview describes it as combining AutoGen's simple single- and multi-agent abstractions with Semantic Kernel's enterprise features such as session-based state, type safety, middleware, and telemetry, plus graph-based workflows.

Language coverage differs. The overview documents .NET and Python, and a **public-preview** Go SDK that lacks some features (declarative agents, RAG, CodeAct, functional workflows). Verify any feature against the language and package version you deploy. This page's code is Python and **illustrative and untested**.

## Core Concepts

| Concept | What it is | Interview point |
|---------|-----------|-----------------|
| Agent | An LLM-backed component that processes input, calls tools and MCP servers, and responds | Open-ended, conversational work with autonomous tool use |
| Agent session | State for multi-turn conversations | Not the same as a workflow checkpoint |
| Workflow | Functional or graph-based execution connecting agents and functions through explicit paths | Use when steps are well defined and you need control over execution order |
| Executor | A workflow node; in Python a class with `@handler` methods or a function decorated with `@executor` | Typed inputs/outputs define legal edges |
| Checkpoint | A saved workflow state you can resume or rehydrate from | Durability for the workflow, not for arbitrary side effects |
| Request/response | An executor asks for external input (`request_info`) and the workflow pauses | The basis of human-in-the-loop (HITL) |
| Orchestrations | Sequential, concurrent, handoff, group-chat, and Magentic patterns | Compare with fixed workflow routing |

The overview's guidance: choose an **agent** for open-ended tasks needing autonomous tool use and planning; choose a **workflow** when the process has well-defined steps and you need explicit control over execution order.

## Agents

Install `pip install agent-framework-core` for the `agent_framework` API used on this page (`pip install agent-framework` pulls in the full meta-package with every provider integration; install only the provider package you use). Model providers listed in the overview include Microsoft Foundry, Anthropic, Azure OpenAI, OpenAI, and Ollama. Client classes, constructor parameters, and credentials are provider-specific; check the provider page for the one you use. The overview itself imports `Agent` from `agent_framework` and a client such as `FoundryChatClient`.

```python
import os
from agent_framework import Agent

# Illustrative, untested. `make_client()` is a placeholder for the provider
# client construction documented for your provider; it should read the model
# name from the AGENT_MODEL environment variable rather than hard-coding one.
model = os.environ["AGENT_MODEL"]
client = make_client(model=model)  # hypothetical helper, not a framework API

agent = Agent(
    client=client,
    name="StudyTutor",
    instructions="Explain concepts briefly and state uncertainty.",
)

async def main():
    result = await agent.run("What is a workflow checkpoint?")
    print(result)
```

The framework does not load `.env` files automatically; call `load_dotenv()` yourself or set the environment.

## Workflows and Executors

A Python executor handles typed messages through `@handler`. `WorkflowContext[T_out, T_workflow_output]` types what the executor can send to downstream nodes and what it can yield as workflow output.

```python
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

# Illustrative, untested.
class UpperCase(Executor):
    @handler
    async def to_upper(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text.upper())

class Emit(Executor):
    @handler
    async def emit(self, text: str, ctx: WorkflowContext[None, str]) -> None:
        await ctx.yield_output(text)

upper, emit = UpperCase(id="upper"), Emit(id="emit")
workflow = WorkflowBuilder(start_executor=upper).add_edge(upper, emit).build()
# async for event in workflow.run("hello", stream=True): ...
```

Agents can participate in workflows as executors, and orchestration builders cover the sequential, concurrent, handoff, group-chat, and Magentic patterns. Consult the official orchestration pages before relying on exact builder names.

## Checkpointing

Per the [checkpoint documentation](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints), pass a `CheckpointStorage` when building the workflow. Three Python implementations ship: `InMemoryCheckpointStorage` (tests/demos), `FileCheckpointStorage` (single machine, survives restarts), and `CosmosCheckpointStorage` (Azure Cosmos DB; separate `agent_framework_azure_cosmos` package, for distributed production use). They share a protocol, so storage can be swapped without changing executors.

```python
from agent_framework import FileCheckpointStorage, WorkflowBuilder

# Illustrative, untested; path is an example.
storage = FileCheckpointStorage("/var/lib/agent-framework/checkpoints")
workflow = WorkflowBuilder(start_executor=start_executor, checkpoint_storage=storage).build()

async for event in workflow.run(input, stream=True):
    ...
checkpoints = await storage.list_checkpoints(workflow_name=workflow.name)

# Resume later (the docs also show rehydrating a freshly built workflow):
saved = checkpoints[5]
async for event in workflow.run(checkpoint_id=saved.checkpoint_id, stream=True):
    ...
```

Operational cautions from the docs and general practice:

- A rehydrated workflow must preserve the **topology and executor identities** of the one that wrote the checkpoint. Change an executor ID or rebuild agents with unstable IDs and resume can fail.
- The docs include a security section on restricting deserialized types (`allowed_checkpoint_types`). Treat checkpoint storage as trusted-write only and read that section before using file or shared storage.
- Resuming re-enters work after the checkpoint; external side effects need idempotency keys. A checkpoint does not make a write exactly-once.

## Human-in-the-Loop

An executor calls `ctx.request_info(...)` with the request data and the expected response type; the workflow emits a `request_info` event and waits. A `@response_handler` method receives the original request and the response ([HITL docs](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)).

```python
from dataclasses import dataclass
from agent_framework import Executor, WorkflowContext, handler, response_handler

# Illustrative, untested.
@dataclass
class ApprovalRequest:
    summary: str

class Gate(Executor):
    def __init__(self):
        super().__init__(id="gate")

    @handler
    async def start(self, proposal: str, ctx: WorkflowContext[str, str]) -> None:
        await ctx.request_info(request_data=ApprovalRequest(summary=proposal), response_type=bool)

    @response_handler
    async def on_decision(self, original: ApprovalRequest, approved: bool,
                          ctx: WorkflowContext[str, str]) -> None:
        if approved:
            await ctx.send_message(original.summary)
        else:
            await ctx.yield_output("rejected")

# Driver loop pattern from the docs:
# stream = workflow.run(proposal, stream=True)
# collect events where event.type == "request_info" -> (event.request_id, event.data)
# resume with workflow.run(stream=True, responses={request_id: decision})
```

Production HITL still needs authenticated approvers, request expiry, and an audit record. Combine request/response with checkpoints if the human may respond after a process restart; confirm in the docs how pending requests are restored for your version.

## Observability (OpenTelemetry)

Workflows emit spans beyond standard GenAI telemetry. Documented span names include `workflow.build`, `workflow.session`, `workflow_invoke`, `executor.process {executor_id}`, `edge_group.process`, and `message.send`; edge-group spans carry delivery-status attributes, and cross-executor causality uses span links rather than parent/child nesting.

In Python, instrumentation is activated with `enable_instrumentation()`, and `configure_otel_providers()` (from `agent_framework.observability`) sets up exporters, reading standard `OTEL_EXPORTER_OTLP_*` environment variables. It needs `opentelemetry-sdk`, plus `opentelemetry-exporter-otlp-proto-grpc` when an OTLP endpoint is configured; `agent-framework-core` does not install them (verified: it raises `ModuleNotFoundError`/`ImportError` otherwise). **Sensitive data** (raw inputs, outputs, message content) is off by default and must be enabled explicitly (for example `enable_sensitive_data=True`); the docs warn to do this only in protected environments.

```python
from agent_framework.observability import configure_otel_providers

# Illustrative, untested. Reads OTEL_EXPORTER_OTLP_* environment variables.
configure_otel_providers()
```

## Migration Notes

Official guides: [from AutoGen](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/) and [from Semantic Kernel](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-semantic-kernel/).

| From | Typical mapping (conceptual) | Re-verify |
|------|-------------------------------|-----------|
| AutoGen conversational group chats | Orchestration patterns, or explicit workflows where control is needed | Termination, speaker selection, and tests |
| Semantic Kernel plugins/functions | Agent tools | Schemas, auth, side effects |
| SK memory/filters | Sessions/context providers and middleware | Retention and data scope |

## Interview Talking Points

1. When is a workflow better than an autonomous agent? (Defined steps, ordering control, audit, resumability.)
2. Distinguish agent-session memory from workflow checkpoints.
3. What must stay stable for a checkpoint to be resumable? (Topology and executor IDs.)
4. How does `request_info` differ from asking "are you sure?" in a prompt? (Real suspension plus authenticated resume.)
5. What would you trace, and what must you redact?
6. How would you migrate an AutoGen group chat, and how would you prove behavior parity?

## Official Sources

Checked 2026-10-12: [overview](https://learn.microsoft.com/en-us/agent-framework/overview/), [workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/), [executors](https://learn.microsoft.com/en-us/agent-framework/workflows/executors), [checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints), [human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop), [workflow observability](https://learn.microsoft.com/en-us/agent-framework/workflows/observability), [agent observability](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-observability).
