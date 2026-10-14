---
sidebar_position: 1
title: "LangChain"
last_verified: 2026-10-12
---

# LangChain

LangChain is the most widely adopted framework for building applications powered by large language models. Since v1, the `langchain` package is deliberately small and agent-focused: `create_agent` is the standard way to build an agent, **middleware** customizes every step of the agent loop, and **structured output** is built in. Everything else (legacy chains, retrievers, the old `AgentExecutor`) moved to `langchain-classic`.

:::info Sources and Verification
Verified against the official LangChain docs (v1 migration guide, agents, middleware, structured output) on 2026-10-12. Snippets marked `# illustrative` were not executed; runnable ones live in `examples/langchain-v1/`. See `reports/batch-2.md`.
:::

## Core Abstractions

LangChain organizes its functionality around several foundational primitives. Understanding these is essential before building anything non-trivial.

### Models

LangChain wraps LLM providers behind a unified interface so you can swap providers without rewriting application logic.

```python
import os

from langchain.chat_models import init_chat_model

# AGENT_MODEL is "<provider>:<model>", e.g. "openai:<model-id>" or "anthropic:<model-id>".
# Switch providers by changing the environment variable, not the code.
llm = init_chat_model(os.environ["AGENT_MODEL"], temperature=0)

response = llm.invoke("Explain agentic AI in two sentences.")
print(response.content)
```

:::info Model Types
LangChain distinguishes between **LLMs** (raw text completion) and **Chat Models** (message-based). Modern applications almost always use Chat Models. Provider classes such as `ChatOpenAI` (`langchain-openai`) and `ChatAnthropic` (`langchain-anthropic`) are chat model wrappers; `init_chat_model` picks the right one from the `provider:model` string.
:::

### Prompt Templates

Prompt templates separate prompt engineering from application logic. They support variable interpolation and message formatting.

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role} who answers concisely."),
    ("human", "{question}"),
])

# Renders to a list of messages
messages = prompt.invoke({"role": "data scientist", "question": "What is RAG?"})
```

### Output Parsers and Structured Output

Output parsers transform raw LLM text into structured Python objects. This works for plain chains, but for agents (and for models that support it) prefer **native structured output**, covered in the `create_agent` section below.

```python
# illustrative
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

class AnalysisResult(BaseModel):
    sentiment: str = Field(description="positive, negative, or neutral")
    confidence: float = Field(description="confidence score between 0 and 1")
    summary: str = Field(description="one-sentence summary")

parser = PydanticOutputParser(pydantic_object=AnalysisResult)

# Include format instructions in the prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "Analyze the following text.\n{format_instructions}"),
    ("human", "{text}"),
])

chain = prompt | llm | parser
result = chain.invoke({
    "text": "The product exceeded all my expectations!",
    "format_instructions": parser.get_format_instructions(),
})
print(result.sentiment)  # "positive"
```

### Tools

Tools give LLMs the ability to interact with external systems. Any Python function can become a tool.

```python
from langchain_core.tools import tool

@tool
def search_database(query: str) -> str:
    """Search the internal knowledge base for relevant documents."""
    # In production, this would query a vector store or database
    return f"Found 3 results for: {query}"

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression))  # Use a safe evaluator in production

tools = [search_database, calculate]
```

:::warning Tool Descriptions Matter
The docstring of a `@tool`-decorated function is sent to the LLM as the tool description. A vague or missing description leads to poor tool selection. Write descriptions as if explaining the tool to a colleague.
:::

## LangChain Expression Language (LCEL)

LCEL is LangChain's declarative composition API. It uses the pipe operator (`|`) to chain components into executable sequences.

### Basic Chain

```python
import os

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful coding tutor."),
    ("human", "{question}"),
])

chain = prompt | init_chat_model(os.environ["AGENT_MODEL"]) | StrOutputParser()

# Invoke synchronously
answer = chain.invoke({"question": "Explain decorators in Python"})

# Stream token by token
for chunk in chain.stream({"question": "Explain decorators in Python"}):
    print(chunk, end="", flush=True)
```

### Branching with RunnableParallel

```python
from langchain_core.runnables import RunnableParallel

analysis_chain = RunnableParallel(
    summary=prompt_summary | llm | StrOutputParser(),
    sentiment=prompt_sentiment | llm | StrOutputParser(),
    keywords=prompt_keywords | llm | StrOutputParser(),
)

results = analysis_chain.invoke({"text": "LangChain is a powerful framework."})
# results = {"summary": "...", "sentiment": "...", "keywords": "..."}
```

:::tip LCEL Benefits
Every LCEL chain automatically gets: **streaming**, **async support**, **batch processing**, **retries**, and **LangSmith tracing** -- with zero extra code.
:::

### Conditional Routing

```python
from langchain_core.runnables import RunnableBranch

