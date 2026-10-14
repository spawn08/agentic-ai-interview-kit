"""Offline smoke test for docs/frameworks/microsoft-agent-framework.md (agent-framework-core only).

Runs the page's executor/workflow, FileCheckpointStorage and request_info/response_handler
patterns with no model provider. The page's agent snippet needs a provider client and is only
import-checked. Observability is checked by calling configure_otel_providers() with no exporters.
"""
import asyncio
from dataclasses import dataclass

from agent_framework import (
    Agent,
    Executor,
    FileCheckpointStorage,
    InMemoryCheckpointStorage,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)


class UpperCase(Executor):
    @handler
    async def to_upper(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text.upper())


class Emit(Executor):
    @handler
    async def emit(self, text: str, ctx: WorkflowContext[None, str]) -> None:
        await ctx.yield_output(text)


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
    async def on_decision(self, original: ApprovalRequest, approved: bool, ctx: WorkflowContext[str, str]) -> None:
        await ctx.yield_output(original.summary if approved else "rejected")


def test_workflow_with_file_checkpoints(tmp_path):
    async def go():
        upper, emit = UpperCase(id="upper"), Emit(id="emit")
        storage = FileCheckpointStorage(str(tmp_path))
        workflow = (
            WorkflowBuilder(start_executor=upper, checkpoint_storage=storage)
            .add_edge(upper, emit)
            .build()
        )
        outputs = [e.data async for e in workflow.run("hello", stream=True) if e.type == "output"]
        checkpoints = await storage.list_checkpoints(workflow_name=workflow.name)
        assert outputs == ["HELLO"]
        assert checkpoints and checkpoints[0].checkpoint_id
        # Resume from a checkpoint on a freshly built workflow with the same topology and IDs.
        new_upper = UpperCase(id="upper")
        rebuilt = (
            WorkflowBuilder(start_executor=new_upper, checkpoint_storage=storage)
            .add_edge(new_upper, Emit(id="emit"))
            .build()
        )
        resumed = [e async for e in rebuilt.run(checkpoint_id=checkpoints[-1].checkpoint_id, stream=True)]
        assert resumed

    asyncio.run(go())


def test_request_info_and_response():
    async def go():
        workflow = WorkflowBuilder(start_executor=Gate(), checkpoint_storage=InMemoryCheckpointStorage()).build()
        requests = [e async for e in workflow.run("deploy", stream=True) if e.type == "request_info"]
        assert len(requests) == 1 and requests[0].data == ApprovalRequest(summary="deploy")
        outputs = [
            e.data
            async for e in workflow.run(stream=True, responses={requests[0].request_id: True})
            if e.type == "output"
        ]
        assert outputs == ["deploy"]

    asyncio.run(go())


def test_observability_configures_without_exporters(monkeypatch):
    for name in ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    from agent_framework.observability import configure_otel_providers

    configure_otel_providers()


def test_agent_class_importable():
    assert "client" in Agent.__init__.__annotations__
