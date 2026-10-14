"""Offline tests for the ReAct page: python fences are extracted from the doc and exec'd.

No network, no secrets: a scripted fake chat model replaces provider models.
Run: pytest examples/langchain-v1/test_react_pattern.py
"""
import json
import logging
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

from check_doc_imports import python_blocks

PAGE = Path(__file__).resolve().parents[2] / "docs/design-patterns/react-pattern.md"
BLOCKS = {}
for _line, _code in python_blocks(PAGE.read_text(encoding="utf-8")):
    for _marker in ("ReAct-style agent using", "Customizing the prebuilt ReAct loop"):
        if _code.lstrip().startswith(f'"""{_marker}'):
            BLOCKS[_marker] = _code


class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def _model(messages):
    return FakeToolModel(messages=iter(messages))


def _call(name, args, call_id):
    return {"id": call_id, "name": name, "args": args, "type": "tool_call"}


def _load(marker):
    ns = {"__name__": "react_doc"}
    exec(compile(BLOCKS[marker], f"react-pattern.md:{marker}", "exec"), ns)
    return ns


@pytest.fixture
def primary():
    return _load("ReAct-style agent using")


@pytest.fixture
def custom():
    return _load("Customizing the prebuilt ReAct loop")


def _ask(agent, text="q", thread="t"):
    cfg = {"configurable": {"thread_id": thread}}
    return agent.invoke({"messages": [{"role": "user", "content": text}]}, config=cfg)


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo pwned')",
        "(1).__class__",
        "abs(-1)",
        "2 ** 3",
        "True + 1",
        "x + 1",
        "1e400",
        "999999999999 * 999999999999",
        "1 / 0",
        "1 +",
        "9" * 300,
        "-" * 60 + "1",
    ],
)
def test_calculator_rejects_exploits(primary, expr):
    out = json.loads(primary["calculator"].func(expr))
    assert "error" in out and "result" not in out


def test_calculator_valid_and_no_eval(primary):
    import ast

    assert json.loads(primary["calculator"].func("-(2 + 3) * 4 / 8"))["result"] == -2.5
    calls = [n.func.id for n in ast.walk(ast.parse(BLOCKS["ReAct-style agent using"]))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "eval" not in calls and "exec" not in calls


def test_primary_agent_runs_native_loop_with_calculator_exploit_rejected(primary):
    model = _model([
        AIMessage(content="", tool_calls=[_call("calculator", {"expression": "__import__('os')"}, "c1")]),
        AIMessage(content="rejected"),
    ])
    out = _ask(primary["build_react_agent"](model))
    tool_msg = next(m for m in out["messages"] if isinstance(m, ToolMessage))
    assert "error" in json.loads(tool_msg.content)
    assert out["messages"][-1].content == "rejected"


def _assert_well_formed(messages):
    asked = {tc["id"] for m in messages if isinstance(m, AIMessage) for tc in m.tool_calls}
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    assert asked == answered


@pytest.mark.parametrize("which", ["primary", "custom"])
def test_run_limit_ends_loop_with_well_formed_messages(which, primary, custom):
    ns, builder, tool_name, args = (
        (primary, "build_react_agent", "search", {"query": "capital of japan"})
        if which == "primary"
        else (custom, "build_middleware_agent", "echo", {"text": "hi"})
    )
    limit = 10 if which == "primary" else 5
    looping = [
        AIMessage(content="", tool_calls=[_call(tool_name, args, f"x{i}")]) for i in range(limit + 3)
    ]
    out = _ask(ns[builder](_model(looping)))
    msgs = out["messages"]
    assert sum(bool(isinstance(m, AIMessage) and m.tool_calls) for m in msgs) == limit
    assert isinstance(msgs[-1], AIMessage) and not msgs[-1].tool_calls
    assert "limit" in msgs[-1].content.lower()
    _assert_well_formed(msgs[:-1])


def test_middleware_traces_success(custom, caplog):
    model = _model([
        AIMessage(content="", tool_calls=[_call("get_weather", {"city": "Paris"}, "w1")]),
        AIMessage(content="clear"),
    ])
    with caplog.at_level(logging.INFO):
        out = _ask(custom["build_middleware_agent"](model))
    assert "tool=get_weather status=success" in caplog.text
    assert "demo data" in next(m for m in out["messages"] if isinstance(m, ToolMessage)).content


def test_middleware_turns_tool_errors_into_error_messages(custom, caplog):
    model = _model([
        AIMessage(content="", tool_calls=[_call("echo", {"text": "hi"}, "e1")]),
        AIMessage(content="handled"),
    ])
    custom["echo"].func = lambda text: (_ for _ in ()).throw(RuntimeError("boom"))
    agent = custom["build_middleware_agent"](model)
    with caplog.at_level(logging.WARNING):
        out = _ask(agent)
    tool_msg = next(m for m in out["messages"] if isinstance(m, ToolMessage))
    assert tool_msg.status == "error" and "boom" in tool_msg.content
    assert "tool=echo status=error" in caplog.text
    assert out["messages"][-1].content == "handled"


def test_middleware_page_has_no_custom_graph_and_fences_import(custom):
    text = PAGE.read_text(encoding="utf-8")
    assert "## Customizing the Loop with Middleware" in text
    assert "## LangGraph Implementation: Custom Graph Nodes" not in text
    assert "StateGraph(" not in "".join(BLOCKS.values())
