---
sidebar_position: 1
title: "LangChain"
---

# LangChain

LangChain is the most widely adopted framework for building applications powered by large language models. It provides a composable set of abstractions that let you connect LLMs to tools, data sources, and multi-step reasoning pipelines with minimal boilerplate.

## Core Abstractions

LangChain organizes its functionality around several foundational primitives. Understanding these is essential before building anything non-trivial.

### Models

LangChain wraps LLM providers behind a unified interface so you can swap providers without rewriting application logic.

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# Switch providers by changing one line
llm = ChatOpenAI(model="gpt-4o", temperature=0)
# llm = ChatAnthropic(model="claude-sonnet-4-20250514")

response = llm.invoke("Explain agentic AI in two sentences.")
print(response.content)
```

:::info Model Types
LangChain distinguishes between **LLMs** (raw text completion) and **Chat Models** (message-based). Modern applications almost always use Chat Models. The `ChatOpenAI` and `ChatAnthropic` classes are chat model wrappers.
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

### Output Parsers

Output parsers transform raw LLM text into structured Python objects.

```python
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
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful coding tutor."),
    ("human", "{question}"),
])

chain = prompt | ChatOpenAI(model="gpt-4o") | StrOutputParser()

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
| `langchain-core` | Base abstractions, LCEL, interfaces |
| `langchain-openai` | OpenAI and Azure OpenAI integrations |
| `langchain-anthropic` | Anthropic Claude integrations |
| `langchain-community` | Third-party integrations (300+) |
| `langchain` | Orchestration chains and higher-level logic |
| `langgraph` | Stateful, multi-actor agent graphs |
| `langsmith` | Observability, tracing, and evaluation |

## Building a Simple Agent

Agents use an LLM to decide which tools to call and when to stop.

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

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

tools = [get_weather, get_population]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful travel assistant."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

llm = ChatOpenAI(model="gpt-4o", temperature=0)
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({
    "input": "What's the weather and population of Tokyo?"
})
print(result["output"])
```

### Agent Execution Flow

1. The LLM receives the user query and available tool descriptions.
2. It decides to call `get_weather("Tokyo")` and `get_population("Tokyo")`.
3. Tool results are appended to the conversation as tool messages.
4. The LLM synthesizes a final answer from the tool outputs.
5. The `AgentExecutor` returns the final response.

## Retrieval-Augmented Generation (RAG)

LangChain provides first-class support for RAG pipelines.

```python
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Build a retriever from documents
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.from_texts(
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
    | ChatOpenAI(model="gpt-4o")
    | StrOutputParser()
)

answer = rag_chain.invoke("What is RAG?")
```

## Pros and Cons

### Strengths

- **Massive ecosystem**: 300+ integrations covering vector stores, LLM providers, tools, and document loaders.
- **LCEL composability**: Declarative chaining that keeps code readable and maintainable.
- **Production tooling**: LangSmith provides tracing, evaluation, and monitoring out of the box.
- **Active community**: Frequent releases, extensive documentation, and a large contributor base.

### Weaknesses

- **Abstraction overhead**: Multiple layers of abstraction can make debugging harder when things go wrong.
- **Rapid API churn**: The framework evolves quickly; code written three months ago may use deprecated patterns.
- **Complex agent control flow**: For multi-step agents with branching logic, LangGraph (covered next) is a better fit.
- **Performance**: The abstraction layers add latency compared to direct API calls.

:::tip When to Choose LangChain
LangChain excels when you need **rapid prototyping**, **broad integrations**, or **straightforward chains and RAG pipelines**. For complex agent orchestration with state management, consider LangGraph instead.
:::

## Interview Talking Points

- Explain the difference between a **chain** (deterministic sequence) and an **agent** (LLM-decided tool calls).
- Describe how LCEL's pipe operator composes `Runnable` objects with a shared `invoke/stream/batch` interface.
- Discuss the trade-off between LangChain's convenience and the debugging complexity of deep abstraction layers.
- Compare `AgentExecutor` (LangChain) with `StateGraph` (LangGraph) for stateful agent workflows.
