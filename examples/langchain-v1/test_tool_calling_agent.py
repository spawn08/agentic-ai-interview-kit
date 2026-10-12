"""Offline tests for the tool-calling-agent page: modules are extracted from the doc and exec'd.

No network, no secrets: ChatOpenAI is replaced by a scripted fake and the page-local
modules (tools/state/nodes/graph) are installed in sys.modules only for the test.
Run: pytest examples/langchain-v1/test_tool_calling_agent.py
"""
import asyncio
import json
import sys
import types
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from check_doc_imports import python_blocks

PAGE = Path(__file__).resolve().parents[2] / "docs/implementations/tool-calling-agent.md"
SOURCES = {}
for _line, _code in python_blocks(PAGE.read_text(encoding="utf-8")):
    for _name in ("tools", "state", "nodes", "graph", "native_agent"):
        if _code.lstrip().startswith(f'"""{_name}.py'):
            SOURCES[_name] = _code


def _load(monkeypatch, name):
    mod = types.ModuleType(name)
    monkeypatch.setitem(sys.modules, name, mod)
    exec(compile(SOURCES[name], f"tool-calling-agent.md:{name}", "exec"), mod.__dict__)
    return mod


class ScriptedModel:
    """Stands in for ChatOpenAI(...).bind_tools(...): replays AIMessages and records inputs."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    async def ainvoke(self, messages):
        self.seen.append(list(messages))
        return self.script.pop(0)


class FakeChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def bind_tools(self, tools):
        return ScriptedModel([])


@pytest.fixture
def mods(monkeypatch):
    import langchain_openai

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setenv("AGENT_MODEL", "fake-model")
    loaded = {}
    for name in ("tools", "state", "nodes", "graph"):
        loaded[name] = _load(monkeypatch, name)
    return types.SimpleNamespace(**loaded)


def _call(name, args, call_id):
    return {"id": call_id, "name": name, "args": args, "type": "tool_call"}


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo pwned')",
        "(1).__class__",
        "().__class__.__bases__",
        "abs(-1)",
        "2 ** 3",
        "True + 1",
        "'a' * 3",
        "x + 1",
        "1e400",
        "10 ** 10 ** 10",
        "999999999999 * 999999999999",
        "1 / 0",
        "1 +",
        "9" * 300,
        "-" * 60 + "1",
        "1 < 2",
        "[1][0]",
    ],
)
def test_calculator_rejects_exploits_and_unsupported_syntax(mods, expr):
    out = json.loads(mods.tools.calculate.func(expr))
    assert "error" in out and "result" not in out


def test_calculator_basic_arithmetic(mods):
    out = json.loads(mods.tools.calculate.func("-(2 + 3) * 4 / 8"))
    assert out["result"] == -2.5
    assert json.loads(mods.tools.calculate.func("+7 - 2"))["result"] == 5


def test_calculator_does_not_use_eval(mods):
    import ast

    calls = [n.func.id for n in ast.walk(ast.parse(SOURCES["tools"])) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "eval" not in calls and "exec" not in calls


def _install_counting_tools(mods, monkeypatch):
    """Replace the tool node so we can prove whether any tool ran."""
    ran = []
    from langchain_core.tools import tool

    @tool
    def get_weather(location: str, unit: str = "celsius") -> str:
        """weather"""
        ran.append(location)
        return json.dumps({"location": location})

    @tool
    def create_ticket(customer_name: str, subject: str) -> str:
        """ticket"""
        ran.append("ticket")
        return "TKT"

    return ran, get_weather, create_ticket


def test_mixed_valid_and_invalid_batch_runs_no_tools_and_has_no_duplicates(mods, monkeypatch):
    ran = []
    real_weather = mods.tools.get_weather
    # Wrap the real tool func side effect: count executions via the ToolNode path.
    original = real_weather.func

    def spying(*a, **k):
        ran.append((a, k))
        return original(*a, **k)

    monkeypatch.setattr(real_weather, "func", spying)

    bad_batch = AIMessage(
        content="",
        tool_calls=[
            _call("get_weather", {"location": "Tokyo"}, "c1"),  # valid
            _call("create_ticket", {"customer_name": "Alice"}, "c2"),  # missing subject
            _call("delete_everything", {}, "c3"),  # unknown tool
        ],
    )
    model = ScriptedModel(
        [
            bad_batch,
            AIMessage(content="", tool_calls=[_call("get_weather", {"location": "Tokyo"}, "c4")]),
            AIMessage(content="Tokyo is sunny."),
        ]
    )
    mods.nodes._model = model
    app = mods.graph.build_tool_agent()
    cfg = {"configurable": {"thread_id": "t"}}
    result = asyncio.run(app.ainvoke({"messages": [HumanMessage(content="hi")]}, config=cfg))

    msgs = result["messages"]
    first_results = [m for m in msgs if isinstance(m, ToolMessage) and m.tool_call_id in {"c1", "c2", "c3"}]
    # Exactly one ToolMessage per original call, all errors, none executed.
    assert sorted(m.tool_call_id for m in first_results) == ["c1", "c2", "c3"]
    assert all(m.status == "error" for m in first_results)
    assert "Invalid arguments" in next(m for m in first_results if m.tool_call_id == "c2").content
    assert "Unknown tool" in next(m for m in first_results if m.tool_call_id == "c3").content
    assert "Not executed" in next(m for m in first_results if m.tool_call_id == "c1").content
    # After the rejection the corrected batch ran exactly once.
    assert len(ran) == 1 and ran[0][1].get("location") == "Tokyo"
    ids = [m.tool_call_id for m in msgs if isinstance(m, ToolMessage)]
    assert len(ids) == len(set(ids)) == 4
    assert msgs[-1].content == "Tokyo is sunny."


def test_validate_node_directly_all_or_nothing(mods):
    ok = AIMessage(content="", tool_calls=[_call("get_weather", {"location": "Tokyo"}, "a")])
    state = mods.state.ToolAgentState(messages=[ok])
    assert asyncio.run(mods.nodes.validate_tool_calls(state)) == {}
    assert mods.nodes.route_after_validate(state) == "tools"

    bad = AIMessage(content="", tool_calls=[_call("calculate", {"expression": "x" * 500}, "b")])
    out = asyncio.run(mods.nodes.validate_tool_calls(mods.state.ToolAgentState(messages=[bad])))
    assert [m.tool_call_id for m in out["messages"]] == ["b"]


def test_iteration_limit_finalizes_pending_calls_and_next_turn_succeeds(mods):
    limit = mods.nodes.MAX_ITERATIONS
    looping = [
        AIMessage(content="", tool_calls=[_call("get_weather", {"location": "Tokyo"}, f"w{i}")])
        for i in range(limit)
    ]
    # The last looping message carries two pending calls, to prove one result per call.
    looping[-1] = AIMessage(
        content="",
        tool_calls=[
            _call("get_weather", {"location": "Tokyo"}, "last1"),
            _call("get_weather", {"location": "London"}, "last2"),
        ],
    )
    model = ScriptedModel(looping + [AIMessage(content="second turn ok")])
    mods.nodes._model = model
    app = mods.graph.build_tool_agent()
    cfg = {"configurable": {"thread_id": "limit"}}

    r1 = asyncio.run(app.ainvoke({"messages": [HumanMessage(content="loop")]}, config=cfg))
    msgs = r1["messages"]
    assert isinstance(msgs[-1], AIMessage) and not msgs[-1].tool_calls
    assert "limit" in msgs[-1].content
    answered = {m.tool_call_id for m in msgs if isinstance(m, ToolMessage)}
    asked = {tc["id"] for m in msgs if isinstance(m, AIMessage) for tc in m.tool_calls}
    assert asked == answered and {"last1", "last2"} <= answered
    assert len(model.seen) == limit

    # Second turn on the same thread: counter is reset, history is well-formed.
    r2 = asyncio.run(app.ainvoke({"messages": [HumanMessage(content="again")]}, config=cfg))
    assert r2["messages"][-1].content == "second turn ok"
    assert len(model.seen) == limit + 1
    assert r2["iteration_count"] == 1


def test_budget_is_per_turn_not_cumulative(mods):
    """Two turns of (tool call, answer) = 2 model calls each; never trips even if the sum > limit."""
    mods.nodes.MAX_ITERATIONS = 3
    turn = lambda i: [  # noqa: E731
        AIMessage(content="", tool_calls=[_call("get_weather", {"location": "Tokyo"}, f"t{i}")]),
        AIMessage(content=f"done {i}"),
    ]
    mods.nodes._model = ScriptedModel(turn(1) + turn(2))
    app = mods.graph.build_tool_agent()
    cfg = {"configurable": {"thread_id": "per-turn"}}
    for i in (1, 2):
        out = asyncio.run(app.ainvoke({"messages": [HumanMessage(content=str(i))]}, config=cfg))
        assert out["messages"][-1].content == f"done {i}"


def test_native_create_agent_path_builds_and_runs_offline(monkeypatch):
    """The illustrative create_agent block is importable; with a fake model it runs the tool loop."""
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    monkeypatch.setenv("AGENT_MODEL", "fake-model")
    for name in ("tools",):
        _load(monkeypatch, name)
    ns = {"__name__": "native_agent"}
    exec(compile(SOURCES["native_agent"], "native_agent", "exec"), ns)

    class FakeToolModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    model = FakeToolModel(
        messages=iter(
            [
                AIMessage(content="", tool_calls=[_call("calculate", {"expression": "2+3"}, "n1")]),
                AIMessage(content="5"),
            ]
        )
    )
    from langchain.agents.middleware import ModelCallLimitMiddleware

    agent = create_agent(
        model,
        tools=sys.modules["tools"].ALL_TOOLS,
        middleware=[ModelCallLimitMiddleware(run_limit=10, exit_behavior="end"), ns["tool_safety"]],
    )
    out = agent.invoke({"messages": [{"role": "user", "content": "2+3?"}]})
    assert out["messages"][-1].content == "5"
    assert any(m.type == "tool" and '"result": 5' in m.content for m in out["messages"])
