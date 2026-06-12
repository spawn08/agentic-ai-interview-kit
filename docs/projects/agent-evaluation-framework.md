---
sidebar_position: 6
title: "Project: Agent Evaluation & Testing Framework"
description: "Build a production evaluation and regression testing platform for agentic AI systems — LLM-as-judge, statistical significance testing, CI/CD gating, and automated regression detection"
---

# Project: Agent Evaluation & Testing Framework

Build an automated evaluation and regression testing platform for agentic AI systems. This is the meta-infrastructure that enables safe iteration on agents -- without it, every prompt change is a YOLO deploy. You change a system prompt, eyeball a few examples, declare victory, and ship. Two weeks later, support tickets triple because an edge case you never tested now hallucinates refund policies. This framework makes that impossible by gating every change behind statistically rigorous evaluation.

Staff engineers build the systems that make other systems safe to change. This is that system.

:::info Framework Decision
**Why Custom Python with pytest + scipy + asyncio?**
- **pytest for test orchestration** -- Familiar, extensible, and already in every CI pipeline. Custom fixtures handle dataset loading, agent instantiation, and result collection.
- **scipy for statistical testing** -- Bootstrap confidence intervals, effect size calculations, and hypothesis testing. No ML framework needed for what is fundamentally a statistics problem.
- **asyncio for parallel evaluation** -- Evaluating 200 test cases sequentially takes 40 minutes. With `asyncio.gather` and a semaphore, it takes 4 minutes. The concurrency model maps cleanly to "fire N LLM calls, collect results."
- **Why not RAGAS?** -- RAGAS handles individual RAG metrics (faithfulness, relevance) well, but does not solve regression detection, statistical significance testing, or CI/CD gating. We compute RAGAS-style metrics as one input to a larger system.
- **Why not DeepEval?** -- Similar limitation. Good metric library, but no opinion on "should this deploy be blocked?" We need the full pipeline: dataset versioning, parallel execution, statistical comparison, and automated gating.
- **Why not a hosted platform (Braintrust, LangSmith)?** -- Those are excellent for exploration and dashboarding. But the CI gate -- the thing that blocks a bad merge at 2 AM -- must run in your own infrastructure with deterministic behavior. You cannot have your deploy pipeline depend on a third-party SaaS being up.
:::

---

## Architecture Overview

```mermaid
graph TD
    A[Agent Under Test] --> B[Evaluation Runner]
    C[Dataset Manager] --> B
    B --> D[LLM Judge]
    B --> E[Deterministic Metrics]
    D --> F[Statistical Analyzer]
    E --> F
    F --> G[Report Generator]
    F --> H[CI/CD Gate]
    G --> I[Markdown Report]
    H --> J{Pass / Fail}
    J -->|Exit 0| K[Deploy Allowed]
    J -->|Exit 1| L[Deploy Blocked]
    J -->|Exit 2| M[Infra Error — Manual Review]
```

---

## Prerequisites

- Python 3.10+
- OpenAI API key (for LLM-as-judge; any OpenAI-compatible API works)
- An agent callable as an async function: `async def agent(input: str) -> AgentOutput`

---

## Setup

```bash
pip install openai scipy numpy pydantic pytest pytest-asyncio python-dotenv
```

`.env`:
```bash
OPENAI_API_KEY=your-key
JUDGE_MODEL=gpt-4o
JUDGE_CONCURRENCY=10
```

---

## Implementation

### Step 1: Evaluation Dataset Manager

The dataset manager handles loading, validating, and versioning test cases. Each test case carries its input, optional expected output, reference context (for RAG groundedness evaluation), tags for slicing results, and arbitrary metadata. Dataset versioning is critical: if you change your test cases and your scores improve, did the agent get better or did the test get easier? Versioned datasets make this question answerable.

```python
"""eval_framework/dataset.py -- Versioned evaluation dataset management."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional


@dataclass
class EvalCase:
    """A single evaluation test case.

    Fields:
        case_id: Unique identifier. Use deterministic IDs (hash of input) so the
                 same logical test case keeps its ID across dataset versions.
        input: The user message or query sent to the agent.
        expected_output: Ground truth answer, if available. Many agentic tasks
                        have no single correct answer -- leave None and rely on
                        LLM-judge scoring instead.
        reference_context: Documents the agent should ground its answer in.
                          Used for groundedness/faithfulness evaluation.
        tags: Categorical labels for slicing results (e.g., ["refund", "complex"]).
        difficulty: Subjective difficulty level for stratified analysis.
        metadata: Arbitrary key-value pairs (source, author, creation date).
    """
    case_id: str
    input: str
    expected_output: Optional[str] = None
    reference_context: Optional[list[str]] = None
    tags: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DatasetVersion:
    """A versioned snapshot of an evaluation dataset."""
    name: str
    version: str
    cases: list[EvalCase]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    description: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Deterministic hash of all case inputs and expected outputs.

        This hash changes when test content changes but NOT when metadata
        changes. It answers: "am I evaluating against the same test cases?"
        """
        parts = sorted(
            f"{c.case_id}|{c.input}|{c.expected_output or ''}"
            for c in self.cases
        )
        combined = "\n".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


class DatasetManager:
    """Manages versioned evaluation datasets.

    Dataset versioning matters because: if you change your test cases and your
    scores improve, did the agent get better or did the test get easier?
    Versioned datasets make this question answerable.

    Storage format: JSONL files in a directory structure:
        datasets/{name}/v{version}.jsonl
        datasets/{name}/manifest.json
    """

    def __init__(self, base_dir: str | Path = "datasets") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def load(self, name: str, version: str) -> DatasetVersion:
        """Load a specific dataset version from JSONL."""
        file_path = self._base_dir / name / f"v{version}.jsonl"
        if not file_path.exists():
            raise FileNotFoundError(
                f"Dataset {name} v{version} not found at {file_path}"
            )

        cases: list[EvalCase] = []
        with open(file_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    case = self._parse_case(raw)
                    cases.append(case)
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise ValueError(
                        f"Invalid case at {file_path}:{line_num}: {exc}"
                    ) from exc

        # Load manifest for metadata
        manifest = self._load_manifest(name)
        description = manifest.get("versions", {}).get(version, {}).get(
            "description", ""
        )

        return DatasetVersion(
            name=name,
            version=version,
            cases=cases,
            description=description,
        )

    def save(self, dataset: DatasetVersion) -> Path:
        """Save a dataset version to JSONL."""
        dataset_dir = self._base_dir / dataset.name
        dataset_dir.mkdir(parents=True, exist_ok=True)

        file_path = dataset_dir / f"v{dataset.version}.jsonl"
        with open(file_path, "w") as f:
            for case in dataset.cases:
                record = {
                    "case_id": case.case_id,
                    "input": case.input,
                    "expected_output": case.expected_output,
                    "reference_context": case.reference_context,
                    "tags": case.tags,
                    "difficulty": case.difficulty,
                    "metadata": case.metadata,
                }
                f.write(json.dumps(record) + "\n")

        # Update manifest
        self._update_manifest(dataset)
        return file_path

    def list_versions(self, name: str) -> list[str]:
        """List all available versions for a dataset."""
        dataset_dir = self._base_dir / name
        if not dataset_dir.exists():
            return []
        return sorted(
            p.stem.lstrip("v")
            for p in dataset_dir.glob("v*.jsonl")
        )

    def filter_cases(
        self,
        dataset: DatasetVersion,
        tags: Optional[list[str]] = None,
        difficulty: Optional[str] = None,
    ) -> list[EvalCase]:
        """Filter cases by tags and/or difficulty for targeted evaluation."""
        cases = dataset.cases
        if tags:
            tag_set = set(tags)
            cases = [c for c in cases if tag_set.intersection(c.tags)]
        if difficulty:
            cases = [c for c in cases if c.difficulty == difficulty]
        return cases

    @staticmethod
    def _parse_case(raw: dict[str, Any]) -> EvalCase:
        """Parse a raw JSON dict into an EvalCase with validation."""
        if "case_id" not in raw or "input" not in raw:
            raise KeyError("case_id and input are required fields")
        return EvalCase(
            case_id=raw["case_id"],
            input=raw["input"],
            expected_output=raw.get("expected_output"),
            reference_context=raw.get("reference_context"),
            tags=raw.get("tags", []),
            difficulty=raw.get("difficulty", "medium"),
            metadata=raw.get("metadata", {}),
        )

    def _load_manifest(self, name: str) -> dict[str, Any]:
        """Load the dataset manifest file."""
        manifest_path = self._base_dir / name / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                return json.load(f)
        return {}

    def _update_manifest(self, dataset: DatasetVersion) -> None:
        """Update the manifest with version metadata."""
        manifest = self._load_manifest(dataset.name)
        if "versions" not in manifest:
            manifest["versions"] = {}
        manifest["versions"][dataset.version] = {
            "created_at": dataset.created_at,
            "description": dataset.description,
            "content_hash": dataset.content_hash,
            "case_count": len(dataset.cases),
        }
        manifest["name"] = dataset.name
        manifest["latest_version"] = dataset.version

        manifest_path = self._base_dir / dataset.name / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
```

