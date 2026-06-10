---
sidebar_position: 7
title: "OpenAI Assistants API"
---

# OpenAI Assistants API

The OpenAI Assistants API is a managed, stateful agent runtime provided directly by OpenAI. Unlike the stateless Chat Completions API, the Assistants API handles conversation state, tool execution, and file management on OpenAI's servers. This makes it the fastest path to a production agent if you are committed to the OpenAI ecosystem.

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Assistant** | A configured agent with instructions, a model, and tools |
| **Thread** | A conversation session that persists messages across interactions |
| **Message** | A single user or assistant message within a thread |
| **Run** | An execution of the assistant on a thread, processing messages and calling tools |
| **Run Step** | A granular record of each action taken during a run |

### How These Fit Together

```
User creates a Thread
  -> Adds Messages to the Thread
    -> Creates a Run (assistant processes the thread)
      -> Run generates Run Steps (tool calls, message creation)
        -> Run completes with a final assistant Message
```

## Creating an Assistant

```python
from openai import OpenAI

client = OpenAI()

assistant = client.beta.assistants.create(
    name="Data Analyst",
    instructions="""You are an expert data analyst. When given data or 
    questions about data, write and execute Python code to perform the 
    analysis. Always create visualizations when appropriate. Explain your 
    findings clearly and provide actionable insights.""",
    model="gpt-4o",
    tools=[
        {"type": "code_interpreter"},
        {"type": "file_search"},
    ],
    temperature=0,
    metadata={"team": "analytics", "version": "1.0"},
)

print(f"Assistant ID: {assistant.id}")
```

:::info Persistent Assistants
Assistants are persistent objects stored on OpenAI's servers. You create them once and reference them by ID in subsequent API calls. This is different from the Chat Completions API, where you configure the model on every request.
:::

## Threads and Messages

Threads represent conversations. They persist independently of runs, so you can continue a conversation days later.

```python
# Create a new thread
thread = client.beta.threads.create()

# Add a user message
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="Analyze the sales data I uploaded and identify the top 3 trends.",
)

# Add a message with a file attachment
message_with_file = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="Here is the Q3 sales data.",
    attachments=[
        {
            "file_id": uploaded_file.id,
            "tools": [{"type": "file_search"}],
        }
    ],
)
```

### Retrieving Conversation History

```python
messages = client.beta.threads.messages.list(
    thread_id=thread.id,
    order="asc",
)

for msg in messages.data:
    role = msg.role
    for block in msg.content:
        if block.type == "text":
            print(f"{role}: {block.text.value}")
        elif block.type == "image_file":
            print(f"{role}: [Image: {block.image_file.file_id}]")
```

## Runs

A run triggers the assistant to process the current thread messages. This is where the reasoning, tool calling, and response generation happen.

```python
run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id,
    instructions="Focus on year-over-year comparisons.",  # Override instructions
    max_completion_tokens=4096,
    max_prompt_tokens=16000,
)
```

### Run Lifecycle

A run transitions through several states:

| Status | Description |
|--------|-------------|
| `queued` | Run is waiting to be processed |
| `in_progress` | The assistant is actively reasoning and generating |
| `requires_action` | The assistant wants to call a function; your code must handle it |
| `completed` | The run finished successfully |
| `failed` | An error occurred during execution |
| `cancelled` | The run was cancelled by the user |
| `expired` | The run timed out (function call not handled within 10 minutes) |

### Polling for Completion

```python
import time

run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id,
)

while run.status in ["queued", "in_progress"]:
    time.sleep(1)
    run = client.beta.threads.runs.retrieve(
        thread_id=thread.id,
        run_id=run.id,
    )
    print(f"Status: {run.status}")

if run.status == "completed":
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    print(messages.data[0].content[0].text.value)
elif run.status == "failed":
    print(f"Run failed: {run.last_error}")
```

:::tip Use create_and_poll
The SDK provides a convenience method that handles polling automatically:
```python
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=assistant.id,
)
```
:::

## Code Interpreter

The Code Interpreter tool runs Python code in a sandboxed environment on OpenAI's servers. It can process uploaded files, generate charts, perform calculations, and return both text and image outputs.

```python
# Upload a file for analysis
file = client.files.create(
    file=open("sales_data.csv", "rb"),
    purpose="assistants",
)

# Create assistant with code interpreter
analyst = client.beta.assistants.create(
    name="CSV Analyst",
    instructions="Analyze CSV files using Python. Always create visualizations.",
    model="gpt-4o",
    tools=[{"type": "code_interpreter"}],
    tool_resources={
        "code_interpreter": {
            "file_ids": [file.id],
        }
    },
)

thread = client.beta.threads.create()
client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="Create a bar chart of monthly revenue and identify anomalies.",
)

run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=analyst.id,
)

# Retrieve results including generated images
messages = client.beta.threads.messages.list(thread_id=thread.id)
for msg in messages.data:
    for block in msg.content:
        if block.type == "image_file":
            # Download the generated chart
            image_data = client.files.content(block.image_file.file_id)
            with open("chart.png", "wb") as f:
                f.write(image_data.read())
```

## File Search

File Search enables the assistant to search through uploaded documents using an automatically managed vector store.

