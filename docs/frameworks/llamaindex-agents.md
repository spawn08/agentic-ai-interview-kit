---
sidebar_position: 6
title: "LlamaIndex Agents"
last_verified: 2026-10-12
---

# LlamaIndex Agents

LlamaIndex (formerly GPT Index) started as a data framework for connecting LLMs to external data sources. It has since evolved into a full agent framework with a distinctive strength: **treating data retrieval pipelines as first-class agent tools**. If your agent's primary job is to query, synthesize, and reason over complex data sources, LlamaIndex agents are purpose-built for that workflow.

:::note Historical interview framing
Older material (including earlier versions of this page) describes `OpenAIAgent`, `ReActAgent.from_tools`, and an "Agent Runner / Agent Worker" split. The current official docs organize agents around `FunctionAgent`, `ReActAgent`, `CodeActAgent`, and `AgentWorkflow` on top of Workflows. Know both vocabularies, but build against the current one.
:::

## Core Philosophy

While LangChain is "tool-first" and CrewAI is "role-first," LlamaIndex is **data-first**. Its agent primitives are designed around the assumption that most real-world AI agents need to intelligently query structured and unstructured data.

| Concept | Description |
|---------|-------------|
| **Query Engine** | A pipeline that takes a natural language query and returns a synthesized response from an index |
| **Tool** | Any callable the agent can use, including query engines wrapped as tools |
| **Agent** (`FunctionAgent`, `ReActAgent`, `CodeActAgent`) | A Workflow-based agent that runs the tool loop and decides which tools to call |
| **AgentWorkflow** | A pre-built Workflow that coordinates one or more agents, shared state, and handoffs |

## Query Engines as Tools

The defining pattern in LlamaIndex agents is wrapping query engines -- which themselves may involve retrieval, reranking, and synthesis -- as tools the agent can select from.

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import QueryEngineTool, ToolMetadata

# Build indexes over different data sources
financial_docs = SimpleDirectoryReader("data/financial_reports").load_data()
financial_index = VectorStoreIndex.from_documents(financial_docs)

hr_docs = SimpleDirectoryReader("data/hr_policies").load_data()
hr_index = VectorStoreIndex.from_documents(hr_docs)

# Wrap each index's query engine as a tool
financial_tool = QueryEngineTool(
    query_engine=financial_index.as_query_engine(similarity_top_k=5),
    metadata=ToolMetadata(
        name="financial_reports",
        description="""Use this tool to answer questions about financial 
        performance, revenue, expenses, and quarterly results. The data 
        covers fiscal years 2022-2025.""",
    ),
)

hr_tool = QueryEngineTool(
    query_engine=hr_index.as_query_engine(similarity_top_k=3),
    metadata=ToolMetadata(
        name="hr_policies",
        description="""Use this tool to answer questions about company HR 
        policies, benefits, leave policies, and employee handbook content.""",
    ),
)
```

:::tip Tool Descriptions Are Critical
The agent selects tools based entirely on their descriptions. A vague description like "search documents" will cause poor routing. Be specific about what datthe tool covers, the time range, and the types of questions it can answer.
:::

## Building an Agent

**Verified against official documentation: 2026-10-12** ([agents guide](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/), [building agents](https://developers.llamaindex.ai/python/framework/understanding/agent/)). Current agents are built on the **Workflows** engine and live in `llama_index.core.agent.workflow`. All code on this page is **illustrative and untested**; set `AGENT_MODEL` to a model your provider account supports. The `OpenAIAgent` class (built via `from_tools`, driven with `.chat`) in older tutorials does not appear on the current agent pages fetched; check your installed version before using it.

| Class | Strategy | When to consider |
|-------|----------|------------------|
| `FunctionAgent` | Uses the LLM provider's function/tool-calling API | The model supports native tool calling (the default starting point in the docs) |
| `ReActAgent` | Text-based Thought/Action/Observation prompting | Models without reliable native tool calling, or when you want an inspectable reasoning loop |
| `CodeActAgent` | The model writes code that calls your tools; you supply `code_execute_fn` | Multi-step tool composition where code is more compact than many tool calls |
| `AgentWorkflow` | A Workflow that manages one or more agents, shared state, and handoffs | Multi-agent systems and shared state |

### FunctionAgent

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
import asyncio
import os
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

llm = OpenAI(model=os.environ["AGENT_MODEL"])  # provider class is your choice

agent = FunctionAgent(
    tools=[financial_tool, hr_tool],  # QueryEngineTools defined above
    llm=llm,
    system_prompt="""You are a corporate assistant that helps employees find
    information from financial reports and HR policies. Always cite which
    source you used to answer the question.""",
)

async def main():
    response = await agent.run(
        "What was our latest quarterly revenue and what is the parental leave policy?"
    )
    print(str(response))

asyncio.run(main())
```

