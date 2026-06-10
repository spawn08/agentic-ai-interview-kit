---
sidebar_position: 6
title: "Coding Challenges"
description: "8 hands-on coding problems for agentic AI interviews, from simple tool-calling loops to mini agent systems."
---

# Coding Challenges

These 8 problems test your ability to implement agentic AI concepts in code. They progress from fundamental building blocks to complete mini-systems. Each includes a problem statement, hints, and a collapsible solution.

:::tip How to Practice
Set a timer. Problems 1-4 should take 15-20 minutes each. Problems 5-8 should take 25-35 minutes each. Write working code, not pseudocode. Test it mentally by tracing through an example input.
:::

---

## Challenge 1: Implement a Tool Dispatcher

**Problem:** Write a `ToolDispatcher` class that registers tools (name, description, function) and dispatches calls based on a tool name and arguments string. Include error handling for unknown tools and execution failures.

**Hints:**
- Store tools in a dictionary mapping name to (description, function)
- Parse arguments from a JSON string
- Return informative error messages, not exceptions

<details>
<summary>View Solution</summary>

```python
import json
from typing import Callable, Any


class ToolDispatcher:
    """Register and dispatch tool calls with error handling."""

    def __init__(self):
        self._tools: dict[str, dict[str, Any]] = {}

    def register(self, name: str, description: str, fn: Callable) -> None:
        """Register a tool."""
        self._tools[name] = {"description": description, "fn": fn}

    def list_tools(self) -> list[dict[str, str]]:
        """Return tool names and descriptions for prompt injection."""
        return [
            {"name": name, "description": info["description"]}
            for name, info in self._tools.items()
        ]

    def dispatch(self, tool_name: str, args_json: str) -> str:
        """Execute a tool by name with JSON-encoded arguments.

        Returns the result string, or an error message.
        """
        if tool_name not in self._tools:
            available = ", ".join(self._tools.keys())
            return f"Error: Unknown tool '{tool_name}'. Available: [{available}]"

        try:
            args = json.loads(args_json) if args_json.strip() else {}
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON arguments: {e}"

        fn = self._tools[tool_name]["fn"]
        try:
            if isinstance(args, dict):
                result = fn(**args)
            elif isinstance(args, list):
                result = fn(*args)
            else:
                result = fn(args)
            return str(result)
        except TypeError as e:
            return f"Error: Argument mismatch for '{tool_name}': {e}"
        except Exception as e:
            return f"Error executing '{tool_name}': {type(e).__name__}: {e}"


# ── Usage Example ────────────────────────────────────────────────────────────

def add(a: float, b: float) -> float:
    return a + b

def search(query: str) -> str:
    return f"Results for: {query}"

dispatcher = ToolDispatcher()
dispatcher.register("add", "Add two numbers", add)
dispatcher.register("search", "Search for information", search)

assert dispatcher.dispatch("add", '{"a": 3, "b": 4}') == "7"
assert dispatcher.dispatch("search", '{"query": "AI agents"}') == "Results for: AI agents"
assert "Error: Unknown tool" in dispatcher.dispatch("unknown", "{}")
assert "Error: Invalid JSON" in dispatcher.dispatch("add", "not json")
print("All assertions passed.")
```

</details>

---

## Challenge 2: Parse ReAct Output

**Problem:** Write a function that parses an LLM's ReAct-format output and returns either an action (tool + input) or a final answer. Handle malformed outputs by raising a `ValueError` with a helpful message.

**Hints:**
- Use regex to extract `Action:`, `Action Input:`, and `Final Answer:` fields
- Check for Final Answer first (if both appear, prioritize based on position)
- The Thought field is optional for parsing but useful to extract

<details>
<summary>View Solution</summary>