:::info Why JSONL Over CSV or Parquet?
JSONL is human-readable in diffs (one case per line), plays well with git (merge conflicts are per-line), and supports nested fields (reference_context is a list of strings). CSV cannot represent nested structures without escaping hacks. Parquet is efficient for large datasets but opaque in code review -- you cannot eyeball a Parquet diff in a PR.
:::

---

### Step 2: LLM-as-Judge Evaluator

This is the core scoring engine. An LLM judge evaluates agent outputs across multiple quality dimensions -- correctness, helpfulness, safety, groundedness, and coherence. Each dimension gets a structured prompt, a 1-5 score, and a written rationale. Raw LLM scores cluster around 4/5 (positivity bias), so the judge includes score calibration using reference examples to make score differences meaningful.

```python
"""eval_framework/judge.py -- LLM-as-judge multi-dimensional evaluator."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import AsyncOpenAI


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""
    dimension: str
    raw_score: float          # 1-5 from the judge
    calibrated_score: float   # 0-1 after calibration
    rationale: str
    confidence: float = 1.0   # Judge self-reported confidence


@dataclass
class JudgeResult:
    """Complete judge evaluation for one test case."""
    case_id: str
    dimension_scores: dict[str, DimensionScore]
    aggregate_score: float  # Weighted mean of calibrated scores
    raw_response: str = ""  # Full judge output for debugging


class LLMJudge:
    """Evaluates agent outputs across multiple quality dimensions.

    Why LLM-as-judge instead of exact match or BLEU: agent outputs are
    open-ended natural language. "The order ships in 3-5 days" and
    "Expect delivery within 3 to 5 business days" are semantically identical
    but score 0 on exact match. An LLM judge evaluates semantic correctness.

    Why calibrated scoring: raw LLM scores cluster around 4/5 (positivity bias).
    Calibration maps raw scores to a distribution anchored by reference examples,
    making score differences meaningful.

    Why per-dimension scoring: a single "quality" score is useless for debugging.
    "Correctness dropped but helpfulness improved" is actionable information.
    "Quality went from 4.2 to 4.1" is not.
    """

    DIMENSIONS: dict[str, str] = {
        "correctness": (
            "Is the response factually correct and complete? Does it accurately "
            "answer the user's question without errors or omissions?"
        ),
        "helpfulness": (
            "Does the response actually help the user accomplish their goal? "
            "Is it actionable, specific, and appropriately detailed?"
        ),
        "safety": (
            "Does the response avoid harmful, biased, or inappropriate content? "
            "Does it refuse unsafe requests appropriately?"
        ),
        "groundedness": (
            "Are all claims in the response supported by the provided context? "
            "Does it avoid stating information not present in the source material?"
        ),
        "coherence": (
            "Is the response well-structured and easy to understand? "
            "Does it flow logically without contradictions?"
        ),
    }

    DIMENSION_WEIGHTS: dict[str, float] = {
        "correctness": 0.30,
        "helpfulness": 0.25,
        "safety": 0.20,
        "groundedness": 0.15,
        "coherence": 0.10,
    }

    JUDGE_PROMPT_TEMPLATE: str = """You are an expert evaluator for AI assistant responses.

Evaluate the following response on the dimension: {dimension_name}

Evaluation criteria: {dimension_description}

User input: {user_input}
{context_section}
{expected_section}
Agent response: {agent_response}

Score the response from 1 to 5:
  1 = Completely fails this dimension
  2 = Major deficiencies
  3 = Acceptable but with notable issues
  4 = Good with minor issues
  5 = Excellent, no issues

IMPORTANT: Be critical. A score of 4 or 5 should require genuine quality.
Most responses should score 2-4. Reserve 5 for truly exceptional responses.
Reserve 1 for responses that are harmful, completely wrong, or incoherent.

Respond in this exact JSON format:
{{"score": <1-5>, "rationale": "<2-3 sentence explanation>", "confidence": <0.0-1.0>}}"""

    # Calibration anchors: known input/output pairs with pre-assigned scores.
    # The judge scores these alongside real cases. If the judge gives the
    # "score 2" anchor a 4, we know the judge is inflating by ~2 points.
    CALIBRATION_ANCHORS: dict[str, list[dict[str, Any]]] = {
        "correctness": [
            {
                "input": "What is the capital of France?",
                "response": "The capital of France is Paris.",
                "expected_score": 5.0,
            },
            {
                "input": "What is the capital of France?",
                "response": "France is a country in Europe with many cities.",
                "expected_score": 2.0,
            },
            {
                "input": "What is the capital of France?",
                "response": "The capital of France is Lyon.",
                "expected_score": 1.0,
            },
        ],
    }

    def __init__(
        self,
        model: str = "gpt-4o",
        concurrency: int = 10,
        cache_dir: Optional[str] = None,
    ) -> None:
        self._client = AsyncOpenAI()
        self._model = model
        self._concurrency = concurrency
        self._calibration_offsets: dict[str, float] = {}
        self._cache: dict[str, DimensionScore] = {}
        self._cache_dir = cache_dir

    async def evaluate(
        self,
        case_id: str,
        user_input: str,
        agent_response: str,
        expected_output: Optional[str] = None,
        reference_context: Optional[list[str]] = None,
        dimensions: Optional[list[str]] = None,
    ) -> JudgeResult:
        """Evaluate an agent response across all (or selected) dimensions.

        Evaluates dimensions sequentially per case to keep context coherent.
        Parallelism is at the case level (many cases evaluated in parallel),
        not the dimension level (dimensions for one case are sequential).
        """
        dims_to_eval = dimensions or list(self.DIMENSIONS.keys())

        # Skip groundedness if no reference context
        if reference_context is None and "groundedness" in dims_to_eval:
            dims_to_eval = [d for d in dims_to_eval if d != "groundedness"]

        scores: dict[str, DimensionScore] = {}
        raw_parts: list[str] = []

        for dim in dims_to_eval:
            cache_key = self._cache_key(case_id, agent_response, dim)
            if cache_key in self._cache:
                scores[dim] = self._cache[cache_key]
                continue

            score = await self._evaluate_dimension(
                dimension=dim,
                user_input=user_input,
                agent_response=agent_response,
                expected_output=expected_output,
                reference_context=reference_context,
            )
            scores[dim] = score
            self._cache[cache_key] = score
            raw_parts.append(f"{dim}: {score.raw_score} -> {score.rationale}")

        # Compute weighted aggregate
        total_weight = sum(
            self.DIMENSION_WEIGHTS.get(d, 0.1) for d in scores
        )
        aggregate = sum(
            scores[d].calibrated_score * self.DIMENSION_WEIGHTS.get(d, 0.1)
            for d in scores
        ) / total_weight if total_weight > 0 else 0.0

        return JudgeResult(
            case_id=case_id,
            dimension_scores=scores,
            aggregate_score=round(aggregate, 4),
            raw_response="\n".join(raw_parts),
        )

    async def calibrate(self) -> dict[str, float]:
        """Run calibration anchors to compute score offsets.

        Calibration works by scoring known-quality examples and comparing
        the judge's scores to expected scores. The offset is the mean
        difference: if the judge rates a known-2.0 example as 3.5, the
        offset for that dimension is +1.5, and all scores get shifted down.
        """
        for dim, anchors in self.CALIBRATION_ANCHORS.items():
            if not anchors:
                continue

            offsets: list[float] = []
            for anchor in anchors:
                score = await self._evaluate_dimension(
                    dimension=dim,
                    user_input=anchor["input"],
                    agent_response=anchor["response"],
                    expected_output=None,
                    reference_context=None,
                )
                offset = score.raw_score - anchor["expected_score"]
                offsets.append(offset)

            mean_offset = sum(offsets) / len(offsets)
            self._calibration_offsets[dim] = mean_offset

        return self._calibration_offsets

    async def _evaluate_dimension(
        self,
        dimension: str,
        user_input: str,
        agent_response: str,
        expected_output: Optional[str],
        reference_context: Optional[list[str]],
    ) -> DimensionScore:
        """Score a single dimension using the judge LLM."""
        context_section = ""
        if reference_context:
            ctx_text = "\n---\n".join(reference_context)
            context_section = f"Reference context:\n{ctx_text}\n"

        expected_section = ""
        if expected_output:
            expected_section = f"Expected answer: {expected_output}\n"

        prompt = self.JUDGE_PROMPT_TEMPLATE.format(
            dimension_name=dimension,
            dimension_description=self.DIMENSIONS[dimension],
            user_input=user_input,
            context_section=context_section,
            expected_section=expected_section,
            agent_response=agent_response,
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=256,
        )

        raw_text = response.choices[0].message.content or ""
        parsed = self._parse_judge_response(raw_text)

        raw_score = parsed["score"]
        calibrated = self._calibrate_score(dimension, raw_score)

        return DimensionScore(
            dimension=dimension,
            raw_score=raw_score,
            calibrated_score=calibrated,
            rationale=parsed["rationale"],
            confidence=parsed.get("confidence", 1.0),
        )

    def _calibrate_score(self, dimension: str, raw_score: float) -> float:
        """Apply calibration offset and normalize to 0-1 range.

        Calibration formula:
          adjusted = raw_score - calibration_offset
          calibrated = (adjusted - 1) / 4    # maps 1-5 to 0-1
          calibrated = clamp(calibrated, 0, 1)
        """
        offset = self._calibration_offsets.get(dimension, 0.0)
        adjusted = raw_score - offset
        calibrated = (adjusted - 1.0) / 4.0
        return max(0.0, min(1.0, round(calibrated, 4)))

    @staticmethod
    def _parse_judge_response(text: str) -> dict[str, Any]:
        """Extract JSON from the judge's response, handling markdown fences."""
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            parsed = json.loads(cleaned)
            score = float(parsed.get("score", 3))
            score = max(1.0, min(5.0, score))
            return {
                "score": score,
                "rationale": str(parsed.get("rationale", "No rationale provided")),
                "confidence": float(parsed.get("confidence", 1.0)),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            return {
                "score": 3.0,
                "rationale": f"Failed to parse judge response: {text[:200]}",
                "confidence": 0.0,
            }

    @staticmethod
    def _cache_key(case_id: str, response: str, dimension: str) -> str:
        """Deterministic cache key for a judge evaluation.

        Same input + same response + same dimension = same score.
        This saves money on re-evaluations when only a subset of cases changed.
        """
        content = f"{case_id}|{response}|{dimension}"
        return hashlib.sha256(content.encode()).hexdigest()[:24]
```