route_chain = RunnableBranch(
    (lambda x: "code" in x["topic"], code_chain),
    (lambda x: "math" in x["topic"], math_chain),
    default_chain,  # Fallback
)
```

## Key Modules

| Module | Purpose |
|--------|---------|
| `langchain-core` | Base abstractions, LCEL, `@tool`, messages, `InMemoryVectorStore` |
| `langchain` (v1) | `create_agent`, middleware, `init_chat_model`, structured output strategies, message types |
| `langchain-openai`, `langchain-anthropic`, `langchain-chroma`, ... | Partner packages: one integration per package, versioned independently |
| `langchain-community` | Long tail of community integrations (being sunset; the package emits a deprecation warning, prefer partner packages) |
| `langchain-classic` | Legacy code removed from `langchain` v1: `AgentExecutor`, legacy chains, `langchain.retrievers`, indexing API, hub |
| `langgraph` | Runtime under `create_agent`; use `StateGraph` directly for custom topologies |
| `langsmith` | Observability, tracing, and evaluation |

### The `langchain-classic` Boundary

In v1 the `langchain` namespace exposes essentially `langchain.agents` (`create_agent`, `AgentState`), `langchain.messages`, `langchain.tools`, `langchain.chat_models` and `langchain.embeddings`. Anything else you previously imported from `langchain` (for example `LLMChain`, `ConversationChain`, `MultiQueryRetriever`, `langchain.indexes`, `langchain.hub`, `AgentExecutor`) now lives in `langchain-classic`:

<details>
<summary>Legacy imports (pre-v1 names, kept for recognizing old code)</summary>

```python
# illustrative
# pip install langchain-classic
from langchain_classic.chains import LLMChain
from langchain_classic.retrievers import MultiQueryRetriever
```

</details>

Treat `langchain-classic` as a migration bridge for existing code, not a target for new code.

## Building a Simple Agent with `create_agent`

Agents use an LLM to decide which tools to call and when to stop. `create_agent` returns a compiled LangGraph graph running the standard loop: model call, tool execution, repeat until the model calls no more tools.

```python
import os

from langchain.agents import create_agent
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # Simulated response
    return f"The weather in {city} is 22C and sunny."

@tool
def get_population(city: str) -> str:
    """Get the population of a city."""
    populations = {"tokyo": "14M", "london": "9M", "paris": "2.1M"}
    return populations.get(city.lower(), "Unknown")

agent = create_agent(
    model=os.environ["AGENT_MODEL"],  # "<provider>:<model>"
    tools=[get_weather, get_population],
    system_prompt="You are a helpful travel assistant.",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather and population of Tokyo?"}]}
)
print(result["messages"][-1].content)
```

The agent is invoked with a `messages` state and returns the full message list; the answer is the last message. There is no prompt template with `{agent_scratchpad}`: the tool-call history is part of the message list.

### Agent Execution Flow

1. The model receives the conversation, the `system_prompt`, and the tool schemas.
2. It emits native tool calls, e.g. `get_weather("Tokyo")` and `get_population("Tokyo")`, possibly in parallel.
3. Tool results are appended to the conversation as tool messages.
4. The model synthesizes a final answer from the tool outputs.
5. The loop ends when the model responds without tool calls.

### Middleware

Middleware hooks into the agent loop (`before_agent`, `before_model`, `wrap_model_call`, `wrap_tool_call`, `after_model`, `after_agent`). It replaces the old `pre_model_hook`/`post_model_hook` arguments and the dynamic-prompt/error-handling options of earlier agent APIs. Built-ins include `SummarizationMiddleware`, `HumanInTheLoopMiddleware`, `ModelCallLimitMiddleware`, `ToolRetryMiddleware`, `ModelFallbackMiddleware`, and `PIIMiddleware`.

```python
# illustrative
import os

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRequest,
    SummarizationMiddleware,
    dynamic_prompt,
    wrap_tool_call,
)
from langchain.messages import ToolMessage

@dynamic_prompt
def role_prompt(request: ModelRequest) -> str:
    return "You are a helpful travel assistant. Be concise."

@wrap_tool_call
def tool_errors_as_messages(request, handler):
    try:
        return handler(request)
    except Exception as exc:
        return ToolMessage(content=f"Tool failed: {exc}", tool_call_id=request.tool_call["id"])

