---
sidebar_position: 3
title: "Design Pattern Questions"
description: "15 Q&A on ReAct, Chain-of-Thought, multi-agent, reflection, and other agentic design patterns."
---

# Design Pattern Questions

These 15 questions cover the proven architectural patterns used to build agentic AI systems. Expect these in senior-level interviews where the interviewer wants to see that you can design, not just implement.

:::info Pattern vs. Framework
Patterns are reusable architectural solutions. Frameworks implement patterns. Know the patterns first -- then you can evaluate any framework and explain why it made specific design choices.
:::

---

## Q1. Explain the ReAct pattern and walk through an execution trace.

<details>
<summary>View Answer</summary>

ReAct (Reasoning + Acting) interleaves reasoning traces with tool-use actions. A typical execution trace looks like: **Thought**: "The user asked for the population of France. I should search for this." **Action**: `wikipedia_search("population of France")` **Observation**: "France has a population of approximately 68 million." **Thought**: "I now have the answer." **Final Answer**: "France has approximately 68 million people." The pattern works because reasoning steps make the model's decision-making transparent and force it to plan before acting, while the observations ground the reasoning in real data. Limitations include: verbose token usage (every thought is written out), sensitivity to prompt formatting, and the model may reason correctly but call the wrong tool. ReAct was introduced by Yao et al. (2022) and became the default pattern in LangChain's early agent implementations. It has been partially superseded by native function calling for tool selection, but the think-before-you-act principle remains foundational.

</details>

---

## Q2. What is the Plan-and-Execute pattern and how does it differ from ReAct?

<details>
<summary>View Answer</summary>

Plan-and-Execute separates planning from execution into two distinct phases. First, a **planner** LLM generates a complete step-by-step plan for the task. Then, an **executor** works through the plan one step at a time, using tools as needed. After each step, the planner may revise the remaining plan based on observations. This differs from ReAct in a key way: ReAct plans one step at a time (local planning), while Plan-and-Execute creates a global plan before executing any step. Advantages: better performance on complex multi-step tasks because the model considers the full problem before acting, and the plan can be shown to users for approval (HITL). Disadvantages: the initial plan may become invalid as new information is discovered, requiring expensive replanning; more LLM calls (planner + executor); and the planner may generate plans that are too vague or too specific. Use Plan-and-Execute for tasks with clear multi-step structure (research reports, data analysis pipelines). Use ReAct for simpler, more dynamic tasks where the next step depends heavily on the previous result.

</details>

---

## Q3. Describe the Supervisor multi-agent pattern.

<details>
<summary>View Answer</summary>

In the Supervisor pattern, a central **supervisor agent** receives the user's request, decides which **worker agent** should handle it (or which sub-task each worker should tackle), delegates the work, collects the results, and synthesizes a final response. The supervisor acts as a router and orchestrator. Workers are specialized agents, each with their own tools and system prompts. For example, a supervisor might route billing questions to a billing agent, technical questions to a tech support agent, and general questions to a FAQ agent. Implementation: the supervisor's system prompt describes the available workers and their capabilities; it uses the conversation context to decide routing; worker outputs are returned to the supervisor for final synthesis. Advantages: clear separation of concerns, each worker can be tested independently, workers can use different models (cheap model for simple tasks, expensive model for hard tasks). Disadvantages: the supervisor is a single point of failure, every interaction requires at least two LLM calls (supervisor + worker), and routing errors cascade. LangGraph implements this pattern with conditional edges from a supervisor node.

</details>

---

## Q4. What is the Reflection pattern and how does it improve agent outputs?

<details>
<summary>View Answer</summary>

The Reflection pattern adds a self-evaluation step where the agent (or a separate evaluator) reviews its own output and decides whether to accept it or revise. The typical flow is: generate a response, then run a "critic" prompt that evaluates the response against criteria (accuracy, completeness, tone), then either accept or regenerate based on the evaluation. This can be implemented as: (1) **self-reflection** -- the same model evaluates its own output (cheaper, but biased toward accepting its own work); (2) **cross-reflection** -- a different model or a separate prompt evaluates (more objective, more expensive); (3) **iterative refinement** -- the reflection loop repeats until the quality threshold is met or a max iteration count is reached. Reflection improves agent outputs by catching errors that the initial generation missed, similar to how human experts review their own work. The key design decision is the evaluation criteria -- vague criteria like "is this good?" produce vague feedback. Specific criteria like "does this answer contain a concrete next step for the customer?" produce actionable improvements.