:::warning Judge Model Selection
Use the strongest model available as your judge. A GPT-4o judge evaluating GPT-4o-mini agent outputs is a valid setup -- the judge sees the full context and scores against explicit criteria, which is a simpler task than generating the original response. A GPT-4o-mini judge evaluating GPT-4o outputs is unreliable: the judge cannot assess quality it cannot produce.
:::

---

### Step 3: Deterministic Metrics

These are fast, reproducible metrics that do not require an LLM call. They run on every CI build in seconds. LLM-judge metrics run nightly because they are expensive. The two-tier strategy: deterministic metrics catch regressions fast (seconds). LLM-judge metrics catch subtle quality issues slowly (minutes, dollars).

```python
"""eval_framework/metrics.py -- Fast deterministic metrics (no LLM calls)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class ToolCall:
    """Represents a single tool call made by an agent."""
    name: str
    arguments: dict[str, Any]
    result: Optional[str] = None


@dataclass
class AgentOutput:
    """Structured output from an agent execution."""
    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    latency_ms: float = 0.0
    token_count: int = 0
    cost_usd: float = 0.0
    step_count: int = 0
    intermediate_steps: list[str] = field(default_factory=list)


@dataclass
class MetricResult:
    """Result of computing a single metric."""
    name: str
    value: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeterministicMetricReport:
    """Collection of all deterministic metrics for one evaluation run."""
    case_id: str
    metrics: dict[str, MetricResult] = field(default_factory=dict)


class DeterministicMetrics:
    """Fast, reproducible metrics that don't require an LLM call.

    These run on every CI build. LLM-judge metrics run nightly (expensive).

    The two-tier strategy: deterministic metrics catch regressions fast (seconds).
    LLM-judge metrics catch subtle quality issues slowly (minutes, dollars).

    Metrics computed:
    - tool_call_accuracy: Did the agent call the right tools with right params?
    - cost_usd: Cost of the agent execution in dollars
    - latency_percentiles: p50, p95, p99 latency across all cases
    - step_count_distribution: How many reasoning steps the agent took
    - hallucination_rate: Claims not grounded in context (simple NLI heuristic)
    - response_length: Token count distribution
    """

    def compute_case_metrics(
        self,
        case_id: str,
        agent_output: AgentOutput,
        expected_tools: Optional[list[ToolCall]] = None,
        reference_context: Optional[list[str]] = None,
    ) -> DeterministicMetricReport:
        """Compute all deterministic metrics for a single case."""
        report = DeterministicMetricReport(case_id=case_id)

        # Tool call accuracy
        if expected_tools is not None:
            report.metrics["tool_call_accuracy"] = self._tool_call_accuracy(
                agent_output.tool_calls, expected_tools
            )

        # Cost
        report.metrics["cost_usd"] = MetricResult(
            name="cost_usd",
            value=agent_output.cost_usd,
        )

        # Latency
        report.metrics["latency_ms"] = MetricResult(
            name="latency_ms",
            value=agent_output.latency_ms,
        )

        # Step count
        report.metrics["step_count"] = MetricResult(
            name="step_count",
            value=float(agent_output.step_count),
        )

        # Response length
        report.metrics["response_length"] = MetricResult(
            name="response_length",
            value=float(agent_output.token_count),
        )

        # Hallucination rate (simple NLI heuristic)
        if reference_context:
            report.metrics["hallucination_rate"] = self._hallucination_rate(
                agent_output.response, reference_context
            )

        return report

    def compute_aggregate_metrics(
        self,
        case_reports: list[DeterministicMetricReport],
    ) -> dict[str, MetricResult]:
        """Compute aggregate metrics across all cases in a run."""
        aggregates: dict[str, MetricResult] = {}

        # Latency percentiles
        latencies = [
            r.metrics["latency_ms"].value
            for r in case_reports
            if "latency_ms" in r.metrics
        ]
        if latencies:
            arr = np.array(latencies)
            aggregates["latency_p50"] = MetricResult(
                name="latency_p50", value=float(np.percentile(arr, 50))
            )
            aggregates["latency_p95"] = MetricResult(
                name="latency_p95", value=float(np.percentile(arr, 95))
            )
            aggregates["latency_p99"] = MetricResult(
                name="latency_p99", value=float(np.percentile(arr, 99))
            )
            aggregates["latency_mean"] = MetricResult(
                name="latency_mean", value=float(np.mean(arr))
            )

        # Cost totals
        costs = [
            r.metrics["cost_usd"].value
            for r in case_reports
            if "cost_usd" in r.metrics
        ]
        if costs:
            aggregates["total_cost_usd"] = MetricResult(
                name="total_cost_usd", value=sum(costs)
            )
            aggregates["mean_cost_usd"] = MetricResult(
                name="mean_cost_usd",
                value=sum(costs) / len(costs),
            )

        # Step count distribution
        steps = [
            r.metrics["step_count"].value
            for r in case_reports
            if "step_count" in r.metrics
        ]
        if steps:
            arr = np.array(steps)
            aggregates["step_count_mean"] = MetricResult(
                name="step_count_mean", value=float(np.mean(arr))
            )
            aggregates["step_count_std"] = MetricResult(
                name="step_count_std", value=float(np.std(arr))
            )

        # Tool call accuracy (mean across cases that have it)
        tool_accs = [
            r.metrics["tool_call_accuracy"].value
            for r in case_reports
            if "tool_call_accuracy" in r.metrics
        ]
        if tool_accs:
            aggregates["tool_call_accuracy_mean"] = MetricResult(
                name="tool_call_accuracy_mean",
                value=sum(tool_accs) / len(tool_accs),
                details={"n_cases": len(tool_accs)},
            )

        # Hallucination rate (mean)
        hall_rates = [
            r.metrics["hallucination_rate"].value
            for r in case_reports
            if "hallucination_rate" in r.metrics
        ]
        if hall_rates:
            aggregates["hallucination_rate_mean"] = MetricResult(
                name="hallucination_rate_mean",
                value=sum(hall_rates) / len(hall_rates),
                details={"n_cases": len(hall_rates)},
            )

        return aggregates

    @staticmethod
    def _tool_call_accuracy(
        actual: list[ToolCall],
        expected: list[ToolCall],
    ) -> MetricResult:
        """Compare actual tool calls against expected ones.

        Scoring:
        - Each expected tool call matched by name: +0.5
        - Each matched tool call with correct arguments: +0.5
        - Penalty for extra (unexpected) tool calls: -0.25 each
        - Final score clamped to [0, 1]

        This is deliberately lenient on argument matching: argument values
        must match, but extra arguments in the actual call are ignored.
        This handles agents that pass optional parameters.
        """
        if not expected:
            # No expected tools -- if agent called none, perfect; otherwise penalize
            if not actual:
                return MetricResult(name="tool_call_accuracy", value=1.0)
            return MetricResult(
                name="tool_call_accuracy",
                value=max(0.0, 1.0 - 0.25 * len(actual)),
                details={"unexpected_calls": len(actual)},
            )

        score = 0.0
        matched_indices: set[int] = set()
        match_details: list[dict[str, Any]] = []

        for exp in expected:
            best_match_idx = -1
            best_match_score = 0.0

            for i, act in enumerate(actual):
                if i in matched_indices:
                    continue
                if act.name == exp.name:
                    # Name match: 0.5 points
                    case_score = 0.5
                    # Check arguments
                    arg_match = all(
                        act.arguments.get(k) == v
                        for k, v in exp.arguments.items()
                    )
                    if arg_match:
                        case_score += 0.5

                    if case_score > best_match_score:
                        best_match_score = case_score
                        best_match_idx = i

            if best_match_idx >= 0:
                matched_indices.add(best_match_idx)
                score += best_match_score
                match_details.append({
                    "expected": exp.name,
                    "matched": True,
                    "score": best_match_score,
                })
            else:
                match_details.append({
                    "expected": exp.name,
                    "matched": False,
                    "score": 0.0,
                })

        # Penalty for unexpected tool calls
        extra_calls = len(actual) - len(matched_indices)
        penalty = 0.25 * extra_calls

        final = max(0.0, min(1.0, (score / len(expected)) - penalty))

        return MetricResult(
            name="tool_call_accuracy",
            value=round(final, 4),
            details={
                "matches": match_details,
                "extra_calls": extra_calls,
                "raw_score": score,
                "max_score": float(len(expected)),
            },
        )

    @staticmethod
    def _hallucination_rate(
        response: str,
        reference_context: list[str],
    ) -> MetricResult:
        """Estimate hallucination rate using simple sentence-level NLI heuristic.

        Algorithm:
        1. Split response into sentences
        2. Split each reference document into sentences
        3. For each response sentence containing a factual claim (has numbers,
           proper nouns, or specific assertions), check if any reference
           sentence has high token overlap (Jaccard similarity > threshold)
        4. Ungrounded claims / total claims = hallucination rate

        This is a HEURISTIC -- not a trained NLI model. It catches obvious
        hallucinations (agent invents a statistic not in context) but misses
        subtle paraphrases. For production, pair this with the LLM judge's
        groundedness dimension.
        """
        # Split into sentences (simple heuristic)
        response_sentences = [
            s.strip() for s in re.split(r'[.!?]+', response)
            if len(s.strip()) > 10
        ]

        if not response_sentences:
            return MetricResult(name="hallucination_rate", value=0.0)

        # Build reference sentence set
        ref_sentences: list[set[str]] = []
        for doc in reference_context:
            for s in re.split(r'[.!?]+', doc):
                s = s.strip()
                if len(s) > 5:
                    tokens = set(s.lower().split())
                    ref_sentences.append(tokens)

        # Check each response sentence for grounding
        claim_count = 0
        ungrounded_count = 0

        for sent in response_sentences:
            # Filter to sentences that look like factual claims
            has_number = bool(re.search(r'\d', sent))
            has_quote = '"' in sent or "'" in sent
            has_specific = has_number or has_quote or len(sent.split()) > 8

            if not has_specific:
                continue

            claim_count += 1
            sent_tokens = set(sent.lower().split())

            # Check Jaccard similarity against all reference sentences
            max_similarity = 0.0
            for ref_tokens in ref_sentences:
                if not ref_tokens or not sent_tokens:
                    continue
                intersection = len(sent_tokens & ref_tokens)
                union = len(sent_tokens | ref_tokens)
                similarity = intersection / union if union > 0 else 0.0
                max_similarity = max(max_similarity, similarity)

            if max_similarity < 0.3:  # Threshold for "grounded"
                ungrounded_count += 1

        rate = ungrounded_count / claim_count if claim_count > 0 else 0.0

        return MetricResult(
            name="hallucination_rate",
            value=round(rate, 4),
            details={
                "total_claims": claim_count,
                "ungrounded_claims": ungrounded_count,
                "total_sentences": len(response_sentences),
            },
        )
```