agent = create_agent(
    model=os.environ["AGENT_MODEL"],
    tools=[get_weather, get_population],
    middleware=[
        role_prompt,
        tool_errors_as_messages,
        SummarizationMiddleware(model=os.environ["AGENT_MODEL"]),
    ],
)
```

Middleware is not a separate runtime: hooks run inside the compiled LangGraph that `create_agent` returns, so the same agent can be dropped into a larger `StateGraph` as a node or subgraph.

### Structured Output

Pass `response_format` to get a validated object back in the `structured_response` key of the final state. Given a bare schema type, LangChain chooses `ProviderStrategy` (native provider structured output) when the model supports it, otherwise `ToolStrategy` (an artificial tool call). JSON Schema dicts must be wrapped explicitly in one of the strategies. The old "prompted output" mode was removed.

```python
# illustrative
import os

from pydantic import BaseModel

from langchain.agents import create_agent

class Answer(BaseModel):
    summary: str
    confidence: float

agent = create_agent(
    model=os.environ["AGENT_MODEL"],
    tools=[get_weather, get_population],
    response_format=Answer,
)
result = agent.invoke({"messages": [{"role": "user", "content": "Summarize Tokyo."}]})
print(result["structured_response"])  # Answer(summary=..., confidence=...)
```

### `create_agent` vs `StateGraph`

| Need | Use |
|------|-----|
| Standard loop: model, tools, repeat | `create_agent` with middleware |
| Cross-cutting concerns: summarization, approvals, retries, guardrails, dynamic prompts | Middleware |
| Custom topology: routing, parallel fan-out, deterministic steps between agents | LangGraph `StateGraph` (agents can be nodes) |

## Legacy: `AgentExecutor`

:::warning Legacy
`AgentExecutor`, `create_tool_calling_agent`, and `create_react_agent` (LangChain's text-parsing variant) are no longer part of the `langchain` v1 namespace. They are available from `langchain_classic.agents` for existing code only. Do not use them for new projects.
:::

<details>
<summary>Legacy example (pre-v1, kept for recognizing old code)</summary>

```python
# illustrative
# pip install langchain-classic
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

agent = create_tool_calling_agent(llm, tools, prompt)  # prompt needs an {agent_scratchpad} placeholder
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
result = executor.invoke({"input": "What's the weather and population of Tokyo?"})
```

</details>

## Retrieval-Augmented Generation (RAG)

LangChain provides first-class support for RAG pipelines.

```python
import os

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Build a retriever from documents
# AGENT_EMBEDDINGS is "<provider>:<embedding-model>"
embeddings = init_embeddings(os.environ["AGENT_EMBEDDINGS"])
vectorstore = InMemoryVectorStore.from_texts(
    ["LangChain is a framework for LLM apps.",
     "Agents use tools to interact with the world.",
     "RAG grounds LLM responses in real data."],
    embeddings,
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# RAG chain with LCEL
prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer based on context:\n{context}"),
    ("human", "{question}"),
])

rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | init_chat_model(os.environ["AGENT_MODEL"])
    | StrOutputParser()
)

answer = rag_chain.invoke("What is RAG?")
```

## Pros and Cons

### Strengths

- **Massive ecosystem**: hundreds of integrations (mostly separate partner packages) covering vector stores, LLM providers, tools, and document loaders.
- **LCEL composability**: Declarative chaining that keeps code readable and maintainable.
- **Production tooling**: LangSmith provides tracing, evaluation, and monitoring out of the box.
- **Active community**: Frequent releases, extensive documentation, and a large contributor base.

### Weaknesses

- **Abstraction overhead**: Multiple layers of abstraction can make debugging harder when things go wrong.
- **Rapid API churn**: The framework evolves quickly; v1 moved legacy chains and `AgentExecutor` to `langchain-classic`, so older tutorials often use removed imports.
- **Complex agent control flow**: For custom branching topologies, drop down to LangGraph (covered next); `create_agent` already runs on it.
- **Performance**: The abstraction layers add latency compared to direct API calls.

:::tip When to Choose LangChain
LangChain excels when you need **rapid prototyping**, **broad integrations**, or **straightforward chains and RAG pipelines**. For custom orchestration topologies, use LangGraph `StateGraph` directly (agents built with `create_agent` can be nodes in it).
:::

## Interview Talking Points

- Explain the difference between a **chain** (deterministic sequence) and an **agent** (LLM-decided tool calls).
- Describe how LCEL's pipe operator composes `Runnable` objects with a shared `invoke/stream/batch` interface.
- Discuss the trade-off between LangChain's convenience and the debugging complexity of deep abstraction layers.
- Explain why `create_agent` plus middleware replaced `AgentExecutor` and `langgraph.prebuilt.create_react_agent`, and what moved to `langchain-classic`.
- Compare `create_agent` middleware (cross-cutting hooks on a standard loop) with a custom `StateGraph` (custom topology).
- Describe `ProviderStrategy` vs `ToolStrategy` for structured output and when each is chosen.