```python
import re
from dataclasses import dataclass
from typing import Union


@dataclass
class AgentAction:
    tool: str
    tool_input: str
    thought: str = ""


@dataclass
class AgentFinish:
    output: str
    thought: str = ""


def parse_react_output(text: str) -> Union[AgentAction, AgentFinish]:
    """Parse ReAct-formatted LLM output.

    Expected formats:
        Thought: ...
        Action: tool_name
        Action Input: input_string
    OR:
        Thought: ...
        Final Answer: answer_string

    Raises ValueError if neither format is found.
    """
    # Extract thought (optional)
    thought = ""
    thought_match = re.search(
        r"Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:)|$)",
        text, re.DOTALL
    )
    if thought_match:
        thought = thought_match.group(1).strip()

    # Check for Final Answer
    final_match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL)
    action_match = re.search(r"Action:\s*(.+?)(?:\n|$)", text)
    input_match = re.search(r"Action Input:\s*(.+?)(?:\n|$)", text, re.DOTALL)

    # If both exist, check which comes first
    if final_match and action_match:
        if text.index("Final Answer:") < text.index("Action:"):
            return AgentFinish(output=final_match.group(1).strip(), thought=thought)
        else:
            if input_match:
                return AgentAction(
                    tool=action_match.group(1).strip(),
                    tool_input=input_match.group(1).strip(),
                    thought=thought,
                )

    if final_match:
        return AgentFinish(output=final_match.group(1).strip(), thought=thought)

    if action_match and input_match:
        return AgentAction(
            tool=action_match.group(1).strip(),
            tool_input=input_match.group(1).strip(),
            thought=thought,
        )

    if action_match and not input_match:
        raise ValueError(
            f"Found 'Action: {action_match.group(1).strip()}' but no 'Action Input:'. "
            "Both are required."
        )

    raise ValueError(
        "Could not parse output. Expected either:\n"
        "  'Action: <tool>\\nAction Input: <input>'\n"
        "or:\n"
        "  'Final Answer: <answer>'\n"
        f"Got:\n{text[:200]}"
    )


# ── Tests ────────────────────────────────────────────────────────────────────

# Test action parsing
result = parse_react_output(
    "Thought: I need to search.\nAction: wikipedia\nAction Input: AI agents"
)
assert isinstance(result, AgentAction)
assert result.tool == "wikipedia"
assert result.tool_input == "AI agents"

# Test final answer
result = parse_react_output("Thought: I know the answer.\nFinal Answer: 42")
assert isinstance(result, AgentFinish)
assert result.output == "42"

# Test error on malformed output
try:
    parse_react_output("Just some random text")
    assert False, "Should have raised ValueError"
except ValueError:
    pass

print("All assertions passed.")
```

</details>

---

## Challenge 3: Implement Conversation Memory with Sliding Window

**Problem:** Build a `SlidingWindowMemory` class that stores conversation messages and provides the most recent N messages when queried. Include a method to estimate token count and trim when approaching a token limit.

**Hints:**
- Each message is a dict with "role" and "content"
- Estimate tokens as `len(content) / 4` (rough approximation)
- Always preserve the system message (first message)

<details>
<summary>View Solution</summary>

```python
from typing import Optional


class SlidingWindowMemory:
    """Conversation memory with sliding window and token-aware trimming."""

    def __init__(self, max_messages: int = 20, max_tokens: int = 4000):
        self._messages: list[dict[str, str]] = []
        self.max_messages = max_messages
        self.max_tokens = max_tokens

    def add(self, role: str, content: str) -> None:
        """Add a message to memory."""
        self._messages.append({"role": role, "content": content})

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """Rough token estimate: ~4 chars per token + overhead per message."""
        total = 0
        for msg in messages:
            total += len(msg["content"]) // 4 + 4  # 4 tokens overhead per message
        return total

    def get_messages(self) -> list[dict[str, str]]:
        """Return messages fitting within both message and token limits.

        Preserves the system message (if present) and the most recent messages.
        """
        if not self._messages:
            return []

        # Separate system message from conversation
        system_msgs = [m for m in self._messages if m["role"] == "system"]
        conversation = [m for m in self._messages if m["role"] != "system"]

        # Apply message count limit
        if len(conversation) > self.max_messages:
            conversation = conversation[-self.max_messages:]

        # Apply token limit
        result = list(system_msgs)  # Always include system message
        system_tokens = self._estimate_tokens(system_msgs)
        remaining_budget = self.max_tokens - system_tokens

        # Add messages from most recent, trimming oldest if over budget
        selected = []
        for msg in reversed(conversation):
            msg_tokens = self._estimate_tokens([msg])
            if remaining_budget - msg_tokens >= 0:
                selected.append(msg)
                remaining_budget -= msg_tokens
            else:
                break

        result.extend(reversed(selected))
        return result

    @property
    def total_messages(self) -> int:
        return len(self._messages)

    @property
    def estimated_tokens(self) -> int:
        return self._estimate_tokens(self.get_messages())

    def clear(self) -> None:
        """Clear all messages except system messages."""
        self._messages = [m for m in self._messages if m["role"] == "system"]


# ── Tests ────────────────────────────────────────────────────────────────────

mem = SlidingWindowMemory(max_messages=3, max_tokens=4000)
mem.add("system", "You are helpful.")
mem.add("user", "Hello")
mem.add("assistant", "Hi there!")
mem.add("user", "Question 1")
mem.add("assistant", "Answer 1")
mem.add("user", "Question 2")
mem.add("assistant", "Answer 2")

messages = mem.get_messages()
# Should have system + last 3 conversation messages
assert messages[0]["role"] == "system"
assert len(messages) == 4  # system + 3 most recent
assert messages[-1]["content"] == "Answer 2"

print("All assertions passed.")
```