---

### Step 4: Statistical Significance Testing

This is the Staff-level differentiator. Do not just compare averages -- compute confidence intervals and effect sizes. You change a prompt and correctness goes from 0.82 to 0.85. Is that a real improvement or noise? With 50 test cases, a 3-point difference is often NOT significant (p > 0.05). Without statistical testing, you ship noise and call it progress.

```python
"""eval_framework/statistics.py -- Statistical significance and regression detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy import stats as scipy_stats


@dataclass
class ComparisonResult:
    """Result of comparing two evaluation runs."""
    dimension: str
    baseline_mean: float
    candidate_mean: float
    mean_diff: float
    ci_lower: float          # Lower bound of confidence interval for the diff
    ci_upper: float          # Upper bound of confidence interval for the diff
    is_significant: bool     # CI does not contain 0
    effect_size: float       # Cohen's d
    effect_magnitude: str    # "negligible", "small", "medium", "large"
    p_value: float           # From permutation test
    n_baseline: int
    n_candidate: int


@dataclass
class RegressionReport:
    """Full regression analysis across all dimensions."""
    comparisons: dict[str, ComparisonResult]
    has_regression: bool
    regression_dimensions: list[str]
    summary: str


class StatisticalAnalyzer:
    """Determines whether score differences are statistically significant.

    Why this matters: you change a prompt and correctness goes from 0.82 to 0.85.
    Is that a real improvement or noise? With 50 test cases, a 3-point difference
    is often NOT significant (p > 0.05). Without statistical testing, you ship
    noise and call it progress.

    Uses bootstrap confidence intervals (not t-tests) because:
    1. LLM scores are not normally distributed (they cluster at extremes)
    2. Bootstrap makes no distributional assumptions
    3. Bootstrap gives confidence intervals, not just p-values

    Also computes Cohen's d for effect size because:
    - Statistical significance depends on sample size. With 10,000 cases,
      a 0.001 difference is "significant." But it is meaningless.
    - Effect size measures the MAGNITUDE of the difference, independent of
      sample size. A small effect size means "real but not worth caring about."
    """

    def __init__(
        self,
        confidence_level: float = 0.95,
        n_bootstrap: int = 10_000,
        regression_threshold: float = 0.02,
        random_seed: int = 42,
    ) -> None:
        self._confidence_level = confidence_level
        self._n_bootstrap = n_bootstrap
        self._regression_threshold = regression_threshold
        self._rng = np.random.default_rng(random_seed)

    def compare_runs(
        self,
        baseline_scores: list[float],
        candidate_scores: list[float],
        dimension: str = "unknown",
    ) -> ComparisonResult:
        """Bootstrap comparison of two score distributions.

        Algorithm:
        1. Compute observed mean difference (candidate - baseline)
        2. Bootstrap: resample both distributions N times, compute mean diff each time
        3. The 2.5th and 97.5th percentiles of bootstrapped diffs = 95% CI
        4. If the CI does not contain 0, the difference is significant
        5. Compute Cohen's d for effect size

        Returns: ComparisonResult with mean_diff, CI, significance, and effect size
        """
        baseline = np.array(baseline_scores, dtype=np.float64)
        candidate = np.array(candidate_scores, dtype=np.float64)

        observed_diff = float(np.mean(candidate) - np.mean(baseline))

        # Bootstrap confidence interval for the mean difference
        bootstrap_diffs = np.empty(self._n_bootstrap)

        for i in range(self._n_bootstrap):
            boot_baseline = self._rng.choice(
                baseline, size=len(baseline), replace=True
            )
            boot_candidate = self._rng.choice(
                candidate, size=len(candidate), replace=True
            )
            bootstrap_diffs[i] = np.mean(boot_candidate) - np.mean(boot_baseline)

        alpha = 1.0 - self._confidence_level
        ci_lower = float(np.percentile(bootstrap_diffs, 100 * alpha / 2))
        ci_upper = float(np.percentile(bootstrap_diffs, 100 * (1 - alpha / 2)))

        # Significance: CI does not contain 0
        is_significant = not (ci_lower <= 0 <= ci_upper)

        # Effect size: Cohen's d
        effect_size = self._cohens_d(baseline, candidate)
        effect_magnitude = self._effect_magnitude(effect_size)

        # Permutation test p-value for additional rigor
        p_value = self._permutation_test(baseline, candidate)

        return ComparisonResult(
            dimension=dimension,
            baseline_mean=round(float(np.mean(baseline)), 4),
            candidate_mean=round(float(np.mean(candidate)), 4),
            mean_diff=round(observed_diff, 4),
            ci_lower=round(ci_lower, 4),
            ci_upper=round(ci_upper, 4),
            is_significant=is_significant,
            effect_size=round(effect_size, 4),
            effect_magnitude=effect_magnitude,
            p_value=round(p_value, 4),
            n_baseline=len(baseline),
            n_candidate=len(candidate),
        )

    def detect_regression(
        self,
        baseline_scores: dict[str, list[float]],
        candidate_scores: dict[str, list[float]],
        threshold: Optional[float] = None,
    ) -> RegressionReport:
        """Detect regressions across multiple dimensions.

        A regression is: statistically significant AND effect size > threshold.

        Why both conditions:
        - Significant but tiny (0.001 drop): not worth blocking a deploy
        - Large but not significant: noise, not a real regression
        - Significant AND large: real regression, block the deploy
        """
        threshold = threshold or self._regression_threshold
        comparisons: dict[str, ComparisonResult] = {}
        regression_dims: list[str] = []

        for dim in baseline_scores:
            if dim not in candidate_scores:
                continue

            result = self.compare_runs(
                baseline_scores[dim],
                candidate_scores[dim],
                dimension=dim,
            )
            comparisons[dim] = result

            # Regression = significant drop that exceeds threshold
            is_drop = result.mean_diff < 0
            exceeds_threshold = abs(result.mean_diff) > threshold
            if result.is_significant and is_drop and exceeds_threshold:
                regression_dims.append(dim)

        has_regression = len(regression_dims) > 0

        # Build summary
        if has_regression:
            dim_details = ", ".join(
                f"{d} ({comparisons[d].mean_diff:+.4f})"
                for d in regression_dims
            )
            summary = (
                f"REGRESSION DETECTED in {len(regression_dims)} dimension(s): "
                f"{dim_details}. "
                f"All regressions are statistically significant (p < "
                f"{1 - self._confidence_level:.2f}) with effect size > "
                f"{threshold}."
            )
        else:
            summary = (
                f"No regressions detected across {len(comparisons)} dimensions. "
                f"Threshold: {threshold}, confidence: {self._confidence_level}."
            )

        return RegressionReport(
            comparisons=comparisons,
            has_regression=has_regression,
            regression_dimensions=regression_dims,
            summary=summary,
        )

    @staticmethod
    def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
        """Compute Cohen's d effect size.

        Cohen's d = (mean2 - mean1) / pooled_std

        Interpretation:
        - |d| < 0.2: negligible
        - 0.2 <= |d| < 0.5: small
        - 0.5 <= |d| < 0.8: medium
        - |d| >= 0.8: large

        Uses pooled standard deviation with Bessel's correction.
        """
        n1, n2 = len(group1), len(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

        # Pooled standard deviation
        pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
        pooled_std = np.sqrt(pooled_var)

        if pooled_std == 0:
            return 0.0

        return float((np.mean(group2) - np.mean(group1)) / pooled_std)

    @staticmethod
    def _effect_magnitude(d: float) -> str:
        """Classify effect size magnitude using Cohen's conventions."""
        abs_d = abs(d)
        if abs_d < 0.2:
            return "negligible"
        elif abs_d < 0.5:
            return "small"
        elif abs_d < 0.8:
            return "medium"
        else:
            return "large"

    def _permutation_test(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        n_permutations: int = 5000,
    ) -> float:
        """Two-sided permutation test for difference in means.

        Under the null hypothesis (no difference), the group labels are
        exchangeable. We shuffle labels N times and count how often the
        permuted difference exceeds the observed difference.
        """
        observed_diff = abs(np.mean(group2) - np.mean(group1))
        combined = np.concatenate([group1, group2])
        n1 = len(group1)

        count_extreme = 0
        for _ in range(n_permutations):
            self._rng.shuffle(combined)
            perm_diff = abs(np.mean(combined[:n1]) - np.mean(combined[n1:]))
            if perm_diff >= observed_diff:
                count_extreme += 1

        return (count_extreme + 1) / (n_permutations + 1)
```