</details>

---

## Q5. Explain the Router pattern and when to use it.

<details>
<summary>View Answer</summary>

The Router pattern uses an LLM (or a classifier) to categorize incoming requests and route them to specialized handlers. Unlike the Supervisor pattern (which delegates and synthesizes), the Router simply directs traffic -- the selected handler produces the final response. Implementation options: (1) **LLM-based routing** -- a small, fast model classifies the query and selects the appropriate handler; (2) **semantic routing** -- embed the query and compare to pre-computed route embeddings; (3) **rule-based routing** -- keyword matching or regex for deterministic routing. Use the Router pattern when: you have distinct categories of requests (each needing different tools, prompts, or models), you want to optimize cost (route simple queries to cheap models), or you need deterministic behavior for specific input types. Advantages: lower latency than a full agent loop for routable queries, cost optimization through model tiering, and clear separation of concerns. The Router pattern is often combined with other patterns -- route to a ReAct agent for complex queries, to a simple RAG pipeline for FAQ-like questions, and to a human for out-of-scope requests.

</details>

---

## Q6. What is the Chain-of-Thought (CoT) pattern and how is it used in agents?

<details>
<summary>View Answer</summary>

Chain-of-Thought prompting instructs the LLM to break down its reasoning into explicit intermediate steps before producing a final answer. In agent systems, CoT serves multiple purposes: (1) **improved accuracy** -- decomposing complex problems into simpler sub-problems reduces errors, especially in math and logic; (2) **transparency** -- the reasoning steps are visible for debugging and auditing; (3) **better tool selection** -- when the agent reasons about what it needs before acting, it chooses tools more accurately. CoT variants include: **zero-shot CoT** ("Let's think step by step"), **few-shot CoT** (examples with step-by-step reasoning), **self-consistency CoT** (generate multiple reasoning paths and take the majority vote), and **tree-of-thought** (explore branching reasoning paths). In agentic systems, CoT is embedded in the ReAct pattern (the "Thought" step is CoT reasoning) and in the planning phase of Plan-and-Execute. The trade-off is token cost: CoT reasoning can add 100-500 tokens per step. For simple queries, CoT is unnecessary overhead; for complex queries, it is essential.

</details>

---

## Q7. Describe the Tool-Use pattern and its design considerations.

<details>
<summary>View Answer</summary>

The Tool-Use pattern gives an LLM access to external functions that it can call to interact with the world. Design considerations include: (1) **tool granularity** -- tools should be atomic (do one thing well) but not too narrow (avoid 50 tools that could be 5); (2) **tool descriptions** -- these are part of the prompt and the LLM selects tools based on them, so clarity is critical (include when to use, when NOT to use, example inputs); (3) **parameter design** -- use descriptive parameter names with clear types and constraints (enums where possible); (4) **error handling** -- tools should return informative error messages, not crash; (5) **idempotency** -- read operations are safe to retry, but write operations (send email, create record) need deduplication or confirmation gates; (6) **security** -- validate all parameters before execution, implement least-privilege access, never pass raw LLM output to shell commands or SQL queries; (7) **observability** -- log every tool call with inputs, outputs, and latency for debugging. The number of tools impacts model performance: beyond 10-15 tools, selection accuracy degrades. If you need more, use a hierarchical approach (route to a tool category first, then to specific tools).

</details>

---

## Q8. What is the Map-Reduce pattern for agents?

<details>
<summary>View Answer</summary>

