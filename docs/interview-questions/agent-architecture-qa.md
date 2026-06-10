---
sidebar_position: 2
title: "Agent Architecture Questions"
description: "15 Q&A on agent concepts, architectures, tools, and memory for interview preparation."
---

# Agent Architecture Questions

These 15 questions cover the core concepts of agentic AI systems: the agent loop, tool integration, memory architectures, planning strategies, and orchestration patterns. These are the questions that separate candidates who have only used LLM APIs from those who understand how to build autonomous systems.

:::info Interview Context
Agent architecture questions are common in mid-level to senior AI engineering interviews. Interviewers want to see that you understand the fundamental building blocks, not just the frameworks that abstract them away.
:::

---

## Q1. What is an AI agent and how does it differ from a simple LLM application?

<details>
<summary>View Answer</summary>

An AI agent is a system where an LLM operates in a loop, deciding which actions to take based on observations from its environment. Unlike a simple LLM application (which takes input, generates output, and stops), an agent has **autonomy** (it decides its own next steps), **tool use** (it can interact with external systems), **memory** (it maintains state across steps), and **iterative reasoning** (it can observe results and adjust its approach). The defining characteristic is the feedback loop: the LLM's output determines the next action, the action produces an observation, and the observation informs the next LLM call. A chatbot that answers questions is an LLM application; a system that researches a topic by searching the web, reading documents, synthesizing information, and iterating until it has a complete answer is an agent.

</details>

---

## Q2. Describe the Observe-Think-Act loop and why it is the foundation of agent design.

<details>
<summary>View Answer</summary>

The Observe-Think-Act (OTA) loop is the fundamental execution cycle of any agent. In the **Observe** phase, the agent receives information from its environment -- this could be user input, tool results, or sensor data. In the **Think** phase, the LLM reasons about what it has observed and decides on the next action (this is where techniques like chain-of-thought and ReAct reasoning happen). In the **Act** phase, the agent executes the chosen action, which could be calling a tool, generating a response, or modifying its environment. The result of the action becomes the next observation, restarting the cycle. This loop is foundational because every agent framework implements some variant of it. LangChain's `AgentExecutor`, CrewAI's task execution, and LangGraph's node traversal all ultimately reduce to this cycle. Understanding the loop helps you debug agents, design new architectures, and reason about failure modes.

</details>

---

## Q3. What is tool calling in the context of LLM agents and how does it work?

<details>
<summary>View Answer</summary>

