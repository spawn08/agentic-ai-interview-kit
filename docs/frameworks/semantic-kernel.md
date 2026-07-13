---
sidebar_position: 5
title: "Semantic Kernel"
---

# Semantic Kernel

Semantic Kernel (SK) is Microsoft's open-source SDK for integrating large language models into applications. Originally designed for .NET, it now has full Python and Java SDKs. Semantic Kernel differentiates itself with a **plugin-centric architecture** and tight integration with the Azure ecosystem, making it a strong choice for enterprise applications.

## Architecture Overview

Semantic Kernel is built around a central **Kernel** object that orchestrates three key components:

| Component | Role |
|-----------|------|
| **Kernel** | The central orchestrator that manages services, plugins, and execution |
| **Plugins** | Collections of functions (semantic and native) the AI can use |
| **Planners** | Components that decompose goals into step-by-step plans using plugins |
| **Memory** | Semantic memory for storing and retrieving embeddings |
| **Connectors** | Integrations with AI services (OpenAI, Azure OpenAI, Hugging Face) |

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

# Create the kernel
kernel = Kernel()

# Add an AI service
kernel.add_service(
    OpenAIChatCompletion(
        service_id="chat",
        ai_model_id="gpt-4o",
    )
)
```

:::info Design Philosophy
Semantic Kernel follows the principle of being "AI-service agnostic." The same plugin code works whether you connect to OpenAI, Azure OpenAI, or a local model. The kernel abstracts away the provider, much like a dependency injection container.
:::

## Plugins

Plugins are the fundamental building blocks in Semantic Kernel. A plugin is a collection of related functions that an AI agent can call. There are two types of functions:

### Native Functions

Native functions are regular Python functions decorated with `@kernel_function`.

```python
from semantic_kernel.functions import kernel_function
from typing import Annotated

class MathPlugin:
    """A plugin for mathematical operations."""

    @kernel_function(
        name="add",
        description="Adds two numbers together",
    )
    def add(
        self,
        a: Annotated[float, "The first number"],
        b: Annotated[float, "The second number"],
    ) -> Annotated[float, "The sum"]:
        return a + b

    @kernel_function(
        name="multiply",
        description="Multiplies two numbers",
    )
    def multiply(
        self,
        a: Annotated[float, "The first number"],
        b: Annotated[float, "The second number"],
    ) -> Annotated[float, "The product"]:
        return a * b

# Register the plugin with the kernel
kernel.add_plugin(MathPlugin(), plugin_name="math")
```

### Semantic Functions (Prompt Functions)

Semantic functions are defined as prompt templates. They use the LLM itself as the implementation.

```python
from semantic_kernel.functions import KernelFunction
from semantic_kernel.prompt_template import PromptTemplateConfig

# Define a semantic function inline
summarize = KernelFunction.from_prompt(
    function_name="summarize",
    plugin_name="text",
    prompt="""Summarize the following text in exactly {{$num_sentences}} sentences.
    
    Text: {{$input}}
    
    Summary:""",
    template_format="semantic-kernel",
)

kernel.add_function(plugin_name="text", function=summarize)
```

You can also load semantic functions from files:

```
plugins/
  WriterPlugin/
    ShortPoem/
      skprompt.txt      # The prompt template
      config.json       # Model settings (temperature, max_tokens, etc.)
    BlogPost/
      skprompt.txt
      config.json
```

```python
# Load all functions from the directory
kernel.add_plugin(parent_directory="./plugins", plugin_name="WriterPlugin")
```

:::tip Plugin Design Principles
Follow the **single responsibility principle** for plugins. A `WeatherPlugin` should only have weather-related functions. A `MathPlugin` should only do math. This makes it easier for the AI planner to select the right functions and reduces confusion.
:::

## Planners and Automatic Function Calling

Planners break down a high-level user goal into a sequence of plugin function calls. Modern Semantic Kernel uses **automatic function calling** rather than explicit planners.

```python
import asyncio

from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory


async def main():
    # Configure automatic function calling
    settings = kernel.get_prompt_execution_settings_class("chat")()
    settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
        filters={"included_plugins": ["math", "text"]}
    )

    chat_history = ChatHistory()
    chat_history.add_user_message("What is 42 multiplied by 17, then summarize the result?")

    # The kernel automatically routes to the right plugin functions
    result = await kernel.invoke_prompt(
        prompt="{{$chat_history}}",
        chat_history=chat_history,
        settings=settings,
    )
    print(result)


asyncio.run(main())
```

### Step-by-Step Planner (Legacy)

For more explicit planning control, Semantic Kernel previously offered dedicated planner classes.

```python
import asyncio

from semantic_kernel.planners import SequentialPlanner


async def main():
    planner = SequentialPlanner(kernel)
    plan = await planner.create_plan("Write a haiku about AI and translate it to French")

    # The plan is a sequence of steps using registered plugins
    for step in plan.steps:
        print(f"Step: {step.plugin_name}.{step.name}")

    # Execute the plan
    result = await plan.invoke(kernel)


asyncio.run(main())
```

:::warning Planner Evolution
Explicit planners (SequentialPlanner, StepwisePlanner) are being phased out in favor of automatic function calling, which is more reliable and leverages the native tool-calling capabilities of modern LLMs. Use `FunctionChoiceBehavior.Auto()` for new projects.
:::

## Memory

Semantic Kernel's memory system stores and retrieves information using vector embeddings, enabling RAG-style patterns.

```python
import asyncio

from semantic_kernel.memory import SemanticTextMemory, VolatileMemoryStore
from semantic_kernel.connectors.ai.open_ai import OpenAITextEmbedding