</details>

---

## Challenge 4: Build a Retry-with-Backoff Decorator for Tool Calls

**Problem:** Write a decorator `@retry_tool` that retries a tool function on failure with exponential backoff. It should support configurable max retries, base delay, and a list of retryable exception types.

**Hints:**
- Use `functools.wraps` to preserve the function metadata
- Exponential backoff: `delay = base * (2 ** attempt)`
- Add jitter to prevent thundering herd
- Return the last error as a string if all retries fail

<details>
<summary>View Solution</summary>

```python
import time
import random
import functools
from typing import Callable, Type


def retry_tool(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
    jitter: bool = True,
):
    """Decorator that retries a tool function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds (before exponential scaling).
        max_delay: Maximum delay cap in seconds.
        retryable_exceptions: Tuple of exception types that trigger retries.
        jitter: Whether to add random jitter to prevent thundering herd.

    Returns:
        Decorator function.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):  # +1 for the initial try
                try:
                    return fn(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        break  # No more retries

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random())  # 50-150% of calculated delay

                    time.sleep(delay)

            return f"Tool '{fn.__name__}' failed after {max_retries + 1} attempts: {last_exception}"

        return wrapper
    return decorator


# ── Usage and Tests ──────────────────────────────────────────────────────────

call_count = 0

@retry_tool(max_retries=2, base_delay=0.01, retryable_exceptions=(ConnectionError,))
def flaky_api_call(query: str) -> str:
    """Simulates a flaky API that fails twice then succeeds."""
    global call_count
    call_count += 1
    if call_count < 3:
        raise ConnectionError("Connection refused")
    return f"Success: {query}"

# Should succeed on the 3rd attempt
call_count = 0
result = flaky_api_call("test")
assert result == "Success: test"
assert call_count == 3

# Should fail after exhausting retries
call_count = 0

@retry_tool(max_retries=1, base_delay=0.01)
def always_fails(query: str) -> str:
    raise ValueError("Always fails")

result = always_fails("test")
assert "failed after" in result

print("All assertions passed.")
```

</details>

---

## Challenge 5: Build a Simple Agent Loop

**Problem:** Implement a complete agent loop that takes a user question, calls a mock LLM function, parses the response for tool calls, executes tools, and repeats until a final answer is produced. Use dependency injection for the LLM function so the solution is testable.

**Hints:**
- Define a `LLMFunction` protocol (callable that takes messages and returns a string)
- The loop should have a max iteration limit
- Use the parser from Challenge 2 or a simplified version

<details>
<summary>View Solution</summary>

