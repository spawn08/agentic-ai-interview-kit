---
sidebar_position: 4
title: "LangGraph Stateful Workflow"
description: "Production-grade LangGraph workflow with parallel execution, PostgreSQL persistence, error recovery, streaming, and subgraph composition."
---

# LangGraph Stateful Workflow

This implementation builds a **production-grade, stateful workflow** using LangGraph. The workflow processes customer support tickets through classification, parallel enrichment, response generation, and quality checking -- with PostgreSQL persistence, error recovery, streaming, and subgraph composition.

:::info Why LangGraph for Workflows?
LangGraph makes execution flow explicit as a typed graph. Every node, edge, and conditional is visible and testable. Combined with checkpointing, you get crash recovery, time-travel debugging, and human-in-the-loop -- capabilities that plain LangChain agents lack.
:::

---

## Workflow Architecture

```mermaid
graph TD
    A[START] --> B[classify_ticket]
    B --> C{route_by_priority}
    C -->|critical| D[escalate_to_human]
    C -->|high| E[senior_agent_response]
    C -->|medium/low| F[auto_response_agent]
    D --> L[END]
    E --> G[quality_check]
    F --> G
    G --> H{route_by_quality}
    H -->|pass| I[send_response]
    H -->|fail & retries left| J[revise_response]
    H -->|fail & max retries| I
    J --> G
    I --> K[log_and_close]
    K --> L[END]
```

---

## Install Dependencies

```bash
pip install langgraph langchain-openai langchain-core pydantic psycopg2-binary
```

---

## Step 1: Define the State Schema

```python
"""state.py -- State schema for the support ticket workflow."""

from __future__ import annotations

from typing import Annotated, Literal, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class TicketState(BaseModel):
    """Typed state flowing through the support ticket workflow.

    Fields are organized by lifecycle: input, classification,
    processing, quality, and output.
    """

    # -- Input --
    ticket_id: str = Field(description="Unique ticket identifier.")
    customer_name: str = ""
    customer_email: str = ""
    subject: str = ""
    body: str = ""

    # -- Classification --
    category: str = Field(default="general")
    priority: Literal["critical", "high", "medium", "low"] = Field(default="medium")
    sentiment: str = Field(default="neutral")

    # -- Processing --
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(
        default_factory=list,
    )
    draft_response: str = ""
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_feedback: str = ""
    revision_count: int = 0

    # -- Output --
    final_response: str = ""
    resolution_status: str = "open"
    escalated: bool = False

    class Config:
        arbitrary_types_allowed = True
```

:::tip Why Pydantic Validation on State?
The `ge=0.0, le=1.0` constraint on `quality_score` catches invalid scores at the boundary of each node. This prevents a downstream node from seeing a `quality_score` of 5.0 and making a bad routing decision.
:::

---

## Step 2: Build the Graph Nodes

