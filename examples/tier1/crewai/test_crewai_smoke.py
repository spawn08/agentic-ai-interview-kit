"""Offline smoke test for docs/frameworks/crewai-guide.md (construction only; kickoff() is never called).

Builds the page's Agent / Task / Crew objects with the INSTALLED crewai and crewai-tools, with fake
credentials and telemetry off, so a renamed parameter or a rejected type (e.g. manager_llm) fails here.
No model or search call is made.
"""
import pytest
from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool
from crewai_tools import DirectoryReadTool, FileReadTool, ScrapeWebsiteTool, SerperDevTool


@pytest.fixture(autouse=True)
def offline_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setenv("SERPER_API_KEY", "fake")
    monkeypatch.setenv("CREWAI_TRACING_ENABLED", "false")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.chdir(tmp_path)


@tool("Database Query Tool")
def query_database(sql: str) -> str:
    """Execute a read-only SQL query against the analytics database."""
    return "Query results: 42 records found"


def build_team():
    researcher = Agent(
        role="Senior Research Analyst", goal="Find information", backstory="Meticulous analyst.",
        tools=[SerperDevTool(), ScrapeWebsiteTool(), FileReadTool(), query_database],
        verbose=False, allow_delegation=True, max_iter=5,
    )
    writer = Agent(role="Writer", goal="Write", backstory="Clear writer.", allow_delegation=False)
    research = Task(description="Research.", expected_output="Report.", agent=researcher, output_file="r.md")
    writing = Task(description="Write.", expected_output="Post.", agent=writer, context=[research])
    return researcher, writer, research, writing


def test_sequential_crew():
    researcher, writer, research, writing = build_team()
    crew = Crew(agents=[researcher, writer], tasks=[research, writing], process=Process.sequential, max_rpm=10)
    assert crew.process == Process.sequential and len(crew.tasks) == 2


def test_hierarchical_crew_uses_crewai_llm():
    researcher, writer, research, writing = build_team()
    crew = Crew(
        agents=[researcher, writer], tasks=[research, writing], process=Process.hierarchical,
        manager_llm=LLM(model="fake-model", temperature=0), manager_agent=None,
    )
    assert crew.process == Process.hierarchical


def test_memory_and_embedder_config_accepted():
    researcher, writer, research, writing = build_team()
    Crew(
        agents=[researcher, writer], tasks=[research, writing], memory=True,
        embedder={"provider": "openai", "config": {"model": "fake-embedding"}},
    )


def test_only_documented_processes_exist():
    assert {p.value for p in Process} == {"sequential", "hierarchical"}
    assert DirectoryReadTool is not None