```python
from typing import Callable, Protocol
from dataclasses import dataclass


class LLMFunction(Protocol):
    """Protocol for the LLM call - enables testing with mocks."""
    def __call__(self, messages: list[dict[str, str]]) -> str: ...


@dataclass
class ToolDef:
    name: str
    description: str
    fn: Callable


def run_agent_loop(
    query: str,
    llm: LLMFunction,
    tools: list[ToolDef],
    max_iterations: int = 5,
) -> str:
    """Execute an agent loop with tool calling.

    Args:
        query: The user's question.
        llm: A callable that takes messages and returns LLM output text.
        tools: Available tools.
        max_iterations: Safety limit on loop iterations.

    Returns:
        The agent's final answer string.
    """
    tool_map = {t.name: t for t in tools}
    tool_desc = "\n".join(f"- {t.name}: {t.description}" for t in tools)

    system_prompt = (
        f"You have these tools:\n{tool_desc}\n\n"
        "Use format:\nAction: <tool>\nAction Input: <input>\n\n"
        "Or:\nFinal Answer: <answer>"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    for i in range(max_iterations):
        response = llm(messages)

        # Check for final answer
        if "Final Answer:" in response:
            idx = response.index("Final Answer:") + len("Final Answer:")
            return response[idx:].strip()

        # Parse action
        if "Action:" in response and "Action Input:" in response:
            action_line = ""
            input_line = ""
            for line in response.split("\n"):
                if line.strip().startswith("Action:"):
                    action_line = line.split("Action:", 1)[1].strip()
                elif line.strip().startswith("Action Input:"):
                    input_line = line.split("Action Input:", 1)[1].strip()

            if action_line and action_line in tool_map:
                try:
                    observation = str(tool_map[action_line].fn(input_line))
                except Exception as e:
                    observation = f"Error: {e}"
            elif action_line:
                observation = f"Unknown tool: {action_line}"
            else:
                observation = "Could not parse action."

            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
        else:
            # Malformed output -- ask for correction
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": "Please respond with Action/Action Input or Final Answer.",
            })

    return "Max iterations reached without a final answer."


# ── Test with Mock LLM ───────────────────────────────────────────────────────

call_num = 0

def mock_llm(messages: list[dict[str, str]]) -> str:
    global call_num
    call_num += 1
    if call_num == 1:
        return "Thought: I need to calculate.\nAction: calc\nAction Input: 2+2"
    else:
        return "Thought: Got it.\nFinal Answer: The answer is 4."

tools = [
    ToolDef("calc", "Calculate a math expression", lambda expr: eval(expr)),
]

call_num = 0
result = run_agent_loop("What is 2+2?", mock_llm, tools)
assert result == "The answer is 4."
print(f"Agent returned: {result}")
print("All assertions passed.")
```

</details>

---

## Challenge 6: Implement a Semantic Router

**Problem:** Build a `SemanticRouter` that routes queries to different handlers based on embedding similarity. Given a set of routes (each with example queries and a handler function), the router embeds the incoming query and matches it to the most similar route.

**Hints:**
- Use cosine similarity between embedding vectors
- Pre-compute route embeddings from the example queries (average the examples)
- Include a confidence threshold -- below it, return a default handler

<details>
<summary>View Solution</summary>

```python
import math
from typing import Callable, Any
from dataclasses import dataclass, field


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class Route:
    name: str
    examples: list[str]
    handler: Callable[[str], str]
    embedding: list[float] = field(default_factory=list)  # Computed


class SemanticRouter:
    """Route queries to handlers based on semantic similarity."""

    def __init__(
        self,
        embed_fn: Callable[[str], list[float]],
        threshold: float = 0.5,
        default_handler: Callable[[str], str] = lambda q: "I cannot handle that request.",
    ):
        self._embed = embed_fn
        self._threshold = threshold
        self._default = default_handler
        self._routes: list[Route] = []

    def add_route(self, name: str, examples: list[str], handler: Callable) -> None:
        """Register a route with example queries."""
        # Compute route embedding as average of example embeddings
        example_embeddings = [self._embed(ex) for ex in examples]
        dim = len(example_embeddings[0])
        avg_embedding = [
            sum(emb[i] for emb in example_embeddings) / len(example_embeddings)
            for i in range(dim)
        ]
        route = Route(name=name, examples=examples, handler=handler, embedding=avg_embedding)
        self._routes.append(route)

    def route(self, query: str) -> tuple[str, str, float]:
        """Route a query to the best matching handler.

        Returns: (route_name, handler_result, confidence)
        """
        query_embedding = self._embed(query)

        best_route = None
        best_score = -1.0

        for route in self._routes:
            score = cosine_similarity(query_embedding, route.embedding)
            if score > best_score:
                best_score = score
                best_route = route

        if best_route and best_score >= self._threshold:
            result = best_route.handler(query)
            return (best_route.name, result, best_score)
        else:
            result = self._default(query)
            return ("default", result, best_score)


# ── Test with a simple mock embedder ─────────────────────────────────────────

# Mock embedding: use character frequency as a simple embedding
def mock_embed(text: str) -> list[float]:
    chars = "abcdefghijklmnopqrstuvwxyz "
    vec = [text.lower().count(c) for c in chars]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

router = SemanticRouter(embed_fn=mock_embed, threshold=0.3)

router.add_route(
    "billing",
    ["what is my bill", "invoice question", "payment issue"],
    lambda q: f"Billing handler: {q}",
)
router.add_route(
    "technical",
    ["bug report", "error message", "system crash"],
    lambda q: f"Tech handler: {q}",
)

name, result, score = router.route("I have a billing question about my invoice")
assert name == "billing", f"Expected billing, got {name}"
print(f"Routed to: {name} (score={score:.3f})")

name, result, score = router.route("My application keeps crashing with an error")
assert name == "technical", f"Expected technical, got {name}"
print(f"Routed to: {name} (score={score:.3f})")

print("All assertions passed.")
```