```python
"""nodes.py -- All graph nodes for the support ticket workflow."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from state import TicketState

logger = logging.getLogger(__name__)

llm = ChatOpenAI(model="gpt-4o", temperature=0.0)


class Classification(BaseModel):
    """Structured output for ticket classification."""
    category: str = Field(description="billing, technical, account, or general")
    priority: str = Field(description="critical, high, medium, or low")
    sentiment: str = Field(description="positive, neutral, negative, or angry")


class QualityAssessment(BaseModel):
    """Structured output for quality checking."""
    score: float = Field(ge=0.0, le=1.0, description="Quality score 0.0-1.0")
    feedback: str = Field(description="Specific improvement suggestions")


async def classify_ticket(state: TicketState) -> dict[str, Any]:
    """Classify the ticket by category, priority, and sentiment."""
    logger.info("Classifying ticket %s", state.ticket_id)

    structured_llm = llm.with_structured_output(Classification)
    classification = await structured_llm.ainvoke([
        SystemMessage(content=(
            "Classify this support ticket. Rules:\n"
            "- critical: data loss, security breach, complete outage\n"
            "- high: significant feature broken, billing overcharge\n"
            "- medium: minor bug, feature request\n"
            "- low: feedback, documentation, cosmetic"
        )),
        HumanMessage(content=f"Subject: {state.subject}\nBody: {state.body}"),
    ])

    return {
        "category": classification.category,
        "priority": classification.priority,
        "sentiment": classification.sentiment,
        "revision_count": 0,
        "escalated": False,
    }


async def escalate_to_human(state: TicketState) -> dict[str, Any]:
    """Mark the ticket for immediate human escalation."""
    logger.warning("Escalating ticket %s (priority=%s)", state.ticket_id, state.priority)
    return {
        "escalated": True,
        "draft_response": (
            f"ESCALATION: Ticket {state.ticket_id} flagged as {state.priority} "
            f"({state.category}). Customer: {state.customer_name}. "
            f"Sentiment: {state.sentiment}."
        ),
        "resolution_status": "escalated_to_human",
    }


async def senior_agent_response(state: TicketState) -> dict[str, Any]:
    """Generate a response for high-priority tickets."""
    logger.info("Senior agent handling ticket %s", state.ticket_id)
    response = await llm.ainvoke([
        SystemMessage(content=(
            "You are a senior support agent. Be empathetic and solution-oriented. "
            "Provide a clear action plan with timeline. Offer escalation if needed."
        )),
        HumanMessage(content=(
            f"Customer: {state.customer_name}\nCategory: {state.category}\n"
            f"Sentiment: {state.sentiment}\nSubject: {state.subject}\n"
            f"Body: {state.body}"
        )),
    ])
    return {"draft_response": response.content}


async def auto_response_agent(state: TicketState) -> dict[str, Any]:
    """Generate an automated response for medium/low-priority tickets."""
    logger.info("Auto-response for ticket %s", state.ticket_id)
    response = await llm.ainvoke([
        SystemMessage(content="You are a friendly support agent. Be concise and helpful."),
        HumanMessage(content=(
            f"Customer: {state.customer_name}\nSubject: {state.subject}\n"
            f"Body: {state.body}"
        )),
    ])
    return {"draft_response": response.content}


async def quality_check(state: TicketState) -> dict[str, Any]:
    """Evaluate the quality of the draft response."""
    logger.info("Quality checking ticket %s (revision %d)", state.ticket_id, state.revision_count)

    structured_llm = llm.with_structured_output(QualityAssessment)
    assessment = await structured_llm.ainvoke([
        SystemMessage(content=(
            "You are a QA specialist. Evaluate this support response on: "
            "accuracy, tone, completeness, professionalism. Be strict."
        )),
        HumanMessage(content=(
            f"Customer ticket: {state.subject}\n{state.body}\n\n"
            f"Draft response:\n{state.draft_response}"
        )),
    ])
    return {"quality_score": assessment.score, "quality_feedback": assessment.feedback}


async def revise_response(state: TicketState) -> dict[str, Any]:
    """Revise the draft response based on quality feedback."""
    logger.info("Revising ticket %s (attempt %d)", state.ticket_id, state.revision_count + 1)
    response = await llm.ainvoke([
        SystemMessage(content="Revise this support response based on the feedback."),
        HumanMessage(content=(
            f"Original:\n{state.draft_response}\n\n"
            f"Feedback:\n{state.quality_feedback}\n\n"
            f"Customer context: {state.subject} (sentiment: {state.sentiment})"
        )),
    ])
    return {"draft_response": response.content, "revision_count": state.revision_count + 1}


async def send_response(state: TicketState) -> dict[str, Any]:
    """Finalize the response for delivery."""
    logger.info("Sending response for ticket %s (quality=%.2f)", state.ticket_id, state.quality_score)
    return {"final_response": state.draft_response, "resolution_status": "resolved"}


async def log_and_close(state: TicketState) -> dict[str, Any]:
    """Log the ticket resolution for audit trail."""
    logger.info(
        "Ticket %s closed | status=%s quality=%.2f revisions=%d",
        state.ticket_id, state.resolution_status,
        state.quality_score, state.revision_count,
    )
    return {}
```

---

## Step 3: Define Routing Logic