:::info Why Not Just Use t-tests?
The t-test assumes normally distributed data. LLM-judge scores cluster bimodally -- many 1s and 5s, few 3s. On bimodal data, t-tests produce unreliable p-values. The bootstrap makes zero distributional assumptions: it resamples your actual data and builds the confidence interval empirically. Permutation tests are similarly assumption-free and serve as a secondary check.
:::

---

### Step 5: Evaluation Runner

The runner orchestrates the full evaluation: loading the dataset, calling the agent under test, scoring with judges and deterministic metrics, and running statistical comparison against a baseline. Parallelization strategy: eval cases run in parallel (asyncio.gather with semaphore for concurrency control), but judge evaluations run sequentially per case (the judge needs the full case context). At 50 cases with concurrency of 10, a full eval run takes approximately 2 minutes instead of 10.

```python
"""eval_framework/runner.py -- Evaluation orchestrator."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable, Optional

from eval_framework.dataset import DatasetVersion, EvalCase
from eval_framework.judge import JudgeResult, LLMJudge
from eval_framework.metrics import (
    AgentOutput,
    DeterministicMetricReport,
    DeterministicMetrics,
    MetricResult,
)
from eval_framework.statistics import RegressionReport, StatisticalAnalyzer


# Type alias for the agent callable
AgentCallable = Callable[[str], Awaitable[AgentOutput]]


@dataclass
class CaseResult:
    """Complete evaluation result for a single case."""
    case_id: str
    input: str
    agent_output: AgentOutput
    judge_result: Optional[JudgeResult]
    metric_report: DeterministicMetricReport
    error: Optional[str] = None


@dataclass
class EvalRun:
    """Complete evaluation run result."""
    run_id: str
    dataset_name: str
    dataset_version: str
    dataset_hash: str
    started_at: str
    completed_at: str
    case_results: list[CaseResult]
    aggregate_metrics: dict[str, MetricResult]
    dimension_scores: dict[str, list[float]]  # dim -> per-case scores
    regression_report: Optional[RegressionReport] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EvaluationRunner:
    """Runs an agent against a dataset and produces a scored report.

    Parallelization strategy: run eval cases in parallel (asyncio.gather with
    semaphore for concurrency control), but run judge evaluations sequentially
    per case (the judge needs the full case context). At 50 cases with
    concurrency=10, a full eval run takes ~2 minutes instead of ~10.
    """

    def __init__(
        self,
        judge: LLMJudge,
        metrics: DeterministicMetrics,
        analyzer: StatisticalAnalyzer,
        concurrency: int = 10,
        run_judge: bool = True,
        results_dir: str | Path = "eval_results",
    ) -> None:
        self._judge = judge
        self._metrics = metrics
        self._analyzer = analyzer
        self._concurrency = concurrency
        self._run_judge = run_judge
        self._results_dir = Path(results_dir)
        self._results_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        agent: AgentCallable,
        dataset: DatasetVersion,
        baseline_run_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> EvalRun:
        """Execute a full evaluation run.

        Steps:
        1. Generate a run ID
        2. Run agent against all cases in parallel (bounded concurrency)
        3. Score each result with deterministic metrics
        4. Optionally score with LLM judge
        5. Aggregate metrics
        6. If baseline provided, run regression detection
        7. Save results and return
        """
        run_id = self._generate_run_id(dataset)
        started_at = datetime.now(timezone.utc).isoformat()

        # Calibrate judge if we are running judge evaluations
        if self._run_judge:
            await self._judge.calibrate()

        # Run agent against all cases with bounded concurrency
        semaphore = asyncio.Semaphore(self._concurrency)
        case_results = await asyncio.gather(
            *(
                self._evaluate_case(agent, case, semaphore)
                for case in dataset.cases
            )
        )

        # Aggregate deterministic metrics
        metric_reports = [r.metric_report for r in case_results]
        aggregate_metrics = self._metrics.compute_aggregate_metrics(metric_reports)

        # Collect per-dimension scores for statistical analysis
        dimension_scores: dict[str, list[float]] = {}
        for result in case_results:
            if result.judge_result:
                for dim, score in result.judge_result.dimension_scores.items():
                    if dim not in dimension_scores:
                        dimension_scores[dim] = []
                    dimension_scores[dim].append(score.calibrated_score)

        completed_at = datetime.now(timezone.utc).isoformat()

        eval_run = EvalRun(
            run_id=run_id,
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            dataset_hash=dataset.content_hash,
            started_at=started_at,
            completed_at=completed_at,
            case_results=case_results,
            aggregate_metrics=aggregate_metrics,
            dimension_scores=dimension_scores,
            metadata=metadata or {},
        )

        # Run regression detection if baseline provided
        if baseline_run_id:
            baseline_run = self._load_run(baseline_run_id)
            if baseline_run and baseline_run.dimension_scores:
                eval_run.regression_report = self._analyzer.detect_regression(
                    baseline_scores=baseline_run.dimension_scores,
                    candidate_scores=dimension_scores,
                )

        # Persist results
        self._save_run(eval_run)

        return eval_run

    async def _evaluate_case(
        self,
        agent: AgentCallable,
        case: EvalCase,
        semaphore: asyncio.Semaphore,
    ) -> CaseResult:
        """Evaluate a single case: call agent, compute metrics, run judge."""
        async with semaphore:
            try:
                # Call the agent under test
                agent_output = await agent(case.input)

                # Compute deterministic metrics
                metric_report = self._metrics.compute_case_metrics(
                    case_id=case.case_id,
                    agent_output=agent_output,
                    reference_context=case.reference_context,
                )

                # Run LLM judge if enabled
                judge_result = None
                if self._run_judge:
                    judge_result = await self._judge.evaluate(
                        case_id=case.case_id,
                        user_input=case.input,
                        agent_response=agent_output.response,
                        expected_output=case.expected_output,
                        reference_context=case.reference_context,
                    )

                return CaseResult(
                    case_id=case.case_id,
                    input=case.input,
                    agent_output=agent_output,
                    judge_result=judge_result,
                    metric_report=metric_report,
                )

            except Exception as exc:
                # Never let a single case failure kill the entire run
                return CaseResult(
                    case_id=case.case_id,
                    input=case.input,
                    agent_output=AgentOutput(response=""),
                    judge_result=None,
                    metric_report=DeterministicMetricReport(case_id=case.case_id),
                    error=str(exc),
                )

    def _save_run(self, run: EvalRun) -> Path:
        """Persist an evaluation run to disk as JSON."""
        run_path = self._results_dir / f"{run.run_id}.json"
        serializable = {
            "run_id": run.run_id,
            "dataset_name": run.dataset_name,
            "dataset_version": run.dataset_version,
            "dataset_hash": run.dataset_hash,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "aggregate_metrics": {
                k: {"name": v.name, "value": v.value, "details": v.details}
                for k, v in run.aggregate_metrics.items()
            },
            "dimension_scores": run.dimension_scores,
            "case_count": len(run.case_results),
            "error_count": sum(1 for r in run.case_results if r.error),
            "metadata": run.metadata,
        }
        if run.regression_report:
            serializable["regression"] = {
                "has_regression": run.regression_report.has_regression,
                "regression_dimensions": run.regression_report.regression_dimensions,
                "summary": run.regression_report.summary,
            }

        with open(run_path, "w") as f:
            json.dump(serializable, f, indent=2)
        return run_path

    def _load_run(self, run_id: str) -> Optional[EvalRun]:
        """Load a previous run's dimension scores for comparison."""
        run_path = self._results_dir / f"{run_id}.json"
        if not run_path.exists():
            return None

        with open(run_path) as f:
            data = json.load(f)

        # Reconstruct a minimal EvalRun with dimension scores
        return EvalRun(
            run_id=data["run_id"],
            dataset_name=data["dataset_name"],
            dataset_version=data["dataset_version"],
            dataset_hash=data.get("dataset_hash", ""),
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            case_results=[],
            aggregate_metrics={},
            dimension_scores=data.get("dimension_scores", {}),
        )

    @staticmethod
    def _generate_run_id(dataset: DatasetVersion) -> str:
        """Generate a deterministic-ish run ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        content = f"{dataset.name}-{dataset.version}-{timestamp}"
        short_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"run-{timestamp}-{short_hash}"
```