</details>

---

## Challenge 7: Build an LLM-as-Judge Evaluator

**Problem:** Implement an evaluation function that uses one LLM call to judge the quality of an agent's response on multiple criteria (accuracy, helpfulness, safety). Return a structured score breakdown.

**Hints:**
- Define the evaluation criteria in the judge prompt
- Request JSON output with scores per criterion
- Handle JSON parsing failures gracefully
- Include the original query and agent response as context

<details>
<summary>View Solution</summary>

```python
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class JudgeResult:
    overall_score: float
    criteria_scores: dict[str, float]
    reasoning: str
    raw_response: str


def llm_judge(
    query: str,
    agent_response: str,
    llm_fn,  # Callable that takes a prompt string and returns text
    criteria: Optional[dict[str, str]] = None,
) -> JudgeResult:
    """Evaluate an agent response using an LLM as judge.

    Args:
        query: The original user query.
        agent_response: The agent's response to evaluate.
        llm_fn: Function that takes a prompt and returns LLM text output.
        criteria: Dict mapping criterion name to description.
                  Defaults to accuracy, helpfulness, safety.

    Returns:
        JudgeResult with per-criterion scores and overall score.
    """
    if criteria is None:
        criteria = {
            "accuracy": "Is the response factually correct and well-supported?",
            "helpfulness": "Does the response address the user's needs completely?",
            "safety": "Is the response free from harmful, biased, or inappropriate content?",
        }

    criteria_text = "\n".join(
        f"  - {name}: {desc}" for name, desc in criteria.items()
    )
    criteria_json = ", ".join(f'"{name}": 0.0' for name in criteria)

    prompt = f"""You are a strict AI response evaluator. Score the following
agent response on a scale of 0.0 (terrible) to 1.0 (perfect) for each criterion.

CRITERIA:
{criteria_text}

USER QUERY:
{query}

AGENT RESPONSE:
{agent_response}

Respond ONLY with valid JSON:
{{
  "scores": {{{criteria_json}}},
  "reasoning": "Brief explanation of scores"
}}"""

    raw = llm_fn(prompt)

    # Parse the response
    try:
        # Handle potential markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        parsed = json.loads(cleaned)
        scores = parsed.get("scores", {})
        reasoning = parsed.get("reasoning", "No reasoning provided.")

        # Validate scores
        validated_scores = {}
        for name in criteria:
            val = scores.get(name, 0.5)
            validated_scores[name] = max(0.0, min(1.0, float(val)))

        overall = sum(validated_scores.values()) / len(validated_scores)

        return JudgeResult(
            overall_score=overall,
            criteria_scores=validated_scores,
            reasoning=reasoning,
            raw_response=raw,
        )

    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # Fallback when parsing fails
        return JudgeResult(
            overall_score=0.5,
            criteria_scores={name: 0.5 for name in criteria},
            reasoning=f"Failed to parse judge response: {raw[:200]}",
            raw_response=raw,
        )


# ── Test with Mock LLM ──────────────────────────────────────────────────────

def mock_judge_llm(prompt: str) -> str:
    return json.dumps({
        "scores": {"accuracy": 0.9, "helpfulness": 0.85, "safety": 1.0},
        "reasoning": "Accurate and helpful, fully safe.",
    })

result = llm_judge(
    query="What is the capital of France?",
    agent_response="The capital of France is Paris.",
    llm_fn=mock_judge_llm,
)

assert result.overall_score > 0.9
assert result.criteria_scores["accuracy"] == 0.9
assert result.criteria_scores["safety"] == 1.0
print(f"Overall: {result.overall_score:.2f}, Scores: {result.criteria_scores}")
print("All assertions passed.")
```

</details>

---

## Challenge 8: Mini Agent System -- Research Assistant

**Problem:** Build a complete mini research assistant that:
1. Takes a research question
2. Breaks it into sub-questions
3. "Searches" for each sub-question (use mock search)
4. Synthesizes the results into a final answer

Use dependency injection for the LLM so it is testable. Implement the Plan-and-Execute pattern.

**Hints:**
- The planner generates a list of sub-questions (JSON array)
- The searcher finds answers for each sub-question
- The synthesizer combines all findings into a coherent answer
- Handle the case where the planner generates an invalid plan

<details>
<summary>View Solution</summary>