The Map-Reduce pattern parallelizes work by splitting a task into independent sub-tasks (map), processing each sub-task concurrently (execute), and combining the results (reduce). In agentic AI, this is used for tasks like: analyzing multiple documents simultaneously, comparing features across several products, or gathering information from multiple sources. The **map** phase creates N parallel tasks (e.g., "summarize each of these 10 documents"). The **execute** phase runs each task independently -- this can be N parallel LLM calls or N parallel agent runs. The **reduce** phase combines the N outputs into a final result (e.g., "synthesize these 10 summaries into a comprehensive report"). Advantages: dramatic latency reduction (10 parallel calls take the same time as 1), natural decomposition of large tasks, and each sub-task is simpler and more focused. Disadvantages: higher total token cost (more LLM calls), the reduce step must handle inconsistencies across sub-task outputs, and some tasks are not naturally decomposable. LangGraph supports this with parallel node execution using the `Send` API.

</details>

---

## Q9. Explain the Fallback Chain pattern.

<details>
<summary>View Answer</summary>

The Fallback Chain pattern defines a sequence of increasingly powerful (and expensive) strategies for handling a request. If the first strategy fails or produces a low-confidence result, the system falls back to the next strategy. A typical chain: (1) **cache lookup** -- check if this exact query has been answered before; (2) **RAG retrieval** -- search the knowledge base for a direct answer; (3) **simple agent** -- use a cheap model (GPT-4o-mini) with basic tools; (4) **full agent** -- use the most capable model (GPT-4o) with all tools; (5) **human escalation** -- route to a human agent. This pattern optimizes for both cost and latency: the vast majority of queries are handled by cheap, fast strategies, while complex queries automatically escalate. Implementation requires a confidence or quality scoring mechanism at each level to decide whether to proceed or fall back. The pattern is analogous to a caching hierarchy in systems engineering. Key design decisions: what triggers a fallback (error, low confidence, specific query type), and how many levels are appropriate (too many levels add latency from failed attempts).

</details>

---

## Q10. What is the Retrieval-Agent pattern and how does it combine RAG with agents?

<details>
<summary>View Answer</summary>

The Retrieval-Agent pattern wraps RAG into a tool that the agent can choose to use alongside other tools. Instead of always retrieving documents for every query, the agent decides when retrieval is necessary based on the question. This is more efficient than always-on RAG because: some questions do not need retrieved context (e.g., "What is 2+2?"), and the agent can combine retrieved information with other tools (calculator, web search, database queries). Implementation: create a retriever tool with a clear description ("Search the knowledge base for company policies and product information"), register it alongside other tools, and let the agent's routing logic decide when to use it. Advanced variants include: **multi-index retrieval** (different vector stores for different document types), **query rewriting** (the agent rewrites the user's query for better retrieval), and **iterative retrieval** (retrieve, assess relevance, refine query, retrieve again). The key advantage over vanilla RAG is flexibility -- the agent can reason about whether retrieval is needed and what to do with the results.

</details>

---

## Q11. Describe the State Machine pattern for agent workflows.

<details>
<summary>View Answer</summary>

The State Machine pattern models an agent workflow as a finite set of states with defined transitions between them. Each state represents a phase of the workflow (e.g., "gathering_info", "processing", "awaiting_approval", "completed"), and transitions are triggered by conditions (user input, tool results, quality checks). Unlike the free-form ReAct loop, the state machine constrains the agent's behavior to predefined paths, making it more predictable and auditable. LangGraph is essentially a state machine framework -- each node is a state, edges are transitions, and conditional edges are dynamic transitions. Advantages: deterministic behavior (you know exactly which states are reachable), easier testing (each state and transition can be tested independently), natural support for HITL (pause at specific states), and clear error handling (define error states and recovery transitions). Disadvantages: less flexible than free-form agents (cannot handle truly novel situations that were not anticipated), and the state graph can become complex for workflows with many branches. Use state machines for business-critical workflows with regulatory or compliance requirements.

</details>

---

## Q12. What is the Critic pattern (also called Verification pattern)?

<details>
<summary>View Answer</summary>

