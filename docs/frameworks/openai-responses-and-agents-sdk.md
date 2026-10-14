---
sidebar_position: 7
title: "OpenAI Responses and Agents SDK"
last_verified: 2026-10-12
---

# OpenAI Responses and Agents SDK

**Verified against official documentation: 2026-10-12.** Three different layers matter: the **Responses API** generates output and tool calls, the **Conversations API** stores conversation items, and the **Agents SDK** orchestrates an agent loop in your application. They are not interchangeable names for a hosted assistant.

:::warning Assistants API has been sunset
OpenAI's [migration guide](https://developers.openai.com/api/docs/assistants/migration) states that the Assistants API was sunset on **August 26, 2026** and is no longer available. Use Responses for new integrations; migrate existing Assistants integrations rather than copying `client.beta.assistants` examples.
:::

## Core Concepts

| Layer | Responsibility | Application responsibility |
|-------|----------------|----------------------------|
| Responses API | Accepts input items; produces output items, including text and tool calls | Supply instructions/tools, inspect output, execute custom functions, handle errors |
| Conversations API | Persists items such as messages, tool calls, and tool outputs across Responses requests | Bind conversations to authorized users; manage retention and lifecycle |
| Agents SDK | Agents, tools, handoffs, guardrails, sessions, and tracing; a runner coordinates model/tool turns | Deploy the runtime, secure tools, select a memory strategy, evaluate behavior |

A response is not necessarily a single text message. `response.output_text` is a convenience for text output; a tool-using application must inspect the other output items too.

## Responses: A Minimal Request

All Python snippets on this page are **illustrative and untested**. Set `AGENT_MODEL` to a model available to your account and compatible with the selected API/tools; set the provider's required credentials separately (for OpenAI, `OPENAI_API_KEY`). No model IDs or prices are assumed.

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
import os
from openai import OpenAI

client = OpenAI()
response = client.responses.create(
    model=os.environ["AGENT_MODEL"],
    instructions="Explain concepts clearly and state uncertainty.",
    input="How does retrieval differ from conversation memory?",
)
print(response.output_text)
```

### Tool Calling Is an Application Loop

For a custom function, the model emits a `function_call` item. Your application validates the arguments, checks authorization, executes the function, and sends back a `function_call_output` with the matching `call_id`. Continue until a final result or an application-defined stopping condition. Do not confuse this with hosted tools such as file search or code interpreter: their execution and configuration are tool-specific.

- Use the [function-calling guide](https://developers.openai.com/api/docs/guides/function-calling) for the actual schema and result format.
- Bound tool calls, execution time, retries, and spend; make writes idempotent.
- Treat retrieved text and tool outputs as untrusted data, not privileged instructions.
- File search requires retrieval resources and access controls; code execution requires an explicit security boundary. A tool's presence does not make every model compatible with it.

## Conversations and Other State Strategies

The [conversation-state guide](https://developers.openai.com/api/docs/guides/conversation-state) documents three choices:

1. **Manual history**: supply the relevant input/output items yourself. You own persistence and context trimming.
2. **Response chaining**: send `previous_response_id` to continue from an earlier response.
3. **Conversations**: create a durable conversation and use it across Responses calls. Input and output items are added to the conversation.

**Illustrative, untested conversation example:**

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
import os
from openai import OpenAI

client = OpenAI()
conversation = client.conversations.create()

first = client.responses.create(
    model=os.environ["AGENT_MODEL"],
    conversation=conversation.id,
    instructions="You are a concise study tutor.",
    input="Explain checkpointing in an agent workflow.",
)
second = client.responses.create(
    model=os.environ["AGENT_MODEL"],
    conversation=conversation.id,
    instructions="You are a concise study tutor.",
    input="How is that different from storing chat history?",
)
print(second.output_text)
```

Choose a state strategy deliberately rather than layering all of them together. Persist actual returned identifiers, never fabricated IDs. Conversation persistence does not imply unlimited model context, free history, or workflow checkpointing. Review current [data controls](https://developers.openai.com/api/docs/guides/your-data) and your deletion requirements before storing sensitive content.

## Agents SDK

The [Python Agents SDK](https://openai.github.io/openai-agents-python/) is installed as `openai-agents` and imported through `agents`. Its runner handles the model/tool loop; **handoffs** transfer control to another agent, while an agent exposed as a tool returns a result to the caller. Guardrails and tracing are orchestration features, not substitutes for tool authorization or evaluation.

**Illustrative, untested SDK example:**

```python
# Illustrative, untested: needs provider credentials / your own data; not run in CI.
import asyncio
import os
from agents import Agent, Runner, function_tool

@function_tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers without external side effects."""
    return a * b

agent = Agent(
    name="Study tutor",
    model=os.environ["AGENT_MODEL"],
    instructions="Use the multiplication tool for arithmetic.",
    tools=[multiply],
)

async def main():
    result = await Runner.run(agent, "What is 12 times 7?")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

For subsequent turns, the SDK documents manual `result.to_input_list()`, SDK sessions, or OpenAI-managed state through `conversation_id` / `previous_response_id`. Choose one according to portability and persistence requirements. An SDK session manages conversational history; it is not automatically a checkpoint of arbitrary application work. Review trace content before exporting it.

## Migration from Assistants

OpenAI's mapping is conceptual, **not a drop-in rename**:

| Former Assistants concept | Responses-era concept | Migration work |
|---------------------------|------------------------|----------------|
| Assistant | Prompt/configuration | Move model, instructions, and tools to request configuration or a versioned prompt |
| Thread | Conversation | Rebuild relevant history as conversation items; preserve application ownership mapping |
| Message | Item | Handle text, tool calls, and tool outputs rather than assuming text-only messages |
| Run | Response | Replace run creation/polling with Responses handling and an explicit custom-tool loop |
| Run step | Item | Update logging and UI to consume output items and streaming events |

### Migration Checklist

1. Inventory instructions, function schemas, files/vector stores, stored thread references, run polling, and UI event handling.
2. Choose direct Responses or the Agents SDK. The SDK is useful when you want runner-managed tools, handoffs, sessions, and tracing; it is not required for Responses.
3. Create and version the new configuration. Translate tool schemas using the current Responses guide; do not blindly reuse a Chat Completions or Assistants payload.
4. Reconstruct only history you have retained and are authorized to migrate. Do not assume old thread IDs are conversation IDs or that retired endpoints can export missing data.
5. Replace `requires_action` / submit-tool-output logic with Responses items or SDK tools. Recheck hosted-tool resources and compatibility.
6. Test tool success/failure, cancellation, streaming, context growth, retries, user isolation, and deletion. Compare representative tasks with your recorded baseline before rollout.

## Trade-offs and Interview Talking Points

- **Direct Responses vs. SDK**: explicit application control versus a reusable orchestration loop.
- **Conversation vs. workflow state**: stored context is not a resumable business transaction.
- **Hosted vs. custom tools**: explain who executes each tool and where authorization happens.
- **Handoff vs. agent-as-tool**: explain which agent retains control after delegation.
- **Migration safety**: describe history reconstruction, idempotency, evaluation, and rollback without assuming retired API availability.

## Official Sources

Checked **2026-10-12**: [Assistants migration](https://developers.openai.com/api/docs/assistants/migration), [text generation](https://developers.openai.com/api/docs/guides/text), [conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [function calling](https://developers.openai.com/api/docs/guides/function-calling), [Agents SDK overview](https://openai.github.io/openai-agents-python/), and [SDK quickstart](https://openai.github.io/openai-agents-python/quickstart/).
