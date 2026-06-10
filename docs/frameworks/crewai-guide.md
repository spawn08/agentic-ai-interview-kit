---
sidebar_position: 3
title: "CrewAI"
---

# CrewAI

CrewAI is a multi-agent orchestration framework built around the metaphor of a team ("crew") of specialized AI agents collaborating to accomplish complex tasks. Its role-based design makes it intuitive to set up and reason about, especially for workflows that mirror real-world team structures.

## Core Concepts

CrewAI organizes work around four primitives:

| Concept | Description |
|---------|-------------|
| **Agent** | An autonomous unit with a role, goal, backstory, and optional tools |
| **Task** | A discrete unit of work assigned to a specific agent |
| **Crew** | A team of agents working together on a set of tasks |
| **Process** | The execution strategy: sequential, hierarchical, or consensual |

### Agents

An agent in CrewAI is defined by its persona and capabilities. The role, goal, and backstory shape the LLM's behavior through careful prompt engineering under the hood.

```python
from crewai import Agent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

researcher = Agent(
    role="Senior Research Analyst",
    goal="Find comprehensive, accurate information about emerging AI trends",
    backstory="""You are a veteran research analyst with 15 years of experience 
    in technology analysis. You are meticulous about fact-checking and always 
    cite your sources. You have a talent for identifying patterns across 
    disparate data points.""",
    tools=[SerperDevTool(), ScrapeWebsiteTool()],
    verbose=True,
    allow_delegation=True,
    max_iter=5,
)

writer = Agent(
    role="Technical Content Writer",
    goal="Transform research into clear, engaging technical content",
    backstory="""You are an award-winning technical writer who specializes in 
    making complex AI concepts accessible. You write with precision and 
    clarity, always structuring content for maximum readability.""",
    verbose=True,
    allow_delegation=False,
)
```

:::tip Writing Effective Backstories
The backstory is not decorative -- it significantly influences agent behavior. A backstory mentioning "you are meticulous about fact-checking" produces noticeably different outputs than "you move fast and prioritize speed." Treat it as a behavioral specification.
:::

### Tasks

Tasks define what needs to be done, who does it, and what the expected output looks like.

```python
from crewai import Task

research_task = Task(
    description="""Research the current state of AI agent frameworks in 2025.
    Focus on: LangGraph, CrewAI, AutoGen, and OpenAI Assistants.
    Identify key differentiators, adoption trends, and production readiness.
    Include specific examples of production deployments where possible.""",
    expected_output="""A structured research report with sections for each 
    framework, comparative analysis, and a recommendation matrix.""",
    agent=researcher,
    output_file="research_report.md",
)

writing_task = Task(
    description="""Using the research report, write a compelling blog post 
    comparing AI agent frameworks. The post should be 1500-2000 words, 
    technically accurate, and accessible to senior engineers.""",
    expected_output="""A polished blog post in markdown format with an 
    introduction, framework comparisons, recommendations by use case, 
    and a conclusion.""",
    agent=writer,
    context=[research_task],  # This task depends on the research task
    output_file="blog_post.md",
)
```

:::info Task Context
The `context` parameter creates explicit data dependencies between tasks. When `writing_task` lists `research_task` in its context, the output of the research task is automatically passed to the writer agent. This is how information flows between agents.
:::

### Crews

The crew brings agents and tasks together under a defined process.

```python
from crewai import Crew, Process

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,
    verbose=True,
    memory=True,
    max_rpm=10,  # Rate limiting for API calls
)

result = crew.kickoff()
print(result.raw)           # Raw text output
print(result.tasks_output)  # Per-task outputs
```

## Process Types

The process defines how tasks are assigned and executed.

### Sequential Process

Tasks execute one after another in the order they are listed. Each task can access the outputs of previous tasks through the `context` parameter.

```python
crew = Crew(
    agents=[researcher, analyst, writer],
    tasks=[research_task, analysis_task, writing_task],
    process=Process.sequential,
)
```

**Best for**: Linear workflows where each step builds on the previous one (research, then analyze, then write).

### Hierarchical Process

A manager agent automatically coordinates the crew, delegating tasks to the most appropriate agent and reviewing outputs.

```python
from langchain_openai import ChatOpenAI

crew = Crew(
    agents=[researcher, analyst, writer],
    tasks=[research_task, analysis_task, writing_task],
    process=Process.hierarchical,
    manager_llm=ChatOpenAI(model="gpt-4o", temperature=0),
    manager_agent=None,  # Auto-creates a manager, or provide a custom one
)
```

**Best for**: Complex projects where task assignment is dynamic and quality review is needed.

:::warning Hierarchical Cost
Hierarchical process adds a manager agent that makes additional LLM calls for coordination and review. This increases both latency and token cost. Use it only when the coordination benefits outweigh the overhead.
:::

### Process Comparison

| Feature | Sequential | Hierarchical |
|---------|-----------|-------------|
| Task order | Fixed, linear | Manager-decided |
| Delegation | Manual via context | Automatic |
| Quality review | None built-in | Manager reviews outputs |
| LLM calls | Predictable | Higher (manager overhead) |
| Complexity | Low | Medium-High |