```python
"""routing.py -- Conditional edge functions for the workflow graph."""

from __future__ import annotations

from state import TicketState

QUALITY_THRESHOLD = 0.75
MAX_REVISIONS = 3


def route_by_priority(state: TicketState) -> str:
    """Route based on classified priority."""
    if state.priority == "critical":
        return "escalate"
    if state.priority == "high":
        return "senior"
    return "auto"


def route_by_quality(state: TicketState) -> str:
    """Route based on quality score and revision count."""
    if state.quality_score >= QUALITY_THRESHOLD:
        return "send"
    if state.revision_count >= MAX_REVISIONS:
        return "send"
    return "revise"
```

:::warning Cycles Need Exit Conditions
The `revise_response -> quality_check` loop creates a cycle. Without `MAX_REVISIONS`, the graph could loop indefinitely. Always include exit conditions for cycles.
:::

---

## Step 4: Assemble the Graph

```python
"""graph.py -- Build and compile the support ticket workflow graph."""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import TicketState
from nodes import (
    classify_ticket, escalate_to_human, senior_agent_response,
    auto_response_agent, quality_check, revise_response,
    send_response, log_and_close,
)
from routing import route_by_priority, route_by_quality


def build_workflow(checkpointer=None):
    """Construct and compile the support ticket workflow graph.

    Args:
        checkpointer: State persistence backend. Defaults to MemorySaver.

    Returns:
        A compiled LangGraph application.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = StateGraph(TicketState)

    # -- Nodes --
    graph.add_node("classify_ticket", classify_ticket)
    graph.add_node("escalate_to_human", escalate_to_human)
    graph.add_node("senior_agent_response", senior_agent_response)
    graph.add_node("auto_response_agent", auto_response_agent)
    graph.add_node("quality_check", quality_check)
    graph.add_node("revise_response", revise_response)
    graph.add_node("send_response", send_response)
    graph.add_node("log_and_close", log_and_close)

    # -- Edges --
    graph.add_edge(START, "classify_ticket")

    graph.add_conditional_edges(
        "classify_ticket",
        route_by_priority,
        {"escalate": "escalate_to_human", "senior": "senior_agent_response", "auto": "auto_response_agent"},
    )

    graph.add_edge("escalate_to_human", END)
    graph.add_edge("senior_agent_response", "quality_check")
    graph.add_edge("auto_response_agent", "quality_check")

    graph.add_conditional_edges(
        "quality_check",
        route_by_quality,
        {"send": "send_response", "revise": "revise_response"},
    )

    graph.add_edge("revise_response", "quality_check")
    graph.add_edge("send_response", "log_and_close")
    graph.add_edge("log_and_close", END)

    return graph.compile(checkpointer=checkpointer)
```

---

## Step 5: Streaming Execution

```python
"""stream.py -- Stream workflow execution with real-time observability."""

import asyncio
import logging

from graph import build_workflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


async def stream_ticket(ticket_data: dict) -> dict:
    """Process a ticket with streaming output for each node.

    Args:
        ticket_data: Initial ticket state fields.

    Returns:
        The final workflow state.
    """
    app = build_workflow()
    config = {"configurable": {"thread_id": ticket_data["ticket_id"]}}

    print(f"Processing ticket: {ticket_data['ticket_id']}")
    print("=" * 60)

    final_state = {}
    async for step in app.astream(ticket_data, config=config):
        node_name = list(step.keys())[0]
        node_output = step[node_name]
        print(f"\n[Node: {node_name}]")

        for key, value in node_output.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}...")
            elif key not in ("messages",):
                print(f"  {key}: {value}")

        final_state = node_output

    return final_state


async def main() -> None:
    await stream_ticket({
        "ticket_id": "TKT-001",
        "customer_name": "Alice Johnson",
        "customer_email": "alice@example.com",
        "subject": "URGENT: Unauthorized access to my account",
        "body": (
            "I received notifications about logins from unrecognized IPs. "
            "Someone changed my email. This is a security breach."
        ),
    })

    print("\n" + "=" * 60 + "\n")

    await stream_ticket({
        "ticket_id": "TKT-002",
        "customer_name": "Bob Smith",
        "customer_email": "bob@example.com",
        "subject": "Question about my last invoice",
        "body": "I noticed a $49.99 charge I do not recognize. My plan is $29.99/month.",
    })


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Step 6: PostgreSQL Persistence

```python
"""persistence.py -- PostgreSQL checkpointer for production persistence."""