---

### Step 6: Regression Detection and CI/CD Gate

The automated gate that blocks deploys when quality regresses. This is where statistical rigor meets deploy pipelines. The gate checks multiple conditions independently because different failure modes have different tolerances: you might accept a small correctness dip but never accept a safety regression.

```python
"""eval_framework/gate.py -- CI/CD quality gate."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Optional

from eval_framework.runner import EvalRun
from eval_framework.statistics import StatisticalAnalyzer


class ExitCode(IntEnum):
    """CI exit codes.

    0 = pass: deploy is safe
    1 = regression: deploy is blocked
    2 = infrastructure error: manual review needed
    """
    PASS = 0
    REGRESSION = 1
    INFRA_ERROR = 2


@dataclass
class GateCheck:
    """Result of a single gate check."""
    name: str
    passed: bool
    message: str
    severity: str = "error"  # "error" blocks, "warning" does not


@dataclass
class GateResult:
    """Aggregated gate result."""
    exit_code: ExitCode
    checks: list[GateCheck]
    summary: str
    blocked_by: list[str] = field(default_factory=list)


class CIGate:
    """CI/CD integration that blocks merges on detected regressions.

    The gate checks:
    1. No dimension regresses significantly (statistical test)
    2. Cost per request stays within budget (+20% tolerance)
    3. P95 latency stays within SLA
    4. Safety score never drops (zero tolerance for safety regression)
    5. Tool call accuracy stays above minimum threshold

    Exit codes: 0 = pass, 1 = regression detected, 2 = eval infrastructure error

    Design philosophy: the gate is deliberately conservative. It is better to
    block a good deploy than to ship a bad one. False positives cost engineer
    time (re-review the change). False negatives cost user trust (shipped a bug).
    """

    def __init__(
        self,
        max_cost_increase_pct: float = 20.0,
        max_latency_p95_ms: float = 5000.0,
        min_tool_accuracy: float = 0.85,
        safety_regression_tolerance: float = 0.0,
        min_cases_for_significance: int = 20,
    ) -> None:
        self._max_cost_increase_pct = max_cost_increase_pct
        self._max_latency_p95_ms = max_latency_p95_ms
        self._min_tool_accuracy = min_tool_accuracy
        self._safety_tolerance = safety_regression_tolerance
        self._min_cases = min_cases_for_significance

    def evaluate(
        self,
        candidate_run: EvalRun,
        baseline_run: Optional[EvalRun] = None,
    ) -> GateResult:
        """Run all gate checks and return the aggregate result."""
        checks: list[GateCheck] = []

        # Check 0: Sufficient data
        n_cases = len(candidate_run.case_results)
        n_errors = sum(1 for r in candidate_run.case_results if r.error)
        error_rate = n_errors / n_cases if n_cases > 0 else 1.0

        if error_rate > 0.1:
            return GateResult(
                exit_code=ExitCode.INFRA_ERROR,
                checks=[GateCheck(
                    name="error_rate",
                    passed=False,
                    message=(
                        f"{n_errors}/{n_cases} cases errored ({error_rate:.0%}). "
                        f"This suggests an infrastructure problem, not an agent problem."
                    ),
                    severity="error",
                )],
                summary="Evaluation infrastructure error: too many case failures.",
                blocked_by=["error_rate"],
            )

        # Check 1: Statistical regression in quality dimensions
        if candidate_run.regression_report:
            reg = candidate_run.regression_report
            if reg.has_regression:
                checks.append(GateCheck(
                    name="dimension_regression",
                    passed=False,
                    message=reg.summary,
                    severity="error",
                ))
            else:
                checks.append(GateCheck(
                    name="dimension_regression",
                    passed=True,
                    message=reg.summary,
                ))

        # Check 2: Safety score (zero tolerance)
        safety_scores = candidate_run.dimension_scores.get("safety", [])
        if safety_scores and baseline_run and baseline_run.dimension_scores:
            baseline_safety = baseline_run.dimension_scores.get("safety", [])
            if baseline_safety:
                import numpy as np
                safety_diff = float(
                    np.mean(safety_scores) - np.mean(baseline_safety)
                )
                if safety_diff < -self._safety_tolerance:
                    checks.append(GateCheck(
                        name="safety_regression",
                        passed=False,
                        message=(
                            f"Safety score dropped by {abs(safety_diff):.4f}. "
                            f"Zero tolerance policy: any safety regression blocks deploy."
                        ),
                        severity="error",
                    ))
                else:
                    checks.append(GateCheck(
                        name="safety_regression",
                        passed=True,
                        message=f"Safety score change: {safety_diff:+.4f}",
                    ))

        # Check 3: Cost budget
        if baseline_run:
            candidate_cost = candidate_run.aggregate_metrics.get("mean_cost_usd")
            baseline_cost = baseline_run.aggregate_metrics.get("mean_cost_usd")
            if candidate_cost and baseline_cost:
                cost_increase_pct = (
                    (candidate_cost.value - baseline_cost.value)
                    / baseline_cost.value * 100
                    if baseline_cost.value > 0 else 0
                )
                passed = cost_increase_pct <= self._max_cost_increase_pct
                checks.append(GateCheck(
                    name="cost_budget",
                    passed=passed,
                    message=(
                        f"Cost change: {cost_increase_pct:+.1f}% "
                        f"(limit: +{self._max_cost_increase_pct}%)"
                    ),
                    severity="error" if not passed else "info",
                ))

        # Check 4: Latency SLA
        latency_p95 = candidate_run.aggregate_metrics.get("latency_p95")
        if latency_p95:
            passed = latency_p95.value <= self._max_latency_p95_ms
            checks.append(GateCheck(
                name="latency_sla",
                passed=passed,
                message=(
                    f"P95 latency: {latency_p95.value:.0f}ms "
                    f"(limit: {self._max_latency_p95_ms:.0f}ms)"
                ),
                severity="error" if not passed else "info",
            ))

        # Check 5: Tool call accuracy minimum
        tool_acc = candidate_run.aggregate_metrics.get("tool_call_accuracy_mean")
        if tool_acc:
            passed = tool_acc.value >= self._min_tool_accuracy
            checks.append(GateCheck(
                name="tool_accuracy",
                passed=passed,
                message=(
                    f"Tool call accuracy: {tool_acc.value:.2%} "
                    f"(minimum: {self._min_tool_accuracy:.2%})"
                ),
                severity="error" if not passed else "info",
            ))

        # Determine final result
        blocking_checks = [c for c in checks if not c.passed and c.severity == "error"]
        blocked_by = [c.name for c in blocking_checks]

        if blocking_checks:
            exit_code = ExitCode.REGRESSION
            summary = (
                f"DEPLOY BLOCKED: {len(blocking_checks)} gate check(s) failed: "
                + ", ".join(blocked_by)
            )
        else:
            exit_code = ExitCode.PASS
            summary = f"All {len(checks)} gate checks passed. Deploy is safe."

        return GateResult(
            exit_code=exit_code,
            checks=checks,
            summary=summary,
            blocked_by=blocked_by,
        )
```

---

### Step 7: Report Generator

Generate a markdown report with dimension-by-dimension comparison, confidence intervals, regression flags, worst-performing cases for debugging, and cost summary. This report gets attached to the CI pipeline as an artifact and linked in the PR comment.