## Delegation

When `allow_delegation=True`, an agent can ask other agents in the crew for help. This enables dynamic collaboration.

```python
lead_developer = Agent(
    role="Lead Developer",
    goal="Design and implement the system architecture",
    backstory="You are a principal engineer who excels at system design.",
    allow_delegation=True,  # Can ask the researcher for information
)

researcher = Agent(
    role="Research Specialist",
    goal="Provide technical information when requested",
    backstory="You are a deep technical researcher.",
    allow_delegation=False,  # Focused on answering, not delegating
)
```

When the lead developer encounters a question it cannot answer, it can delegate a sub-question to the researcher and incorporate the response into its own work.

## Memory

CrewAI supports multiple memory types that persist across task executions.

```python
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    memory=True,          # Enable all memory types
    embedder={            # Custom embedding configuration
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
)
```

| Memory Type | Scope | Purpose |
|-------------|-------|---------|
| **Short-term** | Current crew execution | Maintains context within a single run |
| **Long-term** | Across executions | Learns from past runs to improve over time |
| **Entity** | Across executions | Remembers facts about specific entities |

## Tool Integration

CrewAI provides a library of built-in tools and supports custom tool creation.

```python
from crewai import Agent
from crewai_tools import (
    SerperDevTool,
    ScrapeWebsiteTool,
    FileReadTool,
    DirectoryReadTool,
)

# Built-in tools
search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()
file_tool = FileReadTool()

# Custom tool using the @tool decorator
from crewai.tools import tool

@tool("Database Query Tool")
def query_database(sql: str) -> str:
    """Execute a read-only SQL query against the analytics database.
    Use this when you need to retrieve specific data points or statistics."""
    # Implementation here
    return "Query results: 42 records found"

data_agent = Agent(
    role="Data Analyst",
    goal="Extract insights from the database",
    backstory="You are an expert data analyst.",
    tools=[search_tool, query_database],
)
```

## Complete Multi-Agent Example

Here is a full example of a content production crew with three specialized agents.

```python
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool

# --- Agents ---
researcher = Agent(
    role="Senior Researcher",
    goal="Uncover cutting-edge developments in AI agent architectures",
    backstory="A PhD-level AI researcher who tracks every major paper and release.",
    tools=[SerperDevTool()],
    allow_delegation=False,
    verbose=True,
)

analyst = Agent(
    role="Technology Analyst",
    goal="Evaluate technologies and provide strategic recommendations",
    backstory="A seasoned technology strategist at a Fortune 500 company.",
    allow_delegation=True,
    verbose=True,
)

editor = Agent(
    role="Senior Editor",
    goal="Produce publication-ready content that is accurate and engaging",
    backstory="Former editor at a leading tech publication with high standards.",
    allow_delegation=False,
    verbose=True,
)

# --- Tasks ---
research = Task(
    description="Research the top 5 AI agent frameworks released or updated in 2025.",
    expected_output="A detailed report covering each framework's architecture and strengths.",
    agent=researcher,
)

analysis = Task(
    description="Analyze the research and create a comparison matrix with recommendations.",
    expected_output="A structured comparison with clear recommendations by use case.",
    agent=analyst,
    context=[research],
)

final_article = Task(
    description="Write a polished 2000-word article synthesizing the research and analysis.",
    expected_output="A publication-ready article in markdown format.",
    agent=editor,
    context=[research, analysis],
    output_file="final_article.md",
)

# --- Crew ---
crew = Crew(
    agents=[researcher, analyst, editor],
    tasks=[research, analysis, final_article],
    process=Process.sequential,
    verbose=True,
    memory=True,
)

result = crew.kickoff()
print(f"Final output:\n{result.raw[:500]}")
```

## Pros and Cons

### Strengths

- **Intuitive mental model**: Roles and teams map naturally to how humans organize work.
- **Low barrier to entry**: A working multi-agent system can be built in under 50 lines of code.
- **Built-in memory**: Short-term, long-term, and entity memory are available out of the box.
- **Task dependencies**: The `context` parameter makes data flow between agents explicit.

### Weaknesses

- **Limited control flow**: No support for cycles, conditional branching, or complex graph topologies (unlike LangGraph).
- **Opaque execution**: The internal prompting and delegation logic is harder to customize or debug.
- **Scaling concerns**: Large crews with many agents and delegation can generate unpredictable LLM call patterns.
- **Younger ecosystem**: Fewer production case studies compared to LangChain/LangGraph.

:::tip When to Choose CrewAI
CrewAI is ideal when your problem maps naturally to a **team of specialists with distinct roles** working on **well-defined tasks in sequence**. If you need complex branching, cycles, or fine-grained state control, consider LangGraph instead.
:::

## Interview Talking Points

- Explain how **role-based agent design** reduces prompt engineering complexity.
- Compare **sequential vs. hierarchical** processes and their trade-offs.
- Describe how the **context parameter** on tasks creates an implicit data pipeline between agents.
- Discuss when **delegation** helps vs. when it creates unpredictable behavior.
- Contrast CrewAI's **task-centric** model with LangGraph's **graph-centric** model.
