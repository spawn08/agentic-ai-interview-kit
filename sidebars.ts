import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  learningPath: [
    'index',
    {
      type: 'category',
      label: '1. Foundations',
      collapsed: false,
      link: {type: 'generated-index', description: 'Prerequisite knowledge for understanding agentic AI.'},
      items: [
        'foundations/llm-fundamentals',
        'foundations/prompting-techniques',
        'foundations/embeddings-and-vector-stores',
        'foundations/rag-basics',
        'foundations/fine-tuning-overview',
        'foundations/evaluation-metrics',
      ],
    },
    {
      type: 'category',
      label: '2. Core Concepts',
      collapsed: false,
      link: {type: 'generated-index', description: 'What makes an AI system agentic.'},
      items: [
        'core-concepts/what-are-agents',
        'core-concepts/tools-and-function-calling',
        'core-concepts/planning-and-reasoning',
        'core-concepts/memory-systems',
        'core-concepts/agent-architectures',
        'core-concepts/guardrails-and-safety',
      ],
    },
    {
      type: 'category',
      label: '3. Design Patterns',
      link: {type: 'generated-index', description: 'Proven patterns for building agent behaviors.'},
      items: [
        'design-patterns/react-pattern',
        'design-patterns/chain-of-thought',
        'design-patterns/tool-use-pattern',
        'design-patterns/reflection-pattern',
        'design-patterns/multi-agent-pattern',
        'design-patterns/plan-and-execute',
        'design-patterns/self-refinement',
        'design-patterns/human-in-the-loop',
      ],
    },
    {
      type: 'category',
      label: '4. Frameworks',
      link: {type: 'generated-index', description: 'Hands-on guides for popular agentic AI frameworks.'},
      items: [
        'frameworks/langchain-overview',
        'frameworks/langgraph-deep-dive',
        'frameworks/crewai-guide',
        'frameworks/autogen-guide',
        'frameworks/semantic-kernel',
        'frameworks/llamaindex-agents',
        'frameworks/openai-assistants-api',
        'frameworks/framework-comparison',
      ],
    },
    {
      type: 'category',
      label: '5. Implementations',
      link: {type: 'generated-index', description: 'Runnable code examples for building agentic AI systems.'},
      items: [
        'implementations/basic-react-agent',
        'implementations/rag-agent-with-tools',
        'implementations/multi-agent-crew',
        'implementations/langgraph-workflow',
        'implementations/tool-calling-agent',
        'implementations/evaluation-harness',
      ],
    },
  ],

  systemDesign: [
    {
      type: 'category',
      label: 'Principles & Patterns',
      collapsed: false,
      link: {type: 'generated-index', description: 'Designing agentic systems at production scale.'},
      items: [
        'system-design/design-principles',
        'system-design/agent-orchestration-at-scale',
        'system-design/memory-and-state-management',
        'system-design/tool-registry-design',
        'system-design/multi-agent-communication',
        'system-design/error-handling-and-recovery',
        'system-design/observability-and-tracing',
        'system-design/security-considerations',
      ],
    },
    {
      type: 'category',
      label: 'Case Studies',
      collapsed: false,
      link: {type: 'generated-index', description: 'End-to-end system design walkthroughs with architecture diagrams.'},
      items: [
        'system-design/case-study-customer-support',
        'system-design/case-study-code-assistant',
        'system-design/case-study-data-pipeline',
        'system-design/case-study-research-agent',
        'system-design/case-study-ai-coding-assistant',
        'system-design/case-study-chatgpt-for-autodesk',
        'system-design/case-study-design-review-system',
        'system-design/case-study-rag-engineering-docs',
        'system-design/case-study-cad-modifier-agent',
        'system-design/case-study-building-plan-generator',
        'system-design/case-study-agent-memory-system',
        'system-design/case-study-agent-evaluation-platform',
        'system-design/case-study-workflow-orchestrator',
      ],
    },
  ],

  interviewPrep: [
    {
      type: 'category',
      label: 'Interview Questions',
      collapsed: false,
      link: {type: 'generated-index', description: 'Comprehensive question bank for agentic AI interviews.'},
      items: [
        'interview-questions/foundational-qa',
        'interview-questions/agent-architecture-qa',
        'interview-questions/design-pattern-qa',
        'interview-questions/system-design-qa',
        'interview-questions/framework-qa',
        'interview-questions/coding-challenges',
        'interview-questions/behavioral-and-scenario',
      ],
    },
  ],
};

export default sidebars;