The Critic pattern uses a separate LLM call (or model) to verify the primary agent's output before it is returned to the user. The critic receives the original query, the agent's response, and evaluation criteria, then produces a pass/fail judgment with specific feedback. If the critic rejects the response, it is sent back to the agent for revision. This differs from Reflection (where the agent self-evaluates) in that the critic is independent, which reduces self-serving bias. Implementation approaches: (1) **same model, different prompt** -- cheapest, but the model may make the same errors; (2) **different model** -- e.g., use Claude to critique GPT-4o's output; (3) **specialized verifier** -- a model fine-tuned for evaluation; (4) **rule-based verifier** -- check for factual consistency, format compliance, or policy violations without an LLM. The Critic pattern is especially valuable for high-stakes applications (medical, legal, financial) where errors have serious consequences. The cost trade-off is that every response requires at least one additional LLM call. In interviews, connect this to the "Constitutional AI" concept from Anthropic, where a set of principles guide the critic's evaluation.

</details>

---

## Q13. Explain the Hierarchical Agent pattern.

<details>
<summary>View Answer</summary>

The Hierarchical Agent pattern organizes agents in a tree structure where higher-level agents delegate to lower-level agents, which may further delegate to even more specialized agents. A top-level "manager" agent receives the user's request and delegates to "team lead" agents, which in turn delegate to "worker" agents. Each level adds specialization and narrows scope. For example: a manager agent decides the task is a "data analysis" request and delegates to a data analysis team lead, which delegates sub-tasks to a SQL agent (for queries), a Python agent (for computation), and a visualization agent (for charts). Advantages: scales to very complex tasks, each agent has a narrow, well-defined scope (reducing errors), and different levels can use different models (expensive model for planning, cheap models for execution). Disadvantages: high latency (multiple layers of LLM calls), complex debugging (errors can originate at any level), and the delegation chain can introduce compounding errors if higher levels misunderstand the task. Use this pattern only when the task complexity genuinely requires multiple levels of decomposition.

</details>

---

## Q14. What is the Parallel Execution pattern and how does it differ from Map-Reduce?

<details>
<summary>View Answer</summary>

The Parallel Execution pattern runs multiple independent agent tasks concurrently to reduce total latency. While Map-Reduce applies the same operation to different data and then aggregates, Parallel Execution runs different operations that happen to be independent. For example, when answering "Compare the weather in NYC, London, and Tokyo, and calculate the average temperature," the agent can: (1) fetch NYC weather, (2) fetch London weather, (3) fetch Tokyo weather all in parallel, then (4) calculate the average sequentially. OpenAI's native tool calling supports this: the model can return multiple `tool_calls` in a single response, and the runtime executes them concurrently. In LangGraph, parallel execution is achieved with fan-out edges or the `Send` API. The key difference from Map-Reduce: parallel execution handles heterogeneous tasks (weather + database + calculation), while Map-Reduce handles homogeneous tasks (summarize document 1, summarize document 2, ..., reduce). Design considerations: ensure tasks are truly independent (no data dependencies), handle partial failures (if one parallel task fails, should you fail all or continue?), and manage rate limits (N parallel API calls may hit quotas).

</details>

---

## Q15. How do you choose the right pattern for a given problem?

<details>
<summary>View Answer</summary>

Pattern selection depends on five factors: (1) **Task complexity** -- simple QA uses RAG or a single tool-calling agent; complex multi-step tasks use Plan-and-Execute or multi-agent systems. (2) **Reliability requirements** -- high-stakes tasks need Reflection, Critic, and HITL patterns; low-stakes tasks can use simpler patterns. (3) **Latency budget** -- real-time applications favor Router and Fallback Chain (fast paths for common queries); batch applications can afford Plan-and-Execute and multi-agent. (4) **Cost budget** -- each LLM call costs money; Reflection and Critic patterns double or triple the cost per query. Start with the simplest viable pattern and add complexity only when needed. (5) **Observability needs** -- regulated industries need auditable patterns like State Machine; research applications can use more flexible patterns. The general progression is: start with a simple tool-calling agent, add RAG if knowledge is needed, add Reflection if quality is insufficient, add Routing if you need to handle diverse query types, and only move to multi-agent if the task genuinely requires it. Over-engineering with complex patterns is a common mistake -- each added pattern increases latency, cost, and debugging difficulty.

</details>