Tool calling (also called function calling) is the mechanism by which an LLM requests the execution of external functions. The LLM receives a list of available tools with their names, descriptions, and parameter schemas. When it determines that a tool is needed, it generates a structured request (typically JSON) specifying the tool name and arguments. The agent runtime then executes the actual function and feeds the result back to the LLM. There are two approaches: **native tool calling** (using the API's built-in `tools` parameter, as in OpenAI and Anthropic) produces structured JSON and supports parallel calls; **prompt-based tool calling** (like ReAct) relies on the LLM generating specific text patterns that a parser extracts. Native tool calling is more reliable because the model is trained to produce valid JSON, while prompt-based approaches are more portable across models. Key interview point: the LLM never actually executes the tool -- it only generates the request. Execution happens in the host application, which is critical for security.

</details>

---

## Q4. Explain the different types of memory in agent systems.

<details>
<summary>View Answer</summary>

Agent memory typically has three layers. **Short-term (working) memory** is the current conversation context and scratchpad -- it exists within the context window and is lost when the conversation ends. This includes the message history, tool results, and intermediate reasoning steps. **Long-term memory** persists across conversations and sessions -- it is implemented using external storage like vector databases, key-value stores, or relational databases. This enables the agent to recall past interactions, user preferences, and learned facts. **Episodic memory** records specific past experiences (e.g., "last time the user asked about refunds, the resolution was X"), enabling the agent to learn from its own history. Some frameworks also distinguish **semantic memory** (general knowledge facts) from **procedural memory** (learned strategies for solving tasks). The key design decision is what to store, how to retrieve it, and when to forget -- unbounded memory growth degrades retrieval quality and increases costs.

</details>

---

## Q5. What is the ReAct pattern and why is it significant?

<details>
<summary>View Answer</summary>

ReAct (Reasoning + Acting) is a prompting pattern where the LLM alternates between **reasoning steps** (thinking out loud about what to do) and **action steps** (calling tools or generating outputs). The format is: Thought (reasoning), Action (tool to call), Action Input (arguments), Observation (tool result), repeated until a Final Answer is reached. ReAct is significant because it was one of the first patterns to demonstrate that combining reasoning with tool use dramatically improves accuracy compared to either alone. The reasoning steps make the agent's decision process transparent and debuggable. The pattern was introduced in the Yao et al. 2022 paper and became the default agent architecture in LangChain. Its limitations are: sensitivity to prompt formatting, verbose token usage due to written-out reasoning, and potential for the LLM to deviate from the expected format. Native function calling has partially superseded ReAct for tool selection, but the reasoning-before-acting principle remains central to agent design.

</details>

---

## Q6. How do you decide what should be a tool vs. what should be handled by the LLM directly?

<details>
<summary>View Answer</summary>

A capability should be implemented as a tool when it requires: (1) **real-time or external data** -- the LLM's training data is static, so live information (weather, stock prices, database queries) must come from tools; (2) **deterministic computation** -- math, date calculations, and data transformations should use tools because LLMs make arithmetic errors; (3) **side effects** -- creating records, sending emails, or modifying state requires real execution, not text generation; (4) **structured data access** -- querying databases or APIs with specific parameters. Conversely, keep in the LLM: text summarization, rephrasing, sentiment analysis, general knowledge Q&A, and creative generation -- tasks where the LLM's training provides value and exact precision is not required. A common mistake is making too many tools -- each tool adds complexity to the selection process. Aim for 5-10 well-described tools rather than 50 narrow ones. The tool descriptions are part of the prompt, so more tools mean more tokens and more potential for routing errors.

</details>

---

## Q7. What is the difference between single-agent and multi-agent architectures? When would you choose each?

<details>
<summary>View Answer</summary>

A **single-agent** system uses one LLM instance with a set of tools to complete tasks. A **multi-agent** system uses multiple specialized LLM instances that collaborate, each with its own role, tools, and instructions. Choose single-agent when the task domain is narrow (e.g., a customer support bot), the tool set is manageable (under 10 tools), and the workflow is straightforward. Choose multi-agent when: tasks require diverse expertise (research + writing + editing), the tool set is too large for one agent to manage reliably, you need separation of concerns for security (one agent reads data, another writes), or you want to parallelize work. Multi-agent trade-offs include: higher cost (more LLM calls), increased latency, coordination complexity, and harder debugging. Common multi-agent patterns include supervisor (one agent delegates to others), peer-to-peer (agents communicate directly), and hierarchical (tree of delegation). Start with a single agent and only move to multi-agent when you have evidence that a single agent cannot handle the complexity.

</details>

---

## Q8. How do you handle agent failures and errors in production?

<details>
<summary>View Answer</summary>

Production agent error handling requires multiple layers. **Tool-level**: wrap every tool call in try/except, return informative error messages (not stack traces) to the LLM so it can adapt, and implement retries with exponential backoff for transient failures (network timeouts, rate limits). **Agent-level**: set maximum iteration limits to prevent infinite loops, implement cost caps to prevent runaway spending, use format correction prompts when the LLM deviates from expected output format, and maintain a fallback path (e.g., escalate to human). **System-level**: implement circuit breakers that disable failing tools, log all agent traces for debugging, set up alerting on error rates and latency spikes, and use graceful degradation (return a partial answer rather than nothing). A critical pattern is the "tool error as observation" approach: when a tool fails, feed the error back to the LLM as an observation, allowing it to try a different approach. Never silently swallow errors -- the LLM needs feedback to self-correct.

</details>

---

## Q9. What is a guardrail in the context of AI agents and what types exist?

<details>
<summary>View Answer</summary>

Guardrails are safety mechanisms that constrain agent behavior to prevent harmful, incorrect, or unauthorized actions. **Input guardrails** validate and sanitize user inputs before they reach the LLM -- this includes prompt injection detection, PII filtering, and content moderation. **Output guardrails** check the LLM's generated responses before they are returned to the user -- this includes toxicity filtering, factual verification, and format validation. **Tool guardrails** restrict which tools the agent can call and with what parameters -- for example, preventing a database tool from executing DELETE statements, or requiring human approval for financial transactions above a threshold. **Behavioral guardrails** enforce agent-level policies like maximum iterations, cost limits, and scope restrictions (e.g., the agent should only discuss topics related to the product). Implementation approaches range from simple rule-based checks (regex, keyword lists) to dedicated classifier models (Llama Guard, OpenAI Moderation API). In interviews, emphasize defense-in-depth: no single guardrail is sufficient.

</details>

---

## Q10. Explain the difference between stateless and stateful agents.

<details>
<summary>View Answer</summary>

A **stateless agent** treats each request independently -- it has no memory of previous interactions. Every query starts from scratch with just the system prompt and the current user message. A **stateful agent** maintains state across interactions, either within a session (conversation memory) or across sessions (persistent memory). Stateless agents are simpler to scale (any server can handle any request), easier to test (no hidden state), and have predictable costs. Stateful agents can handle follow-up questions ("What about the other option?"), personalize responses based on user history, and accumulate knowledge across interactions. The key implementation decisions for stateful agents are: where to store state (in-memory, Redis, database), how to serialize/deserialize state, how to manage state size (summarization, eviction policies), and how to handle concurrent access. LangGraph is specifically designed for stateful workflows, using checkpointers to persist state at each node. In interviews, mention that statefulness introduces challenges: debugging is harder, tests must account for state, and state corruption can cascade.

</details>

---

## Q11. What is the role of the system prompt in an agent and how do you design an effective one?

<details>
<summary>View Answer</summary>

The system prompt defines the agent's identity, capabilities, constraints, and behavioral guidelines. It is the most critical piece of prompt engineering in an agent system. An effective system prompt includes: (1) **role definition** -- who the agent is and what it does; (2) **tool descriptions** -- what tools are available and when to use each; (3) **behavioral rules** -- guidelines for tone, format, and decision-making; (4) **constraints** -- what the agent should NOT do (scope limitations, safety rules); (5) **output format** -- how to structure responses (especially for structured output). Design principles: be specific and explicit (ambiguity causes inconsistent behavior), use examples for complex behaviors, prioritize critical instructions at the beginning and end of the prompt (due to attention patterns), and keep it as concise as possible (every token costs money and reduces available context). In production, version-control your system prompts and run evaluation suites whenever you change them.

</details>

---

## Q12. How do you implement human-in-the-loop (HITL) in agent workflows?

<details>
<summary>View Answer</summary>

Human-in-the-loop patterns insert human review or approval at critical points in the agent's execution. Common HITL patterns include: (1) **approval gates** -- the agent proposes an action (e.g., send email, execute trade) and pauses for human approval before executing; (2) **review and edit** -- the agent generates a draft and a human reviews/modifies it before it is sent; (3) **escalation** -- the agent detects it is uncertain or the task is out of scope and escalates to a human; (4) **feedback loops** -- humans rate agent outputs, and ratings are used to improve the system over time. Implementation requires: a state persistence mechanism (so the workflow can pause and resume), a notification system (to alert humans), a UI for review/approval, and timeout handling (what happens if the human does not respond). LangGraph supports HITL natively through its `interrupt_before` and `interrupt_after` parameters on nodes, combined with checkpoint-based state persistence. In interviews, emphasize that HITL is not a failure of AI -- it is a responsible design pattern for high-stakes decisions.

</details>

---

## Q13. What is the planning capability of an agent and what strategies exist?

<details>
<summary>View Answer</summary>

Planning is the agent's ability to decompose a complex goal into a sequence of sub-tasks and execute them in a reasoned order. Key planning strategies include: (1) **ReAct** -- interleaved reasoning and acting, planning one step at a time; (2) **Plan-and-Execute** -- generate a complete plan upfront, then execute steps sequentially, revising the plan if needed; (3) **Tree of Thought (ToT)** -- explore multiple reasoning paths simultaneously and select the best one; (4) **Reflexion** -- after completing a task, reflect on what went well and what did not, then retry with improved strategy; (5) **LLM Compiler** -- decompose into independent sub-tasks that can run in parallel, then combine results. Plan-and-Execute is best for complex, multi-step tasks where the overall structure is important. ReAct is best for simpler tasks where one-step-at-a-time planning suffices. ToT is best for tasks with high uncertainty where exploring alternatives has value. The trade-off is always between planning quality and cost: more sophisticated planning requires more LLM calls.

</details>

---

## Q14. How do you manage the context window in long-running agent interactions?

<details>
<summary>View Answer</summary>

Long-running agents accumulate tokens from conversation history, tool results, and reasoning steps. Context window management strategies include: (1) **sliding window** -- keep only the most recent N messages, dropping the oldest; (2) **summarization** -- periodically summarize the conversation history into a shorter form; (3) **selective retention** -- keep system prompt and recent messages, summarize middle portion; (4) **retrieval-based memory** -- store all messages externally and retrieve only the relevant ones for the current query; (5) **tool output truncation** -- limit the length of tool results before feeding them back to the LLM; (6) **scratchpad compression** -- summarize the agent's reasoning history rather than keeping the full trace. The optimal strategy depends on the application: customer support might use a sliding window (last 10 turns); a research agent might use retrieval-based memory (find relevant past findings). Always monitor token usage per interaction and set alerts when approaching context limits. Token counting libraries (like `tiktoken`) help predict when you are approaching the limit.

</details>

---

## Q15. What are the key metrics for evaluating an agent system in production?

<details>
<summary>View Answer</summary>

Production agent metrics span four categories. **Task performance**: task completion rate, answer accuracy, tool selection accuracy, and end-to-end success rate. **Efficiency**: average tokens per query, average LLM calls per task, average latency (time to first token, total response time), and cost per query. **Reliability**: error rate, timeout rate, infinite loop rate, guardrail trigger rate, and fallback/escalation rate. **User experience**: user satisfaction scores (thumbs up/down), conversation length, retry rate (how often users rephrase), and abandonment rate. For each metric, define acceptable thresholds: e.g., task completion rate above 90%, p95 latency under 10 seconds, error rate below 1%. Track these metrics in dashboards and set up alerting for regressions. In interviews, mention that you should also track **cost efficiency** (cost per successful task, not just cost per query) and **safety metrics** (harmful output rate, prompt injection success rate). The most important meta-metric is the ratio of successful tasks to total LLM calls -- this measures the agent's ability to achieve goals efficiently.

</details>