```python
# Create a vector store
vector_store = client.vector_stores.create(name="Company Knowledge Base")

# Upload files to the vector store
file_paths = ["handbook.pdf", "policies.pdf", "faq.pdf"]
file_streams = [open(path, "rb") for path in file_paths]

file_batch = client.vector_stores.file_batches.upload_and_poll(
    vector_store_id=vector_store.id,
    files=file_streams,
)

# Attach vector store to assistant
assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={
        "file_search": {
            "vector_store_ids": [vector_store.id],
        }
    },
)
```

:::info Automatic Chunking and Embedding
File Search automatically chunks documents, generates embeddings, and builds a searchable index. You do not need to manage chunking strategies, embedding models, or vector databases. This is handled entirely by OpenAI's infrastructure.
:::

## Function Calling

Function calling lets you extend the assistant with custom tools that execute in your own environment.

```python
import json

# Define the assistant with custom functions
assistant = client.beta.assistants.create(
    name="Booking Assistant",
    instructions="Help users book meeting rooms and check availability.",
    model="gpt-4o",
    tools=[
        {
            "type": "function",
            "function": {
                "name": "check_room_availability",
                "description": "Check if a meeting room is available at a given time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "room_name": {
                            "type": "string",
                            "description": "Name of the meeting room",
                        },
                        "date": {
                            "type": "string",
                            "description": "Date in YYYY-MM-DD format",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time in HH:MM format",
                        },
                    },
                    "required": ["room_name", "date", "start_time"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "book_room",
                "description": "Book a meeting room for a specified time slot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "room_name": {"type": "string"},
                        "date": {"type": "string"},
                        "start_time": {"type": "string"},
                        "duration_minutes": {"type": "integer"},
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["room_name", "date", "start_time", "duration_minutes"],
                },
            },
        },
    ],
)

# Handle function calls during a run
def handle_requires_action(run, thread_id):
    tool_outputs = []

    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
        args = json.loads(tool_call.function.arguments)

        if tool_call.function.name == "check_room_availability":
            result = check_availability(args["room_name"], args["date"], args["start_time"])
        elif tool_call.function.name == "book_room":
            result = book_meeting_room(**args)
        else:
            result = json.dumps({"error": "Unknown function"})

        tool_outputs.append({
            "tool_call_id": tool_call.id,
            "output": json.dumps(result),
        })

    # Submit results back to the run
    run = client.beta.threads.runs.submit_tool_outputs_and_poll(
        thread_id=thread_id,
        run_id=run.id,
        tool_outputs=tool_outputs,
    )
    return run
```

## Streaming

Streaming delivers assistant responses token-by-token and provides real-time visibility into tool execution.

```python
from openai import AssistantEventHandler

class MyEventHandler(AssistantEventHandler):
    def on_text_created(self, text):
        print("\nassistant > ", end="", flush=True)

    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)

    def on_tool_call_created(self, tool_call):
        print(f"\n[Tool: {tool_call.type}]", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == "code_interpreter" and delta.code_interpreter:
            if delta.code_interpreter.input:
                print(delta.code_interpreter.input, end="", flush=True)

# Stream the run
with client.beta.threads.runs.stream(
    thread_id=thread.id,
    assistant_id=assistant.id,
    event_handler=MyEventHandler(),
) as stream:
    stream.until_done()
```

:::warning Cost and Latency
The Assistants API charges for token usage like the Chat Completions API, but also charges for Code Interpreter sessions and File Search queries. Threads persist on OpenAI servers, meaning OpenAI manages (and charges for) the storage. Monitor usage carefully in production.
:::

## Pros and Cons

### Strengths

- **Managed state**: Thread and message persistence handled by OpenAI -- no database needed.
- **Built-in tools**: Code Interpreter and File Search work out of the box with no infrastructure.
- **Simple API**: Fewer abstractions than LangChain; the API surface is small and well-documented.
- **Reliable function calling**: Native, well-tested implementation from the model provider.
- **Streaming**: First-class streaming with granular event types.

### Weaknesses

- **Vendor lock-in**: Exclusively tied to OpenAI models and infrastructure.
- **No multi-agent**: Single-assistant architecture; no built-in support for agent collaboration.
- **Limited customization**: Cannot customize retrieval strategies, chunking, or embedding models for File Search.
- **Latency**: Run creation and polling add latency compared to direct Chat Completions calls.
- **Cost opacity**: Code Interpreter sessions and file storage costs can be surprising.
- **Beta status**: The API is still in beta and subject to breaking changes.

:::tip When to Choose the Assistants API
Choose the Assistants API when you want the **fastest path to a working agent** with minimal infrastructure, are already committed to OpenAI, and your use case fits a **single-assistant** model. For multi-agent systems, complex control flow, or provider flexibility, use LangGraph or CrewAI instead.
:::

## Interview Talking Points

- Explain the difference between the **Chat Completions API** (stateless) and the **Assistants API** (stateful).
- Walk through the **Run lifecycle** and what happens at each status transition.
- Describe how **function calling** creates a contract between the assistant and your application code.
- Discuss the **trade-offs of managed state** -- convenience vs. vendor lock-in and cost.
- Compare the Assistants API's **File Search** with building your own RAG pipeline using LlamaIndex or LangChain.
