"""Offline tests for runnable snippets in the migrated docs (no API keys, no network).

Run: pytest examples/langchain-v1
"""
import re
from pathlib import Path

import pytest

from check_doc_imports import PAGE_LOCAL_MODULES, TIER2_PAGES, main as check_imports, python_blocks

DOCS = Path(__file__).resolve().parents[2] / "docs"


def _solution(doc: str, heading: str) -> str:
    """Return the first python fence after `heading` in a docs page."""
    text = (DOCS / doc).read_text(encoding="utf-8")
    start = text.index(heading)
    m = re.search(r"```python\n(.*?)```", text[start:], re.S)
    assert m, heading
    return m.group(1)


@pytest.mark.parametrize(
    "heading",
    ["## Challenge 2: Validate and Execute Native Tool Calls", "## Challenge 5: Build a Simple Agent Loop"],
)
def test_coding_challenge_solutions_run(heading):
    code = _solution("interview-questions/coding-challenges.md", heading)
    exec(compile(code, heading, "exec"), {"__name__": "__doc_example__"})  # asserts live in the snippet


_CHALLENGES = (DOCS / "interview-questions/coding-challenges.md").read_text(encoding="utf-8")
_CHALLENGE_BLOCKS = list(python_blocks(_CHALLENGES))


def test_coding_challenges_has_no_legacy_text_parser():
    """The single historical text-parsed ReAct example lives on the react-pattern page only."""
    assert "parse_react_output" not in _CHALLENGES
    assert "text-parsed" in (DOCS / "design-patterns/react-pattern.md").read_text(encoding="utf-8")


def test_legacy_parser_example_runs_and_rejects_missing_labels():
    code = _solution("design-patterns/react-pattern.md", "<summary>Legacy:")
    ns = {}
    exec(compile(code, "historical-react-parser", "exec"), ns)
    with pytest.raises(ValueError, match="Missing historical"):
        ns["parse_legacy_action"]("search: population of France")
    # Demonstrate the limitation, not a recommended parser: extra lines are truncated.
    assert ns["parse_legacy_action"]("Action: search\nAction Input: first line\nsecond line") == (
        "search", "first line"
    )


def test_historical_parser_occurs_on_exactly_one_page():
    pages = [p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*.md")
             if "def parse_legacy_action(" in p.read_text(encoding="utf-8")]
    assert pages == ["design-patterns/react-pattern.md"]


@pytest.mark.parametrize("line,code", _CHALLENGE_BLOCKS, ids=[f"line{n}" for n, _ in _CHALLENGE_BLOCKS])
def test_every_coding_challenge_block_runs(line, code):
    """Every python block (all are self-contained with asserts) parses AND executes offline."""
    exec(compile(code, f"coding-challenges.md:{line}", "exec"), {"__name__": "__doc_example__"})


def test_naive_fence_regex_would_have_broken_challenge_blocks():
    """Regression: blocks holding an indented fence string must be extracted whole."""
    assert any("FENCE" in code for _, code in _CHALLENGE_BLOCKS)
    for _, code in _CHALLENGE_BLOCKS:
        assert "```" not in code


def test_audited_migration_pages_are_import_checked():
    """Every page in the audit's create_react_agent migration set is covered by CI."""
    required = {
        "docs/core-concepts/guardrails-and-safety.md",
        "docs/core-concepts/what-are-agents.md",
        "docs/core-concepts/tools-and-function-calling.md",
        "docs/core-concepts/planning-and-reasoning.md",
        "docs/core-concepts/agent-architectures.md",
        "docs/core-concepts/memory-systems.md",
        "docs/implementations/tool-calling-agent.md",
        "docs/implementations/basic-react-agent.md",
        "docs/frameworks/langgraph-deep-dive.md",
        "docs/design-patterns/human-in-the-loop.md",
        "docs/design-patterns/tool-use-pattern.md",
        "docs/design-patterns/react-pattern.md",
        "docs/implementations/evaluation-harness.md",
    }
    assert required <= set(TIER2_PAGES)
    assert len(TIER2_PAGES) == len(set(TIER2_PAGES))


def test_tier2_pages_import_cleanly(monkeypatch, capsys):
    """All python fences in all Tier 2 pages parse; every import resolves except the exact page-local modules."""
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    rc = check_imports(TIER2_PAGES)
    assert rc == 0, capsys.readouterr().out


def test_exclusions_are_only_page_local_modules():
    for page, mods in PAGE_LOCAL_MODULES.items():
        text = (DOCS.parent / page).read_text(encoding="utf-8")
        assert all(f"{m}.py" in text for m in mods), page


def test_create_agent_runs_tool_loop_with_fake_model():
    """create_agent + native tool calls, using a scripted fake chat model."""
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.tools import tool

    @tool
    def get_population(city: str) -> str:
        """Get the population of a city."""
        return "14M"

    class FakeToolModel(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    model = FakeToolModel(
        messages=iter(
            [
                AIMessage(content="", tool_calls=[{"id": "1", "name": "get_population", "args": {"city": "Tokyo"}}]),
                AIMessage(content="Tokyo has 14M people."),
            ]
        )
    )
    agent = create_agent(model, tools=[get_population], system_prompt="Be brief.")
    result = agent.invoke({"messages": [{"role": "user", "content": "Population of Tokyo?"}]})
    assert result["messages"][-1].content == "Tokyo has 14M people."
    assert any(m.type == "tool" and m.content == "14M" for m in result["messages"])


def test_mcp_server_snippet_runs_on_mcpserver():
    """The tools page's MCPServer example imports from mcp.server.mcpserver and its tools execute."""
    import asyncio

    code = _solution("core-concepts/tools-and-function-calling.md", "### Building an MCP Server (Python)")
    assert "from mcp.server.mcpserver import MCPServer" in code and "from mcp.server.fastmcp import" not in code
    ns: dict = {"__name__": "__doc_example__"}
    exec(compile(code, "mcp-server-snippet", "exec"), ns)
    result = asyncio.run(ns["mcp"].call_tool("calculate_bmi", {"weight_kg": 70, "height_m": 1.75}))
    assert "BMI: 22.9 (normal)" in str(result)
