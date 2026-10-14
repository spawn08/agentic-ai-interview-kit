---
sidebar_position: 5
title: "Framework Questions"
description: "19 Q&A comparing and questioning LangChain, LangGraph, CrewAI, LlamaIndex, Microsoft Agent Framework, and other current agentic AI frameworks (with AutoGen and Semantic Kernel as legacy context)."
last_verified: 2026-10-12
---

# Framework Questions

These 19 questions test your practical knowledge of the major agentic AI frameworks. Interviewers want to see that you have hands-on experience, understand the trade-offs between frameworks, and can make informed technology choices.

:::info Framework Landscape (as of early 2026)
The current framework taxonomy (see the [Framework Comparison](../frameworks/framework-comparison.md)): **LangChain** (high-level agents and integrations), **LangGraph** (stateful graphs, durable execution), **CrewAI** (role/task Crews and event-driven Flows), **Microsoft Agent Framework** (Microsoft's successor to AutoGen and Semantic Kernel), **LlamaIndex** (workflow-based, data-centric agents), **OpenAI Agents SDK**, **Claude Agent SDK**, **Google ADK**, and **PydanticAI** (typed agents). **AutoGen** and **Semantic Kernel** are legacy: AutoGen is in maintenance mode and Semantic Kernel has Microsoft Agent Framework as its successor (verified 2026-10-12; no dates are claimed). Each has a sweet spot.
:::

---

## Q1. What is LangChain and what problem does it solve?

<details>
<summary>View Answer</summary>

LangChain is a Python (and TypeScript) framework that provides composable building blocks for LLM-powered applications. It solves the problem of integrating LLMs with external data sources, tools, and memory by providing standardized abstractions: **Models** (unified interface across LLM providers), **Prompts** (templates and management), **Chains** (sequences of operations), **Tools** (function integration), **Memory** (conversation state), and **Retrievers** (RAG integration). LangChain's key value proposition is its extensive ecosystem of integrations -- it supports dozens of LLM providers, vector stores, and tool connectors out of the box. Its limitations include: a steep learning curve due to frequent API changes, overly abstracted internals that make debugging difficult, and performance overhead from its abstraction layers. In interviews, mention that LangChain is best used for rapid prototyping and when you need its integrations, but for production systems you may want to use LangGraph (for workflows) or build custom implementations where you need full control.

</details>

---

## Q2. How does LangGraph differ from LangChain, and when should you use it?

<details>
<summary>View Answer</summary>

LangGraph is a library built on top of LangChain that models agent workflows as **directed graphs with state**. LangChain's `create_agent` (which runs on LangGraph) provides a ready-made loop (call model, maybe call tools, repeat) that you customize with **middleware** hooks such as `before_model`, `wrap_tool_call`, and `after_model`. When the topology itself is custom, a LangGraph `StateGraph` makes the control flow explicit: you define nodes (processing steps), edges (transitions), and conditional edges (branching logic). Key differentiators: (1) **explicit state management** -- state is a typed dictionary that flows through the graph, with reducer functions for merging; (2) **persistent checkpointing** -- state is saved at each step, enabling pause/resume, time-travel debugging, and human-in-the-loop; (3) **cycles and branching** -- unlike chains, LangGraph supports loops (retry patterns) and conditional branching natively; (4) **streaming** -- you can stream the execution of the graph, observing each node's output in real time. Use LangGraph when: you need complex, multi-step workflows with branching logic; you need HITL approval gates; you need state persistence across sessions; or you need fine-grained control over the agent's execution flow. Stick with simple LangChain chains for straightforward, linear pipelines.

</details>

---

## Q3. What is CrewAI and how does its approach to multi-agent differ from other frameworks?

<details>
<summary>View Answer</summary>

CrewAI is a framework for building multi-agent systems where specialized agents collaborate on tasks. Its distinctive approach is role-based: each agent has a **role** (e.g., "Senior Researcher"), a **goal**, a **backstory** (which shapes its behavior), and a set of **tools**. Agents are organized into a **Crew** that executes **Tasks** in sequence or hierarchically. CrewAI's key differentiators: (1) **role-playing** -- the backstory prompts produce more focused, personality-consistent outputs than generic agents; (2) **delegation** -- agents can delegate sub-tasks to other agents in the crew; (3) **process types** -- sequential (fixed order), hierarchical (manager delegates), and consensual (agents vote); (4) **built-in memory** -- short-term, long-term, and entity memory across tasks. Compared to AutoGen (which focuses on conversational multi-agent patterns), CrewAI is more structured and task-oriented. Compared to LangGraph (which gives you low-level graph control), CrewAI is higher-level and opinionated. Use CrewAI for content creation pipelines, research workflows, and other scenarios where role-based specialization is natural.

</details>

---

## Q4. Explain AutoGen (AG2) and its conversational agent pattern.

<details>
<summary>View Answer</summary>

AutoGen (recently rebranded to AG2) is Microsoft's framework for building multi-agent systems based on **conversational patterns**. Its core abstraction is the `ConversableAgent` -- agents communicate by sending messages to each other in a conversation. Key concepts: (1) **AssistantAgent** -- an LLM-powered agent that can generate code, reason, and use tools; (2) **UserProxyAgent** -- represents the human, can auto-execute code or request human input; (3) **GroupChat** -- multiple agents in a shared conversation with a manager that selects the next speaker; (4) **nested chats** -- agents can spawn sub-conversations for complex sub-tasks. AutoGen's unique strength is its emphasis on **code generation and execution**: agents can write Python code, execute it in a sandboxed environment, observe the results, and iterate. This makes it excellent for data analysis, code generation, and computational tasks. Compared to CrewAI (role-based, task-focused), AutoGen is conversation-based and code-execution-focused. Its main limitations are: complex configuration for non-trivial setups, the GroupChat manager can be a bottleneck, and debugging multi-agent conversations is challenging.

</details>

---

## Q5. What is the OpenAI Agents SDK and how does it compare to third-party frameworks?

<details>
<summary>View Answer</summary>

The OpenAI Agents SDK is OpenAI's official framework for building agents using their models. It provides: **Agent** (an LLM with instructions, tools, and handoff capabilities), **Handoffs** (transfer control between agents), **Guardrails** (input/output validation), and **Tracing** (built-in observability). Key advantages: (1) tight integration with OpenAI's tool calling and structured output features; (2) native support for agent-to-agent handoffs (useful for routing and escalation patterns); (3) built-in tracing for debugging without external tools; (4) simpler API than LangChain for OpenAI-only deployments. Limitations: (1) vendor lock-in to OpenAI models (the SDK is designed for their API); (2) less flexible than LangGraph for complex, stateful workflows; (3) smaller ecosystem of integrations compared to LangChain; (4) no built-in RAG support (you need to implement your own retrieval). Use the OpenAI Agents SDK when your stack is OpenAI-only and your workflows are relatively straightforward. Use LangGraph when you need complex state management, provider flexibility, or advanced workflow patterns.

</details>

---

## Q6. How does LlamaIndex differ from LangChain in its approach to building agents?

<details>
<summary>View Answer</summary>

LlamaIndex is a **data-centric** framework, while LangChain is an **orchestration-centric** framework. LlamaIndex excels at connecting LLMs to data: it provides sophisticated document loaders, index structures (vector, keyword, tree, knowledge graph), query engines, and retrieval strategies. Its agent capabilities are built on top of this data infrastructure and, in current LlamaIndex, run on Workflows: `FunctionAgent` (uses the LLM provider's function/tool-calling capability), `ReActAgent` and `CodeActAgent` (other prompting strategies for executing tools), and `AgentWorkflow` (combines agents that hand off control to each other). Key differences: (1) **indexing flexibility** -- LlamaIndex offers multiple index types beyond simple vector stores, including summary indexes, tree indexes, and composable indexes; (2) **query pipelines** -- structured query transformation and routing; (3) **data agents** -- agents that specialize in querying and synthesizing from structured and unstructured data; (4) **sub-question query engine** -- automatically decomposes complex queries into sub-questions targeted at different data sources. Choose LlamaIndex when your application is primarily about querying and synthesizing from complex data sources (multiple document collections, databases, APIs). Choose LangChain/LangGraph when your application is primarily about orchestrating tools, managing workflows, and handling complex control flow. In practice, many production systems use both: LlamaIndex for the data/retrieval layer and LangChain/LangGraph for the agent orchestration layer.

</details>

---

## Q7. What is Semantic Kernel and what audience is it designed for?

<details>
<summary>View Answer</summary>

Semantic Kernel is Microsoft's open-source SDK for integrating AI into applications, designed primarily for **enterprise .NET and Python developers**. Its core abstractions are: **Kernel** (the orchestration engine), **Plugins** (collections of functions the AI can call), **Planners** (automated plan generation from goals), and **Memory** (conversation and semantic memory). Key differentiators: (1) **enterprise-first** -- deep integration with Azure OpenAI, Microsoft 365, and the Microsoft ecosystem; (2) **plugin architecture** -- functions are organized into plugins that can be shared and reused, similar to OpenAPI specifications; (3) **C#/.NET support** -- one of the few frameworks with first-class .NET support, making it the default choice for Microsoft-stack enterprises; (4) **process framework** -- built-in support for business process automation with state machines. Compared to LangChain, Semantic Kernel is more opinionated and enterprise-focused, with less community-driven experimentation but better corporate support. Use Semantic Kernel when building on the Microsoft/Azure stack, when you need .NET support, or when enterprise governance and plugin reusability are priorities.

</details>

---

## Q8. How do you choose between frameworks for a new project?

<details>
<summary>View Answer</summary>

Framework selection depends on six factors: (1) **Task type** -- RAG-heavy applications favor LlamaIndex; complex workflows favor LangGraph; multi-agent collaboration favors CrewAI or AutoGen; simple tool-calling favors the OpenAI Agents SDK. (2) **Team expertise** -- if your team knows Python well and wants fine-grained control, LangGraph is ideal; if they want high-level abstractions, CrewAI is faster to start with. (3) **Provider flexibility** -- if you need to swap between OpenAI, Anthropic, and open-source models, LangChain's provider abstraction helps; if you are all-in on OpenAI, the Agents SDK is simpler. (4) **Production requirements** -- LangGraph's checkpointing and state management are built for production; CrewAI is better for batch workflows than real-time serving. (5) **Ecosystem needs** -- LangChain has the largest integration ecosystem (vector stores, tools, loaders); this matters if you need specific connectors. (6) **Long-term maintenance** -- frameworks evolve rapidly; consider community size, release cadence, and breaking change history. My recommendation: start with LangGraph for most production agent systems, use LlamaIndex for the retrieval layer, and only bring in CrewAI or AutoGen for genuinely multi-agent use cases.

</details>

---

## Q9. What are the common criticisms of LangChain and how are they being addressed?

<details>
<summary>View Answer</summary>

Common criticisms include: (1) **over-abstraction** -- too many layers of abstraction make it hard to understand what is happening under the hood, making debugging painful; (2) **frequent breaking changes** -- the API changed significantly between versions, requiring constant code updates; (3) **performance overhead** -- the abstraction layers add latency and memory usage compared to direct API calls; (4) **magic behavior** -- some components have implicit behaviors that are not obvious from the documentation; (5) **documentation gaps** -- rapid development outpaced documentation. These are being addressed: LangChain has stabilized its core API (LCEL -- LangChain Expression Language), moved complex orchestration to LangGraph (which has cleaner abstractions), improved documentation significantly, and released LangSmith for observability (making debugging easier). The practical advice for interviews: acknowledge these criticisms honestly, note the improvements, and emphasize that the right approach is to use LangChain's integration ecosystem while building critical orchestration logic in LangGraph or custom code. Do not be dogmatic about frameworks -- use them where they add value and bypass them where they add friction.

</details>

---

## Q10. How does tool definition differ across frameworks?

<details>
<summary>View Answer</summary>

Each framework has its own approach to tool definition. **OpenAI API**: JSON Schema objects describing function name, description, and parameters -- the most explicit and verbose approach. **LangChain**: The `@tool` decorator on Python functions, which auto-generates the schema from the function signature and docstring. **CrewAI**: Uses the `@tool` decorator from `crewai.tools`, similar to LangChain but with additional metadata (name override, caching). **AutoGen**: Functions registered on agents via `register_for_llm()` and `register_for_execution()`, separating the LLM's knowledge of the tool from its execution. **LlamaIndex**: `FunctionTool.from_defaults()` wrapping a function. **Semantic Kernel**: Functions decorated with `@kernel_function`, organized into plugins. The key insight for interviews: regardless of framework, the fundamental information is the same -- a name, a description, and a parameter schema. Good tool descriptions are more important than the framework choice. The description is what the LLM uses to decide when to call the tool, so it should clearly state the tool's purpose, when to use it, when NOT to use it, and provide example inputs if the usage is non-obvious.

</details>

---

## Q11. How do you implement memory in LangGraph vs. CrewAI vs. AutoGen?

<details>
<summary>View Answer</summary>

**LangGraph** uses explicit state management: the state object (TypedDict) flows through the graph, and a checkpointer (MemorySaver, PostgresSaver) persists it between invocations. You define exactly what is in state and how it is updated (via reducer functions). Memory across sessions is achieved by using the same `thread_id` in the config. **CrewAI** provides three memory types out of the box: short-term memory (conversation within a task), long-term memory (learnings across crew executions, stored in a local SQLite database), and entity memory (facts about specific entities mentioned in interactions). Enable with `memory=True` on the Crew. **AutoGen** maintains memory through the conversation history itself -- messages between agents are the memory. For persistent memory, you implement custom message stores or use AutoGen's `Teachability` capability, which lets agents learn and recall information across sessions. The key trade-off: LangGraph gives you the most control (you own the state schema) but requires more setup. CrewAI is the most batteries-included but less flexible. AutoGen's conversational memory is natural for dialogue-heavy applications but can grow unbounded. For interviews, emphasize that memory architecture should match the use case: customer support needs session memory (LangGraph), collaborative content creation benefits from shared task memory (CrewAI), and iterative problem-solving benefits from conversational memory (AutoGen).

</details>

---

## Q12. How do frameworks handle error recovery differently?

<details>
<summary>View Answer</summary>

**LangChain/LangGraph**: with `create_agent`, tool errors are handled in middleware (`wrap_tool_call`, or built-ins such as `ToolRetryMiddleware` and `ModelRetryMiddleware`), and with native tool calling there is no text format to mis-parse; schema validation failures on tool arguments come back to the model as error messages it can correct. (The old `AgentExecutor` `handle_parsing_errors=True` option exists only in legacy `langchain-classic`.) A custom LangGraph `StateGraph` adds graph-level error handling: you can define error nodes and error edges, and the checkpointer allows manual state correction and replay. **CrewAI**: Agents have `max_iter` (iteration limit) and `max_retry_limit` parameters. The framework automatically retries failed tool calls and LLM calls. For task-level errors, you can define fallback tasks. **AutoGen**: Error handling is conversational -- if an agent produces an error, the other agents in the group chat see it and can respond. Code execution errors are returned to the AssistantAgent, which can fix the code. The UserProxyAgent can intervene if auto-retry fails. **OpenAI Agents SDK**: Built-in retry logic for API errors and rate limits. Guardrails can catch and handle invalid outputs before they reach the user. The practical recommendation for interviews: framework-level error handling is a starting point, not a complete solution. Production systems need additional layers: circuit breakers for external services, dead letter queues for messages that repeatedly fail, structured logging for debugging, and alerting on error rate spikes.

</details>

---

## Q13. Compare the observability and debugging capabilities across frameworks.

<details>
<summary>View Answer</summary>

**LangChain/LangGraph + LangSmith**: LangSmith is the most mature observability solution -- it captures every LLM call, tool invocation, and chain step with full input/output logging, latency tracking, and cost estimation. Supports trace replay, dataset creation from production traces, and online evaluation. **CrewAI**: Has built-in verbose logging and integrates with third-party tracing (LangSmith, Arize). The `verbose=True` flag prints each agent's reasoning steps. Crew execution produces a structured log of task delegation and completion. **AutoGen**: Provides conversation logging and can export full chat histories. Less structured tracing than LangSmith but the conversational format is naturally readable. **OpenAI Agents SDK**: Built-in tracing that captures agent runs, tool calls, and handoffs. Can be viewed in the OpenAI dashboard. **LlamaIndex**: Integrates with observability platforms (Arize, Weights & Biases) and provides callback-based tracing. For interviews, the important point is that observability is not optional for production agents. If your chosen framework does not have good built-in observability, integrate with a platform like LangSmith, Arize Phoenix, or build custom tracing using OpenTelemetry. The minimum viable observability for any agent includes: every LLM call logged with input, output, tokens, and latency; every tool call logged with arguments and results; and end-to-end trace linking for debugging.

</details>

---

## Q14. What is LCEL (LangChain Expression Language) and why was it introduced?

<details>
<summary>View Answer</summary>

LCEL is a declarative composition syntax introduced in LangChain to replace the earlier imperative chain-building approach. It uses the pipe operator (`|`) to compose components: `prompt | llm | output_parser`. LCEL was introduced to address several problems: (1) **consistency** -- all components implement the `Runnable` interface with `.invoke()`, `.stream()`, `.batch()`, and `.ainvoke()` methods, so any component can be swapped without changing the composition; (2) **streaming** -- LCEL chains support streaming end-to-end, passing tokens through the pipeline as they are generated; (3) **parallelism** -- `RunnableParallel` enables concurrent execution of independent branches; (4) **fallbacks** -- `.with_fallbacks()` chains alternative components for error recovery; (5) **configuration** -- `.with_config()` and `.configurable_fields()` enable runtime configuration without code changes. While LCEL makes simple chains elegant, it has been criticized for making complex logic harder to read than plain Python (especially with deeply nested RunnablePassthrough and RunnableLambda constructs). The practical advice: use LCEL for simple, linear pipelines; use LangGraph for anything with branching, loops, or complex state.

</details>

---

## Q15. If you were starting a new agentic AI project today, what would your technology stack look like?

<details>
<summary>View Answer</summary>

For a production agentic AI system in early 2026, the recommended stack is: **LLM Provider**: a standard-tier model (`AGENT_MODEL`) for complex reasoning, a fast-tier model (`AGENT_MODEL_FAST`) for simple tasks, with a second provider's model (`AGENT_MODEL_ALT`) as a fallback. Consider open-source models (Llama 3) for cost-sensitive or privacy-sensitive components. **Orchestration**: LangGraph for the agent workflow, with explicit state management and checkpointing. **Retrieval**: LlamaIndex for document processing and indexing, with a hybrid search strategy (vector + BM25). **Vector Store**: Qdrant or Weaviate for production (managed options available), ChromaDB for development. **Memory**: Redis for session state, PostgreSQL for long-term memory, vector store for semantic memory. **Observability**: LangSmith for development and testing, OpenTelemetry + Grafana for production monitoring. **Evaluation**: Custom evaluation harness with LLM-as-judge scoring, integrated into CI/CD. **Guardrails**: Input validation (prompt injection detection), output validation (content moderation), and tool-level authorization. **Deployment**: Containerized (Docker/Kubernetes) with autoscaling based on queue depth. This stack optimizes for production readiness, observability, and flexibility. The key principle is to use frameworks where they add value (integrations, state management) and bypass them where they add unnecessary complexity (simple API calls, custom tools).

</details>

---

## Q16. How do frameworks expose native (provider-run) tools, and what should you check?

**Level: Mid**

<details>
<summary>View Answer</summary>

**30-second answer:** Check whether the framework passes the provider's built-in tools (web search, code execution, remote MCP) through to the API, or only supports tools you define. If it does not, you either wrap the capability as a client tool or call the provider SDK directly.

**2-minute answer:** Native tool support is provider-specific: OpenAI's tools guide lists built-ins such as web search, file search, code interpreter, computer use, and remote MCP; Claude's tool docs describe server tools Anthropic executes, such as web search. A framework abstraction may expose some, all, or none of them, and its tracing and guardrail hooks may not see calls executed by the vendor. Checklist: (1) does the framework version you use expose the tool and its result blocks; (2) do your traces and logs capture vendor-executed calls; (3) can you restrict the tool (domains, usage limits); (4) what happens when you switch providers -- native tools do not port, so isolate them behind your own interface. Confirm against the framework's current docs rather than assuming.

</details>

## Q17. How do current frameworks relate to MCP, and why does the spec version matter?

**Level: Mid**

<details>
<summary>View Answer</summary>

**30-second answer:** Most frameworks act as MCP clients through an adapter or SDK. The spec version matters because the 2026-07-28 revision is stateless (no initialize handshake or protocol sessions), so a client or server written for an older revision may need an update to interoperate.

**2-minute answer:** In a framework, MCP tools typically appear as ordinary tools after an adapter converts them. Questions to ask: which MCP spec revision does the framework's MCP client implement; does it assume a persistent session (for example, caching tool lists per connection or relying on connection-scoped state); and how does it handle server-minted handles. Do not state that a framework "supports MCP" without a version -- say, for example, "supports the 2026-07-28 revision" only after checking its release notes. Operationally: pin versions of the framework and MCP SDK, test against the servers you actually use, and treat third-party MCP servers as untrusted supply chain (OWASP lists agentic supply-chain vulnerabilities as ASI04).

</details>

## Q18. Does your framework let you control reasoning effort, and what happens if it does not?

**Level: Mid**

<details>
<summary>View Answer</summary>

**30-second answer:** Check that the framework forwards the provider's effort or reasoning setting to the API. If it does not, the setting never reaches the model and you get the default, so you may pay for more reasoning than needed or get less than required.

**2-minute answer:** Effort and thinking controls are provider API parameters (for example, Claude's `output_config.effort`, with levels whose availability varies by model). Framework wrappers differ in whether they expose them as first-class options, pass-through keyword arguments, or not at all, and in whether they preserve the provider's thinking output across tool-call turns. Verify by inspecting the actual request (via tracing or a proxy) rather than trusting the constructor argument. Consider making effort a per-node setting in graph frameworks: cheap for routing and formatting nodes, higher for planning and verification nodes. And record the effort level in traces so cost and quality can be compared across runs.

</details>

## Q19. How do you attribute a result to the framework, the model, or your harness code?

**Level: Senior**

<details>
<summary>View Answer</summary>

**30-second answer:** The framework is part of your harness, not a separate layer to blame or credit. To attribute, vary one thing at a time: same model with different orchestration code, then same orchestration code with a different model, on one fixed eval set.

**2-minute answer:** Frameworks decide defaults that quietly affect results: prompt templates, how context is trimmed, retry behavior, how tool errors are surfaced, and what state is persisted. So a result like "LangGraph beat CrewAI" usually means "this harness design with these defaults beat that one". To make a defensible comparison: (1) fix the model, tools, and eval; (2) disable or standardize framework defaults you do not control (prompts, retries, truncation); (3) run multiple trials and report variance and cost per success; (4) inspect traces to confirm the framework did what you think it did. If a migration improves results, check whether it was the framework or the rewrite you did while migrating. Frameworks mainly buy you speed of development, observability, and persistence; they do not by themselves make the model smarter.

</details>

*Sources (checked 2026-10-12): [Claude tool use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview), [OpenAI tools guide](https://developers.openai.com/api/docs/guides/tools), [MCP specification 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) and its [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), [Claude effort](https://platform.claude.com/docs/en/build-with-claude/effort) and [adaptive thinking](https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost), [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).*
