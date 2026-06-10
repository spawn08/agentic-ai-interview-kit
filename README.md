# Agentic AI Interview Kit

[![GitHub Pages](https://img.shields.io/badge/docs-live-brightgreen?style=flat&logo=github)](https://spawn08.github.io/agentic-ai-interview-kit/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Built with Docusaurus](https://img.shields.io/badge/built%20with-Docusaurus-5b21b6?logo=docusaurus)](https://docusaurus.io/)
[![Node.js](https://img.shields.io/badge/node-%3E%3D20.0-339933?logo=node.js&logoColor=white)](https://nodejs.org/)

**The comprehensive, open-source study guide for mastering agentic AI -- from foundations to production system design.** Built for engineers preparing for interviews and practitioners building real-world agentic systems.

[**Read the Docs**](https://spawn08.github.io/agentic-ai-interview-kit/) | [**Report an Issue**](https://github.com/spawn08/agentic-ai-interview-kit/issues) | [**Contribute**](https://github.com/spawn08/agentic-ai-interview-kit/pulls)

---

## Why This Exists

Agentic AI -- systems where LLMs autonomously observe, reason, act, and learn -- is becoming the dominant architecture for intelligent applications. Yet there is no single, structured resource that covers the full spectrum from foundational LLM knowledge through production system design, all organized for interview preparation.

This project fills that gap with **60+ in-depth pages** covering theory, design patterns, framework walkthroughs, runnable code, system design case studies, and a comprehensive interview question bank.

---

## What's Inside

The guide is organized into seven progressive sections. Each builds on the previous one.

### Learning Path

| # | Section | Topics | Pages |
|---|---------|--------|-------|
| 1 | **Foundations** | LLM internals, prompting, embeddings, RAG, fine-tuning, evaluation metrics | 6 |
| 2 | **Core Concepts** | Agent loop, tool use, memory architectures, planning & reasoning, guardrails | 6 |
| 3 | **Design Patterns** | ReAct, Chain-of-Thought, reflection, multi-agent, plan-and-execute, HITL | 8 |
| 4 | **Frameworks** | LangChain, LangGraph, CrewAI, AutoGen, Semantic Kernel, LlamaIndex, OpenAI | 8 |
| 5 | **Implementations** | ReAct agent, RAG agent, multi-agent crew, LangGraph workflow, eval harness | 6 |

### System Design

| Section | Topics | Pages |
|---------|--------|-------|
| **Principles & Patterns** | Orchestration, state management, tool registries, observability, security | 8 |
| **Case Studies** | Customer support, code assistant, data pipeline, research agent, and 9 more | 13 |

### Interview Prep

| Section | Topics | Pages |
|---------|--------|-------|
| **Question Bank** | Foundational, architecture, design patterns, system design, framework, coding, behavioral | 7 |

---

## Quick Start

### Prerequisites

- [Node.js](https://nodejs.org/) >= 20.0
- npm (included with Node.js)

### Local Development

```bash
# Clone the repository
git clone https://github.com/spawn08/agentic-ai-interview-kit.git
cd agentic-ai-interview-kit

# Install dependencies
npm install

# Start the development server
npm start
```

The site opens at `http://localhost:3000/agentic-ai-interview-kit/`. Changes to Markdown files are reflected instantly via hot reload.

### Production Build

```bash
# Generate static output
npm run build

# Preview the production build locally
npm run serve
```

Static output is written to the `build/` directory and can be deployed to any static hosting service.

---

## Where Should I Start?

| Your Experience | Start Here | Time Estimate |
|-----------------|------------|---------------|
| New to LLMs | [Foundations: LLM Fundamentals](https://spawn08.github.io/agentic-ai-interview-kit/foundations/llm-fundamentals) | 20--25 hours (full guide) |
| Comfortable with LLMs, new to agents | [Core Concepts: What Are Agents](https://spawn08.github.io/agentic-ai-interview-kit/core-concepts/what-are-agents) | 15--18 hours |
| Built simple agents, want depth | [Design Patterns: ReAct](https://spawn08.github.io/agentic-ai-interview-kit/design-patterns/react-pattern) | 10--12 hours |
| Experienced practitioner, interview prep | [Interview Questions](https://spawn08.github.io/agentic-ai-interview-kit/interview-questions/foundational-qa) | 5--8 hours |

---

## Project Structure

```
agentic-ai-interview-kit/
├── docs/                          # All documentation content (Markdown + MDX)
│   ├── index.md                   # Landing page
│   ├── foundations/               # Section 1: LLM fundamentals
│   ├── core-concepts/             # Section 2: Agent building blocks
│   ├── design-patterns/           # Section 3: Architectural patterns
│   ├── frameworks/                # Section 4: Framework guides
│   ├── implementations/           # Section 5: Runnable code examples
│   ├── system-design/             # Section 6: System design & case studies
│   └── interview-questions/       # Section 7: Question bank
├── src/css/                       # Custom theme styles
├── static/                        # Static assets (images, favicons)
├── docusaurus.config.ts           # Site configuration
├── sidebars.ts                    # Navigation structure
└── package.json
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Static site generator | [Docusaurus 3](https://docusaurus.io/) |
| Diagrams | [Mermaid](https://mermaid.js.org/) (rendered natively) |
| Search | [docusaurus-search-local](https://github.com/easyops-cn/docusaurus-search-local) |
| Hosting | [GitHub Pages](https://pages.github.com/) |
| Code highlighting | [Prism](https://prismjs.com/) (Python, Bash, JSON, YAML) |

---

## Deployment

The site is deployed to GitHub Pages at:

**https://spawn08.github.io/agentic-ai-interview-kit/**

To deploy manually:

```bash
# Deploy to GitHub Pages via SSH
USE_SSH=true npm run deploy

# Or via HTTPS
GIT_USER=<your-github-username> npm run deploy
```

---

## Contributing

Contributions are welcome -- whether it's fixing a typo, improving an explanation, adding a new case study, or expanding the question bank.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-topic`)
3. Make your changes
4. Run the build to verify (`npm run build`)
5. Submit a pull request

Please ensure all Markdown renders correctly and any code examples are tested against Python 3.10+.

---

## License

This project is open source and available under the [MIT License](LICENSE).

---

<p align="center">
  <strong>Built with care for the agentic AI community.</strong><br/>
  If this resource helped you, consider giving it a star on GitHub.
</p>