from __future__ import annotations

import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from graph import build_workflow
from state import TicketState


async def build_with_postgres(connection_string: str):
    """Build the workflow with PostgreSQL-backed persistence.

    Args:
        connection_string: PostgreSQL connection string, e.g.
            ``postgresql://user:pass@localhost:5432/langgraph``

    Returns:
        A compiled graph with durable checkpointing.
    """
    async with AsyncPostgresSaver.from_conn_string(connection_string) as saver:
        await saver.setup()
        return build_workflow(checkpointer=saver)


async def demonstrate_persistence() -> None:
    """Show checkpoint replay and time-travel debugging."""
    from langgraph.checkpoint.memory import MemorySaver

    app = build_workflow(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "TKT-PERSIST-001"}}

    result = await app.ainvoke(
        {
            "ticket_id": "TKT-PERSIST-001",
            "customer_name": "Charlie Brown",
            "customer_email": "charlie@example.com",
            "subject": "Feature request: dark mode",
            "body": "Would love a dark mode option in the dashboard.",
        },
        config=config,
    )

    # Time-travel: inspect all historical snapshots
    history = []
    async for snapshot in app.aget_state_history(config):
        history.append(snapshot)

    print(f"Workflow produced {len(history)} state snapshots.")
    for i, snap in enumerate(history[:5]):
        print(f"  Snapshot {i}: source={snap.metadata.get('source', 'unknown')}")


if __name__ == "__main__":
    asyncio.run(demonstrate_persistence())
```

:::info PostgreSQL for Production
`MemorySaver` is for development only. In production, use `AsyncPostgresSaver` (or `SqliteSaver`) so that state survives process restarts, and multiple workers can share checkpoints.
:::

---

## Step 7: Error Recovery with Retry

```python
"""retry.py -- Retry wrapper for fault-tolerant node execution."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


def with_retry(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator that adds exponential backoff retry to async graph nodes.

    Args:
        max_retries: Maximum number of attempts.
        backoff_base: Base delay in seconds (doubles each attempt).
        retry_on: Exception types that trigger a retry.
    """
    def decorator(fn: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries):
                try:
                    return await fn(*args, **kwargs)
                except retry_on as exc:
                    if attempt == max_retries - 1:
                        logger.error("Node %s failed after %d retries: %s", fn.__name__, max_retries, exc)
                        raise
                    wait = backoff_base * (2 ** attempt)
                    logger.warning(
                        "Node %s attempt %d failed: %s. Retrying in %.1fs",
                        fn.__name__, attempt + 1, exc, wait,
                    )
                    await asyncio.sleep(wait)
        return wrapper
    return decorator
```

---

## Key Takeaways for Interviews

:::tip Interview Talking Points
1. **LangGraph makes control flow explicit.** Unlike implicit agent loops, you see and test every path through the workflow.
2. **State reducers** control how concurrent updates merge. The `add_messages` reducer appends; without it, messages would be overwritten.
3. **Conditional edges enable dynamic routing** without sacrificing determinism. The routing function is pure Python, not an LLM call (though it can be).
4. **Checkpointing enables crash recovery and time-travel.** With PostgreSQL, state survives process restarts and can be replayed for debugging.
5. **Cycles with exit conditions** enable retry patterns. Always cap iterations to prevent infinite loops.
6. **Streaming** provides real-time observability into which nodes are executing and what state changes they produce.
7. **Subgraph composition** lets you build and test sub-workflows independently, then compose them into larger systems.
:::

---

## Deployment Considerations

| Concern | Solution |
|---|---|
| State persistence | PostgreSQL or Redis checkpointer |
| Horizontal scaling | Stateless workers + shared checkpointer |
| Observability | LangSmith tracing + structured logging |
| Error recovery | `with_retry` decorator on LLM nodes |
| Cost control | Token tracking in state + budget guards |
| Timeouts | `asyncio.wait_for` on node coroutines |
| Testing | Mock LLM + deterministic routing tests |