```python
import json
from typing import Protocol
from dataclasses import dataclass


class LLMFunction(Protocol):
    def __call__(self, prompt: str) -> str: ...


@dataclass
class ResearchResult:
    question: str
    sub_questions: list[str]
    findings: dict[str, str]  # sub_question -> finding
    synthesis: str
    steps_taken: int


class ResearchAssistant:
    """A mini research agent using the Plan-and-Execute pattern."""

    def __init__(
        self,
        planner_llm: LLMFunction,
        synthesizer_llm: LLMFunction,
        search_fn,  # Callable[[str], str]
        max_sub_questions: int = 5,
    ):
        self.planner = planner_llm
        self.synthesizer = synthesizer_llm
        self.search = search_fn
        self.max_sub_questions = max_sub_questions

    def _plan(self, question: str) -> list[str]:
        """Decompose the research question into sub-questions."""
        prompt = (
            f"Break this research question into 2-{self.max_sub_questions} "
            f"specific sub-questions that, when answered, would fully address "
            f"the main question.\n\n"
            f"Question: {question}\n\n"
            f"Respond with a JSON array of strings, nothing else."
        )
        response = self.planner(prompt)

        try:
            # Handle potential markdown fences
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            sub_questions = json.loads(cleaned)

            if not isinstance(sub_questions, list):
                raise ValueError("Expected a JSON array")

            # Cap the number of sub-questions
            return [str(q) for q in sub_questions[:self.max_sub_questions]]

        except (json.JSONDecodeError, ValueError):
            # Fallback: treat the whole question as a single sub-question
            return [question]

    def _execute(self, sub_questions: list[str]) -> dict[str, str]:
        """Search for answers to each sub-question."""
        findings = {}
        for sq in sub_questions:
            findings[sq] = self.search(sq)
        return findings

    def _synthesize(self, question: str, findings: dict[str, str]) -> str:
        """Synthesize findings into a coherent answer."""
        findings_text = "\n\n".join(
            f"Sub-question: {sq}\nFinding: {finding}"
            for sq, finding in findings.items()
        )
        prompt = (
            f"Synthesize the following research findings into a clear, "
            f"comprehensive answer to the main question.\n\n"
            f"Main question: {question}\n\n"
            f"Findings:\n{findings_text}\n\n"
            f"Provide a well-structured synthesis."
        )
        return self.synthesizer(prompt)

    def research(self, question: str) -> ResearchResult:
        """Execute the full research pipeline.

        Returns a ResearchResult with the plan, findings, and synthesis.
        """
        # Step 1: Plan
        sub_questions = self._plan(question)

        # Step 2: Execute
        findings = self._execute(sub_questions)

        # Step 3: Synthesize
        synthesis = self._synthesize(question, findings)

        return ResearchResult(
            question=question,
            sub_questions=sub_questions,
            findings=findings,
            synthesis=synthesis,
            steps_taken=1 + len(sub_questions) + 1,  # plan + searches + synthesize
        )


# ── Test with Mock Components ────────────────────────────────────────────────

def mock_planner(prompt: str) -> str:
    return json.dumps([
        "What is agentic AI?",
        "What are common agent architectures?",
        "What frameworks exist for building agents?",
    ])

def mock_search(query: str) -> str:
    responses = {
        "What is agentic AI?": "Agentic AI refers to systems where LLMs operate autonomously.",
        "What are common agent architectures?": "Common architectures include ReAct, Plan-and-Execute, and multi-agent systems.",
        "What frameworks exist for building agents?": "Popular frameworks include LangChain, LangGraph, CrewAI, and AutoGen.",
    }
    return responses.get(query, f"No information found for: {query}")

def mock_synthesizer(prompt: str) -> str:
    return (
        "Agentic AI is the discipline of building autonomous LLM-powered systems. "
        "Key architectures include ReAct and Plan-and-Execute. "
        "Leading frameworks are LangChain, LangGraph, CrewAI, and AutoGen."
    )

assistant = ResearchAssistant(
    planner_llm=mock_planner,
    synthesizer_llm=mock_synthesizer,
    search_fn=mock_search,
)

result = assistant.research("What is the state of agentic AI?")

assert len(result.sub_questions) == 3
assert len(result.findings) == 3
assert "Agentic AI" in result.synthesis
assert result.steps_taken == 5  # 1 plan + 3 searches + 1 synthesis
print(f"Sub-questions: {result.sub_questions}")
print(f"Synthesis: {result.synthesis}")
print(f"Total steps: {result.steps_taken}")
print("All assertions passed.")
```

</details>
