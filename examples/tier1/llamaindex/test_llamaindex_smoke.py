"""Offline smoke test for docs/frameworks/llamaindex-agents.md (llama-index-core, no network).

A scripted CustomLLM and MockEmbedding stand in for the provider, so this runs the page's
VectorStoreIndex -> QueryEngineTool, SubQuestionQueryEngine(LLMQuestionGenerator) and ReActAgent
paths against the INSTALLED llama-index-core. FunctionAgent/CodeActAgent/AgentWorkflow are only
constructed or import-checked (they need a tool-calling provider).
"""
import asyncio
from typing import Any

import pytest
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.agent.workflow import AgentWorkflow, FunctionAgent, ReActAgent
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.llms import CompletionResponse, CustomLLM, LLMMetadata
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.core.question_gen import LLMQuestionGenerator
from llama_index.core.tools import FunctionTool, QueryEngineTool, ToolMetadata

REPLY = "Thought: I can answer without using any more tools.\nAnswer: scripted answer"


class ScriptedLLM(CustomLLM):
    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(model_name="scripted")

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        return CompletionResponse(text=REPLY)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs: Any):
        yield CompletionResponse(text=REPLY, delta=REPLY)


@pytest.fixture()
def tool():
    old_llm, old_embed = Settings._llm, Settings._embed_model
    Settings.llm = ScriptedLLM()
    Settings.embed_model = MockEmbedding(embed_dim=8)
    index = VectorStoreIndex.from_documents([Document(text="Revenue was 10.")])
    yield QueryEngineTool(
        query_engine=index.as_query_engine(similarity_top_k=1),
        metadata=ToolMetadata(name="financial_reports", description="Financial results."),
    )
    Settings._llm, Settings._embed_model = old_llm, old_embed


def test_query_engine_tool(tool):
    assert tool.metadata.name == "financial_reports"
    assert str(tool.query_engine.query("revenue")).strip()


def test_sub_question_engine_builds_with_core_generator(tool):
    engine = SubQuestionQueryEngine.from_defaults(
        query_engine_tools=[tool], question_gen=LLMQuestionGenerator.from_defaults(), use_async=True
    )
    assert isinstance(engine, SubQuestionQueryEngine)


def test_react_agent_runs(tool):
    agent = ReActAgent(tools=[tool], llm=Settings.llm)

    async def go():  # agent.run() must be called inside a running loop (as in the page's main())
        return await asyncio.wait_for(agent.run("hello"), timeout=60)

    result = asyncio.run(go())
    assert "scripted answer" in str(result)


def test_function_tool_and_workflow_classes(tool):
    def record_notes(note: str) -> str:
        """Record a note."""
        return note

    assert FunctionTool.from_defaults(fn=record_notes).metadata.name == "record_notes"
    assert callable(FunctionAgent) and callable(AgentWorkflow)