```python
"""eval_framework/report.py -- Markdown report generator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from eval_framework.gate import GateResult
from eval_framework.runner import EvalRun
from eval_framework.statistics import ComparisonResult


class ReportGenerator:
    """Generate a markdown evaluation report.

    The report is designed to be:
    1. Scannable: the TL;DR is at the top (pass/fail, which dimensions changed)
    2. Debuggable: worst-performing cases are listed with their judge rationales
    3. Archivable: includes all numbers needed to reproduce the analysis
    """

    def generate(
        self,
        run: EvalRun,
        gate_result: Optional[GateResult] = None,
    ) -> str:
        """Generate the full markdown report."""
        sections: list[str] = []

        # Header
        sections.append(f"# Evaluation Report: {run.run_id}\n")
        sections.append(f"**Dataset:** {run.dataset_name} v{run.dataset_version}")
        sections.append(f"**Content hash:** `{run.dataset_hash}`")
        sections.append(f"**Started:** {run.started_at}")
        sections.append(f"**Completed:** {run.completed_at}")
        sections.append(
            f"**Cases:** {len(run.case_results)} "
            f"({sum(1 for r in run.case_results if r.error)} errors)\n"
        )

        # Gate result (TL;DR)
        if gate_result:
            status = "PASS" if gate_result.exit_code == 0 else "FAIL"
            sections.append(f"## Gate Result: {status}\n")
            sections.append(f"{gate_result.summary}\n")
            sections.append("| Check | Status | Details |")
            sections.append("|-------|--------|---------|")
            for check in gate_result.checks:
                icon = "Pass" if check.passed else "FAIL"
                sections.append(f"| {check.name} | {icon} | {check.message} |")
            sections.append("")

        # Dimension scores
        if run.dimension_scores:
            sections.append("## Quality Dimensions\n")
            sections.append("| Dimension | Mean Score | Std Dev | N Cases |")
            sections.append("|-----------|-----------|---------|---------|")
            for dim, scores in sorted(run.dimension_scores.items()):
                import numpy as np
                arr = np.array(scores)
                sections.append(
                    f"| {dim} | {np.mean(arr):.4f} | {np.std(arr):.4f} | {len(arr)} |"
                )
            sections.append("")

        # Regression analysis
        if run.regression_report:
            sections.append("## Regression Analysis\n")
            sections.append(run.regression_report.summary + "\n")
            sections.append(
                "| Dimension | Baseline | Candidate | Diff | "
                "CI (95%) | Significant | Effect Size |"
            )
            sections.append(
                "|-----------|----------|-----------|------|"
                "----------|-------------|-------------|"
            )
            for dim, comp in sorted(run.regression_report.comparisons.items()):
                sig = "Yes" if comp.is_significant else "No"
                sections.append(
                    f"| {dim} | {comp.baseline_mean:.4f} | "
                    f"{comp.candidate_mean:.4f} | {comp.mean_diff:+.4f} | "
                    f"[{comp.ci_lower:+.4f}, {comp.ci_upper:+.4f}] | "
                    f"{sig} | {comp.effect_size:+.4f} ({comp.effect_magnitude}) |"
                )
            sections.append("")

        # Aggregate metrics
        if run.aggregate_metrics:
            sections.append("## Operational Metrics\n")
            sections.append("| Metric | Value |")
            sections.append("|--------|-------|")
            for name, metric in sorted(run.aggregate_metrics.items()):
                if "cost" in name:
                    sections.append(f"| {name} | ${metric.value:.4f} |")
                elif "latency" in name:
                    sections.append(f"| {name} | {metric.value:.0f}ms |")
                else:
                    sections.append(f"| {name} | {metric.value:.4f} |")
            sections.append("")

        # Worst performing cases (for debugging)
        sections.append("## Worst Performing Cases\n")
        scored_cases = [
            r for r in run.case_results
            if r.judge_result and not r.error
        ]
        scored_cases.sort(key=lambda r: r.judge_result.aggregate_score)

        for case in scored_cases[:5]:
            jr = case.judge_result
            sections.append(
                f"### Case `{case.case_id}` "
                f"(aggregate: {jr.aggregate_score:.4f})\n"
            )
            sections.append(f"**Input:** {case.input[:200]}\n")
            sections.append(
                f"**Response:** {case.agent_output.response[:200]}...\n"
            )
            for dim, score in jr.dimension_scores.items():
                sections.append(
                    f"- **{dim}:** {score.calibrated_score:.2f} -- "
                    f"{score.rationale}"
                )
            sections.append("")

        # Error cases
        error_cases = [r for r in run.case_results if r.error]
        if error_cases:
            sections.append("## Error Cases\n")
            for case in error_cases[:10]:
                sections.append(f"- `{case.case_id}`: {case.error}")
            sections.append("")

        return "\n".join(sections)
```

---

### Step 8: CLI Interface

The CLI provides three commands: `run` executes a full evaluation, `compare` compares two existing runs without re-executing, and `gate` runs the CI gate check against a candidate/baseline pair and exits with the appropriate code.

```python
"""eval_framework/__main__.py -- CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from eval_framework.dataset import DatasetManager
from eval_framework.gate import CIGate, ExitCode
from eval_framework.judge import LLMJudge
from eval_framework.metrics import AgentOutput, DeterministicMetrics
from eval_framework.report import ReportGenerator
from eval_framework.runner import EvalRun, EvaluationRunner
from eval_framework.statistics import StatisticalAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eval_framework",
        description="Agent Evaluation & Testing Framework",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Run evaluation")
    run_parser.add_argument(
        "--agent", required=True, help="Agent module path (e.g., myagent.run)"
    )
    run_parser.add_argument("--dataset", required=True, help="Dataset name")
    run_parser.add_argument(
        "--version", required=True, help="Dataset version"
    )
    run_parser.add_argument(
        "--baseline", default=None, help="Baseline run ID for comparison"
    )
    run_parser.add_argument(
        "--concurrency", type=int, default=10, help="Max parallel evaluations"
    )
    run_parser.add_argument(
        "--skip-judge", action="store_true",
        help="Skip LLM judge (deterministic metrics only)",
    )
    run_parser.add_argument(
        "--output", default=None, help="Output report path (.md)"
    )

    # --- compare ---
    cmp_parser = subparsers.add_parser(
        "compare", help="Compare two existing runs"
    )
    cmp_parser.add_argument("--baseline", required=True, help="Baseline run ID")
    cmp_parser.add_argument(
        "--candidate", required=True, help="Candidate run ID"
    )
    cmp_parser.add_argument(
        "--output", default=None, help="Output report path (.md)"
    )

    # --- gate ---
    gate_parser = subparsers.add_parser(
        "gate", help="CI quality gate check"
    )
    gate_parser.add_argument(
        "--candidate", required=True, help="Candidate run ID"
    )
    gate_parser.add_argument(
        "--baseline", required=True, help="Baseline run ID"
    )
    gate_parser.add_argument(
        "--max-cost-increase", type=float, default=20.0,
        help="Max cost increase percent",
    )
    gate_parser.add_argument(
        "--max-latency-p95", type=float, default=5000.0,
        help="Max P95 latency in ms",
    )
    gate_parser.add_argument(
        "--min-tool-accuracy", type=float, default=0.85,
        help="Minimum tool call accuracy",
    )

    return parser


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a full evaluation run."""
    dataset_mgr = DatasetManager()
    dataset = dataset_mgr.load(args.dataset, args.version)
    print(f"Loaded dataset: {dataset.name} v{dataset.version} ({len(dataset.cases)} cases)")

    judge = LLMJudge()
    metrics = DeterministicMetrics()
    analyzer = StatisticalAnalyzer()
    runner = EvaluationRunner(
        judge=judge,
        metrics=metrics,
        analyzer=analyzer,
        concurrency=args.concurrency,
        run_judge=not args.skip_judge,
    )

    # Load the agent callable (dynamic import)
    agent = _load_agent(args.agent)

    # Run evaluation
    eval_run = asyncio.run(
        runner.run(
            agent=agent,
            dataset=dataset,
            baseline_run_id=args.baseline,
        )
    )

    print(f"Evaluation complete: {eval_run.run_id}")
    print(f"  Cases: {len(eval_run.case_results)}")
    print(f"  Errors: {sum(1 for r in eval_run.case_results if r.error)}")

    # Generate report
    gate = CIGate()
    gate_result = gate.evaluate(eval_run)
    report_gen = ReportGenerator()
    report = report_gen.generate(eval_run, gate_result)

    if args.output:
        Path(args.output).write_text(report)
        print(f"  Report: {args.output}")
    else:
        print(report)

    return gate_result.exit_code


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two existing runs."""
    results_dir = Path("eval_results")
    analyzer = StatisticalAnalyzer()

    baseline_data = _load_run_data(results_dir / f"{args.baseline}.json")
    candidate_data = _load_run_data(results_dir / f"{args.candidate}.json")

    if not baseline_data or not candidate_data:
        print("Error: could not load one or both runs.", file=sys.stderr)
        return ExitCode.INFRA_ERROR

    regression_report = analyzer.detect_regression(
        baseline_scores=baseline_data.get("dimension_scores", {}),
        candidate_scores=candidate_data.get("dimension_scores", {}),
    )

    print(f"Comparing {args.baseline} vs {args.candidate}")
    print(f"\n{regression_report.summary}\n")

    for dim, comp in sorted(regression_report.comparisons.items()):
        sig_marker = " ***" if comp.is_significant else ""
        print(
            f"  {dim:15s}: {comp.baseline_mean:.4f} -> "
            f"{comp.candidate_mean:.4f} ({comp.mean_diff:+.4f}) "
            f"[{comp.ci_lower:+.4f}, {comp.ci_upper:+.4f}] "
            f"d={comp.effect_size:+.4f}{sig_marker}"
        )

    return ExitCode.PASS


def cmd_gate(args: argparse.Namespace) -> int:
    """Run CI quality gate."""
    results_dir = Path("eval_results")

    candidate_data = _load_run_data(results_dir / f"{args.candidate}.json")
    baseline_data = _load_run_data(results_dir / f"{args.baseline}.json")

    if not candidate_data or not baseline_data:
        print("Error: could not load run data.", file=sys.stderr)
        return ExitCode.INFRA_ERROR

    # Reconstruct minimal EvalRun objects for the gate
    from eval_framework.metrics import MetricResult
    from eval_framework.runner import EvalRun

    candidate_run = _data_to_eval_run(candidate_data)
    baseline_run = _data_to_eval_run(baseline_data)

    # Run regression detection
    analyzer = StatisticalAnalyzer()
    regression = analyzer.detect_regression(
        baseline_scores=baseline_data.get("dimension_scores", {}),
        candidate_scores=candidate_data.get("dimension_scores", {}),
    )
    candidate_run.regression_report = regression

    gate = CIGate(
        max_cost_increase_pct=args.max_cost_increase,
        max_latency_p95_ms=args.max_latency_p95,
        min_tool_accuracy=args.min_tool_accuracy,
    )
    result = gate.evaluate(candidate_run, baseline_run)

    print(result.summary)
    for check in result.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"  [{status}] {check.name}: {check.message}")

    return result.exit_code


def _load_agent(module_path: str):
    """Dynamically import an agent callable from a module path.

    Expected: the module exposes an async function `run(input: str) -> AgentOutput`
    """
    import importlib
    module = importlib.import_module(module_path)
    if not hasattr(module, "run"):
        raise AttributeError(
            f"Agent module {module_path} must expose an async `run` function"
        )
    return module.run


def _load_run_data(path: Path) -> dict | None:
    """Load a run JSON file."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _data_to_eval_run(data: dict) -> EvalRun:
    """Convert raw JSON data to a minimal EvalRun for gate checks."""
    from eval_framework.metrics import MetricResult

    aggregate = {}
    for k, v in data.get("aggregate_metrics", {}).items():
        aggregate[k] = MetricResult(
            name=v.get("name", k),
            value=v.get("value", 0),
            details=v.get("details", {}),
        )

    return EvalRun(
        run_id=data["run_id"],
        dataset_name=data["dataset_name"],
        dataset_version=data["dataset_version"],
        dataset_hash=data.get("dataset_hash", ""),
        started_at=data["started_at"],
        completed_at=data["completed_at"],
        case_results=[],
        aggregate_metrics=aggregate,
        dimension_scores=data.get("dimension_scores", {}),
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "run": cmd_run,
        "compare": cmd_compare,
        "gate": cmd_gate,
    }

    exit_code = handlers[args.command](args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

---

## How to Run

```bash
# Run a full evaluation with LLM judge
python -m eval_framework run \
    --agent customer_support.run \
    --dataset customer-support \
    --version 2.1 \
    --baseline run-20260610-143022-a1b2c3d4 \
    --output report.md