# Configure memory with an embedding model and a store
embedding = OpenAITextEmbedding(ai_model_id="text-embedding-3-small")

# In-memory store for development
store = VolatileMemoryStore()
memory = SemanticTextMemory(storage=store, embeddings_generator=embedding)


async def main():
    # Save information
    await memory.save_information(
        collection="company_docs",
        id="doc1",
        text="Semantic Kernel supports plugins, planners, and memory.",
        description="SK overview",
    )
    await memory.save_information(
        collection="company_docs",
        id="doc2",
        text="Plugins can be native Python functions or prompt templates.",
        description="Plugin types",
    )

    # Retrieve relevant information
    results = await memory.search("company_docs", "How do plugins work?", limit=2)
    for result in results:
        print(f"[{result.relevance:.2f}] {result.text}")


asyncio.run(main())
```

## Building an Agent with Semantic Kernel

Here is a complete example of building a conversational agent with tools.

```python
import asyncio
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import kernel_function
from typing import Annotated

# --- Plugins ---
class WeatherPlugin:
    @kernel_function(description="Get current weather for a city")
    def get_weather(
        self, city: Annotated[str, "The city name"]
    ) -> str:
        weather_data = {
            "london": "15C, cloudy with light rain",
            "tokyo": "28C, sunny and humid",
            "new york": "22C, partly cloudy",
        }
        return weather_data.get(city.lower(), f"No data for {city}")

class RecommendationPlugin:
    @kernel_function(description="Get activity recommendations based on weather")
    def recommend_activities(
        self, weather: Annotated[str, "The weather description"]
    ) -> str:
        if "sunny" in weather.lower():
            return "Recommended: hiking, picnic, sightseeing, outdoor dining"
        elif "rain" in weather.lower():
            return "Recommended: museum visit, indoor market, cafe hopping"
        return "Recommended: walking tour, shopping, local cuisine exploration"

# --- Kernel Setup ---
async def main():
    kernel = Kernel()
    kernel.add_service(OpenAIChatCompletion(service_id="chat", ai_model_id="gpt-4o"))
    kernel.add_plugin(WeatherPlugin(), plugin_name="weather")
    kernel.add_plugin(RecommendationPlugin(), plugin_name="recommendations")

    settings = kernel.get_prompt_execution_settings_class("chat")()
    settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    chat_history = ChatHistory(
        system_message="You are a travel assistant. Use the available tools."
    )

    # Multi-turn conversation
    queries = [
        "What's the weather like in Tokyo?",
        "What should I do there given the weather?",
        "How about London instead?",
    ]

    for query in queries:
        chat_history.add_user_message(query)
        result = await kernel.invoke_prompt(
            prompt="{{$chat_history}}",
            chat_history=chat_history,
            settings=settings,
        )
        print(f"User: {query}")
        print(f"Agent: {result}\n")
        chat_history.add_assistant_message(str(result))

asyncio.run(main())
```

## Comparison with LangChain

| Dimension | Semantic Kernel | LangChain |
|-----------|----------------|-----------|
| **Primary language** | C# / .NET (Python, Java SDKs available) | Python (JS/TS SDK available) |
| **Architecture** | Plugin-centric with a central kernel | Chain/Runnable composition with LCEL |
| **Tool definition** | `@kernel_function` decorator | `@tool` decorator |
| **Planning** | Auto function calling / planners | Agent executors / LangGraph |
| **Memory** | Built-in semantic memory | Via vector store integrations |
| **Enterprise focus** | Strong Azure integration | Cloud-agnostic |
| **Community size** | Growing, Microsoft-backed | Largest in the LLM framework space |
| **Observability** | Azure Monitor integration | LangSmith |
| **Multi-agent** | Limited (agents via plugins) | LangGraph for full multi-agent |

:::info When to Choose Semantic Kernel
Semantic Kernel is the strongest choice when you are building on the **Microsoft/.NET stack**, need deep **Azure OpenAI integration**, or work in an enterprise environment that already uses Azure services. Its plugin model is clean and well-organized for large codebases.
:::

## Filters and Middleware

Semantic Kernel supports function invocation filters for cross-cutting concerns like logging, authentication, and rate limiting.

```python
from semantic_kernel.filters import FunctionInvocationContext

async def logging_filter(context: FunctionInvocationContext, next_handler):
    """Log every function call for observability."""
    print(f"Calling: {context.function.plugin_name}.{context.function.name}")
    print(f"Arguments: {context.arguments}")

    await next_handler(context)

    print(f"Result: {context.result}")

kernel.add_function_invocation_filter(logging_filter)
```

## Pros and Cons

### Strengths

- **Enterprise-ready**: Deep Azure integration, .NET-first design, Microsoft backing.
- **Clean plugin model**: Well-structured, testable, and composable.
- **Multi-language**: Full SDKs for C#, Python, and Java.
- **Automatic function calling**: Leverages native LLM tool-calling capabilities.

### Weaknesses

- **Smaller Python community**: Most production usage and examples are in C#.
- **Limited multi-agent support**: Not designed for complex multi-agent orchestration like LangGraph or AutoGen.
- **Azure-centric**: While it supports other providers, the best experience is on Azure.
- **Less flexible composition**: No equivalent to LCEL's pipe-based chain composition.

## Interview Talking Points

- Explain the difference between **native functions** and **semantic functions** in the plugin model.
- Describe how **automatic function calling** replaced explicit planners and why this is more reliable.
- Compare the **kernel/plugin** architecture with LangChain's **chain/tool** architecture.
- Discuss when you would choose Semantic Kernel over LangChain for an enterprise project.
- Explain how **filters** enable cross-cutting concerns without modifying plugin code.