The docs note that `FunctionAgent` streams by default and that `streaming=False` can be set if you hit an error with your provider.

### ReActAgent

```python
from llama_index.core.agent.workflow import ReActAgent

# Illustrative, untested.
react_agent = ReActAgent(tools=[financial_tool, hr_tool], llm=llm)
response = await react_agent.run("Compare recent revenue trends.")
```

:::info ReAct vs Function Calling
**Function calling** agents rely on the LLM provider's structured tool-calling API. **ReAct** agents use a text-based reasoning loop (Thought/Action/Observation) and so depend on the model following a prompt format. Native function calling is generally more reliable where available, but verify with your own evaluations.
:::

### CodeActAgent

`CodeActAgent` needs a `code_execute_fn` that runs model-generated code. The official example runs code **in-process and warns it is not safe for production**; use proper sandboxing.

```python
from llama_index.core.agent.workflow import CodeActAgent

# Illustrative, untested. `execute_in_sandbox` is a placeholder for YOUR
# isolated executor (container, restricted runtime); never exec model code
# in your application process.
agent = CodeActAgent(
    code_execute_fn=execute_in_sandbox,
    llm=llm,
    tools=[add, subtract, multiply, divide],
)
```

### AgentWorkflow: Multi-Agent and State

`AgentWorkflow` is a pre-built `Workflow` that takes several agents, a `root_agent` (by name), and optional `initial_state`. Agents hand off control according to `can_handoff_to`. Further patterns (orchestrator agent with sub-agents as tools, custom planner) are in the [multi-agent guide](https://developers.llamaindex.ai/python/framework/understanding/agent/multi_agent/).

```python
from llama_index.core.agent.workflow import AgentWorkflow, FunctionAgent

# Illustrative, untested; search_web, record_notes, write_report are your tools.
research_agent = FunctionAgent(
    name="ResearchAgent",
    description="Search sources and record notes.",
    system_prompt="Research the topic, then hand off to WriteAgent.",
    llm=llm,
    tools=[search_web, record_notes],
    can_handoff_to=["WriteAgent"],
)
write_agent = FunctionAgent(
    name="WriteAgent",
    description="Writes a report from the notes.",
    system_prompt="Write the report from recorded notes.",
    llm=llm,
    tools=[write_report],
)
workflow = AgentWorkflow(
    agents=[research_agent, write_agent],
    root_agent=research_agent.name,
    initial_state={"research_notes": {}, "report_content": "Not written yet."},
)
response = await workflow.run(user_msg="Write a short report on retrieval evaluation.")
```

**State.** An `AgentWorkflow` is stateless between runs by default. Create `ctx = Context(workflow)` and pass it to each run to keep state, and use `ctx.to_dict(serializer=JsonSerializer())` / `Context.from_dict(...)` to persist and restore it ([state guide](https://developers.llamaindex.ai/python/framework/understanding/agent/state/)). Tools can read and edit the shared `state` through `ctx.store`. Treat deserializing a context as trusting its source; the docs also list `JsonPickleSerializer`, which carries the usual pickle risks.

**Human-in-the-loop.** A tool can call `ctx.wait_for_event(HumanResponseEvent, waiter_event=InputRequiredEvent(...), ...)`; the caller sees `InputRequiredEvent` while streaming events and answers with `handler.ctx.send_event(HumanResponseEvent(...))` ([HITL guide](https://developers.llamaindex.ai/python/framework/understanding/agent/human_in_the_loop/)). For slow or cross-process approvals the docs suggest serializing the context so the workflow can resume later. Authentication of the approver and idempotent side effects remain your responsibility.

## Sub-Question Query Engine

The Sub-Question Query Engine is a powerful LlamaIndex pattern that automatically decomposes a complex question into sub-questions, routes each to the appropriate tool, and synthesizes the answers.

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.question_gen import LLMQuestionGenerator
from llama_index.core.query_engine import SubQuestionQueryEngine

# Each tool covers a different data domain
tools = [
    QueryEngineTool(
        query_engine=financial_index.as_query_engine(),
        metadata=ToolMetadata(
            name="financials",
            description="Financial reports and quarterly earnings data.",
        ),
    ),
    QueryEngineTool(
        query_engine=product_index.as_query_engine(),
        metadata=ToolMetadata(
            name="products",
            description="Product catalog, specifications, and roadmap.",
        ),
    ),
    QueryEngineTool(
        query_engine=competitor_index.as_query_engine(),
        metadata=ToolMetadata(
            name="competitors",
            description="Competitor analysis and market positioning.",
        ),
    ),
]

sub_question_engine = SubQuestionQueryEngine.from_defaults(
    query_engine_tools=tools,
    question_gen=LLMQuestionGenerator.from_defaults(),  # uses Settings.llm; core, no extra package
    use_async=True,
)

# A complex question that spans multiple data sources
response = sub_question_engine.query(
    "How does our product roadmap align with competitor offerings, "
    "and do we have the financial runway to execute on it?"
)
```

### How Sub-Question Decomposition Works

1. The user asks a complex, multi-faceted question.
2. The question generator breaks it into targeted sub-questions (e.g., "What is the product roadmap?", "What are competitor offerings?", "What is our financial runway?").
3. Each sub-question is routed to the most relevant query engine tool.
4. Individual answers are retrieved in parallel.
5. A synthesis step combines all sub-answers into a coherent final response.

## Tool Abstractions

LlamaIndex provides multiple ways to define tools beyond query engine wrappers.

### Function Tools

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
from llama_index.core.tools import FunctionTool

def calculate_runway(
    cash_on_hand: float,
    monthly_burn_rate: float,
) -> str:
    """Calculate the financial runway in months given current cash and burn rate."""
    months = cash_on_hand / monthly_burn_rate
    return f"Runway: {months:.1f} months ({months/12:.1f} years)"

runway_tool = FunctionTool.from_defaults(
    fn=calculate_runway,
    name="calculate_runway",
    description="Calculate financial runway from cash reserves and burn rate.",
)
```

### Pydantic Tools (Structured Input)

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
from pydantic import BaseModel, Field
from llama_index.core.tools import FunctionTool

class StockQuery(BaseModel):
    """Query parameters for stock data retrieval."""
    symbol: str = Field(description="Stock ticker symbol (e.g., AAPL)")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")
    end_date: str = Field(description="End date in YYYY-MM-DD format")
    metric: str = Field(description="Metric to retrieve: 'price', 'volume', or 'both'")

def fetch_stock_data(query: StockQuery) -> str:
    """Fetch historical stock data for analysis."""
    return f"Stock data for {query.symbol} from {query.start_date} to {query.end_date}"

stock_tool = FunctionTool.from_defaults(
    fn=fetch_stock_data,
    name="stock_data",
    description="Retrieve historical stock market data for analysis.",
)
```

## RAG-Focused Agent Patterns

### Router Query Engine

Route queries to different indexes based on the question type.

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector

router_engine = RouterQueryEngine(
    selector=LLMSingleSelector.from_defaults(),
    query_engine_tools=[
        QueryEngineTool(
            query_engine=summary_index.as_query_engine(),
            metadata=ToolMetadata(
                name="summary",
                description="Useful for summarization questions over the entire document.",
            ),
        ),
        QueryEngineTool(
            query_engine=vector_index.as_query_engine(),
            metadata=ToolMetadata(
                name="vector_search",
                description="Useful for specific fact-based questions.",
            ),
        ),
    ],
)
```

### Multi-Document Agent

Build agents that reason across many documents, each with its own query engine.

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core import VectorStoreIndex, SummaryIndex
import os

# Build per-document tools
doc_tools = []
for doc_name, documents in document_collections.items():
    vector_index = VectorStoreIndex.from_documents(documents)
    summary_index = SummaryIndex.from_documents(documents)

    query_tool = QueryEngineTool(
        query_engine=vector_index.as_query_engine(),
        metadata=ToolMetadata(
            name=f"{doc_name}_search",
            description=f"Search for specific information in {doc_name}.",
        ),
    )

    summary_tool = QueryEngineTool(
        query_engine=summary_index.as_query_engine(),
        metadata=ToolMetadata(
            name=f"{doc_name}_summary",
            description=f"Get a summary of {doc_name}.",
        ),
    )

    doc_tools.extend([query_tool, summary_tool])

# Create an agent with tools spanning all documents
agent = FunctionAgent(
    tools=doc_tools,
    llm=OpenAI(model=os.environ["AGENT_MODEL"]),
    system_prompt="You are a research assistant with access to multiple documents.",
)
```

:::warning Tool Count Limits
When an agent has access to many tools (e.g., 2 tools per document across 50 documents = 100 tools), LLMs struggle with tool selection. Use a **tool retrieval** step to dynamically select the top-k most relevant tools for each query, or use a hierarchical agent architecture.
:::

## Agentic RAG Pipeline

Combining retrieval, tool use, and multi-step reasoning into a cohesive pipeline.

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
import os
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import QueryEngineTool, FunctionTool

# RAG tools
knowledge_tool = QueryEngineTool(
    query_engine=knowledge_index.as_query_engine(similarity_top_k=5),
    metadata=ToolMetadata(
        name="knowledge_base",
        description="Search the internal knowledge base for company information.",
    ),
)

# Computation tools
def analyze_sentiment(text: str) -> str:
    """Analyze the sentiment of the given text."""
    # Implementation using a model or heuristic
    return "Sentiment: Positive (confidence: 0.87)"

sentiment_tool = FunctionTool.from_defaults(fn=analyze_sentiment)

# Build the agentic RAG pipeline
agent = FunctionAgent(
    tools=[knowledge_tool, sentiment_tool],
    llm=OpenAI(model=os.environ["AGENT_MODEL"]),
    system_prompt="""You are an analyst. First retrieve relevant information 
    from the knowledge base, then analyze it using available tools before 
    providing your final answer.""",
)

# The agent decides: retrieve -> analyze -> synthesize
response = await agent.run("What do customers think about our latest product launch?")  # inside an async function
```

## Pros and Cons

### Strengths

- **Best-in-class RAG**: The most sophisticated retrieval and query pipeline abstractions available.
- **Query engine as tool**: Seamlessly converts complex retrieval pipelines into agent tools.
- **Sub-question decomposition**: Automatically breaks complex queries across multiple data sources.
- **Index variety**: Vector, summary, keyword, knowledge graph, and SQL indexes out of the box.
- **Data connectors**: 100+ data loaders (LlamaHub) for PDFs, databases, APIs, and more.

### Weaknesses

- **Data-centric scope**: Less suited for agents that primarily need to take actions rather than query data.
- **Multi-agent is Workflow-centric**: `AgentWorkflow` provides handoffs and shared state, but the role-based collaboration abstractions of other frameworks are not its focus; custom orchestration uses lower-level Workflows.
- **Complexity at scale**: Configuring retrieval pipelines with reranking, filtering, and hybrid search adds significant complexity.
- **Overlap with LangChain**: Many users find themselves using both frameworks, which adds dependency overhead.

:::tip When to Choose LlamaIndex Agents
Choose LlamaIndex when your agent's primary function is **intelligent data retrieval and synthesis** across multiple heterogeneous data sources. If your agent needs to take actions (send emails, update databases, call APIs), combine LlamaIndex tools with a broader orchestration framework like LangGraph.
:::

## Interview Talking Points

- Explain the **query engine as tool** pattern and why it is more powerful than simple vector search.
- Describe how the **Sub-Question Query Engine** decomposes complex questions across data sources.
- Compare LlamaIndex's **data-first** philosophy with LangChain's **tool-first** approach.
- Discuss strategies for handling **many tools** (tool retrieval, hierarchical agents).
- Explain when you would combine LlamaIndex with LangGraph rather than using either alone.
- Distinguish `FunctionAgent`, `ReActAgent`, and `CodeActAgent`, and explain why `CodeActAgent` needs a sandbox.
- Explain how `AgentWorkflow` handoffs and shared state work, and how `Context` serialization supports resuming.

## Official Sources

Checked **2026-10-12**: [agents guide](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/), [building agents](https://developers.llamaindex.ai/python/framework/understanding/agent/), [multi-agent patterns](https://developers.llamaindex.ai/python/framework/understanding/agent/multi_agent/), [maintaining state](https://developers.llamaindex.ai/python/framework/understanding/agent/state/), [human in the loop](https://developers.llamaindex.ai/python/framework/understanding/agent/human_in_the_loop/), [CodeActAgent example](https://developers.llamaindex.ai/python/examples/agent/code_act_agent/), and the `llama_index.core.agent.workflow` package exports on GitHub. `ReActAgent`'s constructor arguments, and `QueryEngineTool` / `SubQuestionQueryEngine` snippets retained from the original page, were not re-verified.