# Run fast evaluation (deterministic metrics only, no LLM judge)
python -m eval_framework run \
    --agent customer_support.run \
    --dataset customer-support \
    --version 2.1 \
    --skip-judge

# Compare two existing runs without re-executing the agent
python -m eval_framework compare \
    --baseline run-20260610-143022-a1b2c3d4 \
    --candidate run-20260611-091544-e5f6g7h8

# CI gate check (use in GitHub Actions / GitLab CI)
python -m eval_framework gate \
    --candidate run-20260611-091544-e5f6g7h8 \
    --baseline run-20260610-143022-a1b2c3d4 \
    --max-cost-increase 20 \
    --max-latency-p95 5000

# Example output:
# DEPLOY BLOCKED: 1 gate check(s) failed: dimension_regression
#   [FAIL] dimension_regression: REGRESSION DETECTED in 1 dimension(s):
#          correctness (-0.0412). All regressions are statistically significant
#          (p < 0.05) with effect size > 0.02.
#   [PASS] safety_regression: Safety score change: +0.0021
#   [PASS] cost_budget: Cost change: +8.3% (limit: +20.0%)
#   [PASS] latency_sla: P95 latency: 3200ms (limit: 5000ms)
#   [PASS] tool_accuracy: Tool call accuracy: 91.20% (minimum: 85.00%)

# Example CI integration (GitHub Actions):
# - name: Run evaluation gate
#   run: |
#     python -m eval_framework gate \
#       --candidate ${{ steps.eval.outputs.run_id }} \
#       --baseline ${{ env.BASELINE_RUN_ID }}
#   # Exit code 0 = pass, 1 = blocked, 2 = infra error
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| LLM-as-judge over human eval | Human eval is the gold standard but does not scale to CI. LLM judges run in minutes, not days. Calibration with reference examples mitigates positivity bias. Reserve human eval for quarterly audits. |
| Bootstrap CI over t-tests | LLM scores are bimodal (many 1s and 5s), violating the normality assumption. Bootstrap makes no distributional assumptions and provides confidence intervals, not just p-values. |
| Effect size (Cohen's d) thresholds | Statistical significance depends on sample size. With 10,000 cases, a 0.001 difference is "significant" but meaningless. Effect size measures magnitude independent of sample size. |
| Two-tier metric strategy | Deterministic metrics (tool accuracy, latency, cost) run on every CI build in seconds. LLM-judge metrics run nightly because they cost dollars per run. Fast feedback for obvious regressions, thorough feedback for subtle ones. |
| Per-dimension regression over aggregate | An aggregate score that goes from 4.1 to 4.1 can hide correctness dropping from 4.5 to 3.8 while helpfulness rises from 3.7 to 4.4. Per-dimension regression catches compensating changes. |
| Zero tolerance for safety | Unlike correctness or helpfulness, safety regressions have asymmetric risk. A slightly less helpful agent is annoying. A slightly less safe agent is a liability. The gate blocks on any safety drop. |
| Dataset versioning with content hash | If test cases change and scores improve, is the agent better or the test easier? The content hash makes this detectable. Comparing runs with different hashes triggers a warning. |
| Cache judge results by input+output hash | Same input and same output always produces the same score from a temperature-0 judge. Caching saves judge API costs when re-evaluating partially changed datasets. |

---

## Scaling Considerations

**Parallel eval execution with semaphore:**
The `asyncio.Semaphore` bounds concurrent agent calls. Without it, 200 concurrent LLM API calls would trigger rate limits. The semaphore defaults to 10 -- enough to saturate a typical rate limit without exceeding it. Adjust based on your provider's limits.

**Caching judge results:**
The judge cache keys on `sha256(case_id + response + dimension)`. If the agent produces the same output for the same input, the judge score is reused. This matters during iterative development: you change a prompt, 80% of outputs are identical, only 20% need re-judging. Cost drops from $5 per run to $1.

**Incremental evaluation:**
When a dataset has 500 cases but only 20 changed between versions, you do not need to re-evaluate all 500. The content hash on `DatasetVersion` enables a diff: load both versions, identify changed cases by `case_id`, evaluate only those. Unchanged cases carry forward their previous scores. Implementation is straightforward -- diff case IDs, run only the delta, merge with cached results.

**Result storage for historical analysis:**
Each run is persisted as a JSON file keyed by `run_id`. For teams running 10+ evaluations per day, migrate to a database (SQLite for small teams, PostgreSQL for larger). The JSON schema is designed to be directly insertable into a `runs` table with a JSONB `dimension_scores` column.

**Multi-agent evaluation:**
The `AgentCallable` type alias (`async (str) -> AgentOutput`) abstracts away the agent implementation. To evaluate a LangGraph agent, a CrewAI agent, or a raw API wrapper, you only need to wrap each in a function matching this signature. The framework does not care what is inside the agent.

---

## Interview Key Takeaways

**What this demonstrates at Staff/Principal level:**

1. **Building infrastructure that enables safe iteration.** This is not a feature -- it is the system that makes all other features safe to ship. Staff engineers identify these leverage points and build them before the team learns the hard way.

2. **Statistical rigor in evaluation.** Comparing averages is a junior mistake. Confidence intervals, effect sizes, and permutation tests are the minimum bar for claiming "this change improved the agent." Interviewers at Staff level expect you to know why averages lie.

3. **Understanding that averages hide regressions.** An aggregate score of 4.1 can mask correctness dropping from 4.5 to 3.8 while helpfulness rises from 3.7 to 4.4. Per-dimension analysis with statistical testing catches compensating changes that aggregates miss.

4. **Two-tier evaluation strategy.** Deterministic metrics on every commit (fast, cheap, catches obvious breaks). LLM-judge metrics nightly (slow, expensive, catches subtle quality shifts). This is a cost-aware design, not just a technically correct one.

5. **CI/CD integration as a first-class concern.** The exit code contract (0/1/2), the gate check design, the conservative blocking policy -- these show you have shipped systems where the deploy pipeline matters as much as the code.

6. **Calibration and bias mitigation.** Knowing that LLM judges have positivity bias and designing calibration anchors to correct for it shows deep understanding of the tool's failure modes, not just its happy path.
