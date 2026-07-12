---
sidebar_position: 2
title: "AI Agent that Modifies CAD Models"
description: "System design for an AI agent that understands and modifies CAD models via natural language with constraint solving and validation"
---

# AI Agent that Modifies CAD Models

An AI agent that parses CAD files (DXF, STEP, IFC), builds geometric and semantic understanding, translates natural language instructions into precise parametric operations, validates changes against structural and manufacturing constraints, and supports multi-turn dialog with undo/redo. This system bridges the gap between natural language understanding and exact geometric operations -- a domain where approximate answers are not acceptable.

---

## Problem Statement
> "Design an AI agent that can read CAD models in standard formats, understand their geometry and constraints, and modify them based on natural language instructions like 'move the kitchen wall 1.5 meters north.' The system must guarantee sub-millimeter precision, respect all existing constraints, and support undo/redo for every operation."

---

## Clarifying Questions to Ask

1. **Which CAD formats must be supported?** DXF, STEP, IFC only, or also proprietary formats like DWG and Solidworks?
2. **What is the typical model complexity?** How many elements (hundreds vs. hundreds of thousands)?
3. **Standalone tool or plugin?** Does it run as an independent application or integrate into existing CAD software?
4. **What types of modifications are expected?** Simple single-element moves, or complex multi-element cascading changes?
5. **What constraint systems exist?** Dimensional constraints, alignment constraints, connection constraints, or all of the above?
6. **How should ambiguity be handled?** When the user says "the wall" but there are three walls, should the system ask or guess?
7. **What validation is required post-modification?** Structural integrity only, or also manufacturability, code compliance, and clearance checks?
8. **Is there a safety tier system?** Should destructive operations require escalating levels of confirmation?

---

## Requirements

### Functional Requirements

1. **CAD file parsing** -- read and understand DXF, STEP, IFC, and proprietary formats
2. **Geometric understanding** -- comprehend spatial relationships, dimensions, tolerances, and constraints
3. **Natural language to parametric operations** -- translate instructions like "make the wall 2 meters longer" into exact geometric transformations
4. **Constraint solver integration** -- ensure modifications respect existing constraints (dimensions, alignments, connections)
5. **Change validation** -- verify structural integrity, manufacturability, and standards compliance after each change
6. **Undo/redo with version control** -- every modification creates a checkpoint; full change history
7. **Preview rendering** -- show before/after comparison before applying destructive operations
8. **Multi-turn modification dialog** -- support iterative refinement through conversation
9. **Safety checks** -- warn before destructive operations; require confirmation for large-scale changes

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Operation latency (simple) | < 3s for single-element modifications |
| Operation latency (complex) | < 15s for multi-element cascading changes |
| Geometric precision | Sub-millimeter accuracy for all operations |
| Parse time (typical model) | < 10s for models with < 50K elements |
| Undo latency | < 1s to revert any operation |
| Constraint satisfaction | 100% -- no invalid states allowed |

### Out of Scope

- Creating models from scratch (see the Building Plan Generator design)
- Physical simulation (FEA, CFD)
- Rendering photorealistic images (only preview wireframes and shaded views)

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        Chat[Chat Interface<br/>NL Instructions]
        Preview[3D Preview Viewer<br/>Before / After]
        History[Change History<br/>Timeline View]
    end

    subgraph "NL Understanding"
        IntentParser[Intent Parser<br/>Operation Classification]
        ParamExtractor[Parameter Extractor<br/>Dimensions, References]
        AmbiguityResolver[Ambiguity Resolver<br/>Clarification Dialog]
    end

    subgraph "Geometry Engine"
        CADParser[CAD File Parser<br/>DXF, STEP, IFC]
        GeomModel[Geometry Model<br/>B-Rep / CSG]
        SpatialIndex[Spatial Index<br/>R-Tree / Octree]
        ConstraintGraph[Constraint Graph<br/>Dimensions + Relations]
    end

    subgraph "Operation Execution"
        OpTranslator[Operation Translator<br/>NL to Parametric Ops]
        ConstraintSolver[Constraint Solver<br/>Propagate Changes]
        Validator[Change Validator<br/>Integrity + Manufacturability]
        Renderer[Preview Renderer<br/>Wireframe + Shaded]
    end

    subgraph "State Management"
        VersionMgr[Version Manager<br/>Checkpoints]
        ChangeLog[Change Log<br/>Full History]
        SessionMgr[Session Manager<br/>Multi-Turn State]
    end

    subgraph "Storage"
        ModelStore[(Model Store<br/>CAD Files)]
        SnapshotStore[(Snapshot Store<br/>Checkpoints)]
        VDB[(Vector DB<br/>Element Embeddings)]
    end

    Chat --> IntentParser
    IntentParser --> ParamExtractor
    ParamExtractor --> AmbiguityResolver
    AmbiguityResolver --> Chat

    AmbiguityResolver --> OpTranslator
    OpTranslator --> ConstraintSolver
    ConstraintSolver --> ConstraintGraph
    ConstraintSolver --> Validator

    CADParser --> GeomModel
    CADParser --> SpatialIndex
    CADParser --> ConstraintGraph
    GeomModel --> SpatialIndex

    Validator --> Renderer
    Renderer --> Preview
    Validator --> VersionMgr
    VersionMgr --> ChangeLog
    ChangeLog --> History

    VersionMgr --> SnapshotStore
    CADParser --> ModelStore
    GeomModel --> VDB
    SessionMgr --> Chat
```

### Architecture Walkthrough

The user interacts through a **Chat Interface** where they type natural language instructions. The **NL Understanding** layer parses intent (e.g., MOVE_ELEMENT), extracts parameters (direction, distance, target element), and resolves ambiguities by asking clarifying questions when references are unclear.

The **Geometry Engine** is the system's core data layer. It parses CAD files into an internal representation (B-Rep or CSG), builds a spatial index (R-tree or Octree) for efficient proximity queries, and maintains a constraint graph that encodes all dimensional and relational constraints between elements.

The **Operation Execution** layer translates parsed intent into precise parametric operations, propagates changes through the constraint graph to maintain model integrity, validates the result against structural and manufacturing rules, and renders a before/after preview. Only after user confirmation does the system commit the change.

**State Management** tracks all checkpoints and change history, enabling undo to any previous state. The session manager maintains multi-turn conversation context so the user can iteratively refine modifications.

---

## Component Design

### CAD File Parser and Geometry Model

The parser supports multiple CAD formats through format-specific handlers (DXF, STEP/STP, IFC, DWG). For each file, it classifies every element by type (wall, door, beam, pipe), extracts geometric properties (bounding box, centroid, area, volume, vertex count, topology type), and identifies dimensional constraints. After parsing, it builds two critical indices: a **spatial index** (R-tree) for fast proximity and intersection queries, and a **constraint graph** that encodes all relationships between elements.

| Format | Parser Strategy | Key Challenges |
|--------|----------------|----------------|
| DXF | Open standard, direct parsing | 2D-centric, limited semantic info |
| STEP | ISO standard, rich geometry | Complex B-Rep topology |
| IFC | BIM standard, semantic-rich | Large files, deep hierarchy |
| DWG | Proprietary, requires converter | License constraints |

### Natural Language to Parametric Operations

The operation translator bridges the gap between human language and precise geometry. It resolves natural language element references ("the wall near the entrance") to specific model elements using three strategies in order: exact name/ID match, spatial reference resolution (using the R-tree), and semantic search over element descriptions (using the vector DB). When multiple candidates match, it raises an ambiguity error that triggers a clarification dialog.

Once targets are resolved, the LLM generates the parametric operation with exact numeric parameters (all in meters, enforced to 4 decimal places). The available operation types include translate, rotate, scale, mirror, extend, trim, fillet, chamfer, add/remove/copy element, modify parameter, align, and distribute.

### Constraint Solver

The constraint solver is responsible for maintaining model integrity when any element is modified. It walks the constraint graph from the modified element outward (up to depth 5) to identify all dependent elements, clones the model state for safe computation, applies the primary operations, and then iteratively resolves constraint violations until the model reaches a stable state (up to 50 iterations).

If the solver cannot satisfy all constraints within the iteration limit, it reports which constraints remain violated and suggests alternative parameters. This guarantees the system never produces an invalid model state -- a non-negotiable requirement for CAD modification.

### Change Validation and Safety Checks

After constraint propagation, the validator runs five parallel checks: geometry validity (no self-intersecting faces), minimum dimensions (no room below code-required area), structural integrity (load paths maintained), manufacturability (achievable tolerances), and clearances (doors can open, corridors are wide enough).

The system also enforces a tiered safety model based on the scope of impact:

| Risk Level | Trigger | Action |
|------------|---------|--------|
| Low | Single element parameter change | Apply immediately after preview |
| Medium | 2-10 elements affected | Show preview, require confirmation |
| High | 10-50 elements cascading | Detailed impact report, explicit "I understand" confirmation |
| Critical | Structural element removal or > 50 affected elements | Require typed confirmation, log to audit trail |

### Version Control and Undo/Redo

Every modification creates a checkpoint before execution. The version manager stores delta snapshots (not full copies) for storage efficiency -- only the changes between consecutive checkpoints are persisted. This enables sub-second undo by replaying deltas backward. The change log records every checkpoint with a description, timestamp, affected elements, and delta size, providing a full audit trail of all AI-initiated modifications. Users can undo to the previous state or jump to any specific checkpoint in the history.

---

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant NLU as NL Understanding
    participant OpTrans as Op Translator
    participant Solver as Constraint Solver
    participant Valid as Validator
    participant Render as Renderer
    participant VCS as Version Control

    User->>NLU: "Move the kitchen wall 1.5m north"
    NLU->>NLU: Parse intent: MOVE_ELEMENT
    NLU->>NLU: Extract: element=kitchen_wall, direction=north, distance=1.5m

    alt Ambiguous Reference
        NLU->>User: "There are 2 kitchen walls. Did you mean the north or south wall?"
        User->>NLU: "The south wall"
        NLU->>NLU: Resolve: element=wall_47
    end

    NLU->>OpTrans: Translate to parametric operation
    OpTrans->>OpTrans: Operation: translate(wall_47, vector=[0, 1.5, 0])

    OpTrans->>Solver: Propagate constraints
    Solver->>Solver: Find dependent elements (3 connected walls, 1 door, 2 windows)
    Solver->>Solver: Compute cascading modifications

    Solver->>Valid: Validate all changes
    Valid->>Valid: Check: minimum room size OK
    Valid->>Valid: Check: door clearance OK
    Valid->>Valid: Check: structural load path OK

    alt Validation Fails
        Valid->>User: "Moving this wall would reduce bathroom below minimum 5 sqm. Proceed anyway?"
        User->>Valid: "Reduce to 1.2m instead"
        Note over NLU,Valid: Restart with adjusted parameters
    end

    Valid->>VCS: Create checkpoint
    VCS-->>Valid: Checkpoint cp-23

    Valid->>Render: Generate preview
    Render-->>User: Before/after comparison

    User->>Valid: "Apply"
    Valid->>VCS: Commit changes
    VCS-->>User: Applied. Change ID: ch-89
```

The sequence above illustrates the complete modification lifecycle. Notice several key design decisions: ambiguity is resolved interactively (not guessed), constraint violations trigger a re-negotiation with the user rather than silent failure, and the checkpoint is created before the preview so the system can always roll back even if preview generation fails.

---

## Scaling Considerations

| Component | Strategy |
|-----------|----------|
| CAD parsing | Worker pool with format-specific containers; cache parsed models |
| Constraint solving | CPU-bound; scale with compute instances; timeout and approximate for large models |
| Spatial indexing | R-tree fits in memory for most models (< 100K elements); shard for mega-models |
| Version storage | Delta compression; garbage-collect old checkpoints after 30 days |
| Preview rendering | GPU pool for real-time wireframe; pre-rendered snapshots for history view |

---

## Cost Analysis

| Component | Cost/Operation | Notes |
|-----------|---------------|-------|
| LLM inference (intent + translation) | $0.02-0.10 | Depends on context size and clarification rounds |
| Constraint solving (CPU) | $0.001-0.01 | Scales with model complexity and constraint depth |
| Preview rendering (GPU) | $0.01-0.05 | Wireframe is cheap; shaded views cost more |
| Storage (delta snapshots) | $0.001 | Delta compression keeps cost minimal |
| **Total per modification** | **$0.03-0.17** | Typical session has 5-15 modifications |

For an engineer whose time costs $60-100/hour, even a $1 session cost is trivial if it saves 10 minutes of manual CAD operations per modification.

---

## Data Model

The persistence layer must guarantee that every AI-initiated change is reversible and auditable. Geometry precision is preserved by storing coordinates as fixed-precision `NUMERIC` in meters (never floats), and version history is stored as delta snapshots rather than full model copies.

### cad_sessions -- multi-turn modification session

```sql
CREATE TABLE cad_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    source_format VARCHAR(10) NOT NULL CHECK (source_format IN ('dxf', 'step', 'ifc', 'dwg')),
    unit VARCHAR(10) NOT NULL DEFAULT 'meter',
    tolerance_mm NUMERIC(10, 6) NOT NULL DEFAULT 0.001,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'idle', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cad_sessions_user_model ON cad_sessions(user_id, model_id);
```

### model_checkpoints -- delta snapshots for undo/redo

```sql
CREATE TABLE model_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES cad_sessions(id) ON DELETE CASCADE,
    parent_checkpoint_id UUID REFERENCES model_checkpoints(id),
    label VARCHAR(64) NOT NULL,             -- e.g. 'cp-23'
    delta_uri TEXT NOT NULL,                -- object-store pointer to the delta snapshot
    delta_bytes BIGINT NOT NULL,
    element_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_checkpoints_session ON model_checkpoints(session_id, created_at DESC);
```

### operations -- parametric operations translated from NL

```sql
CREATE TABLE operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES cad_sessions(id) ON DELETE CASCADE,
    checkpoint_id UUID REFERENCES model_checkpoints(id),
    instruction TEXT NOT NULL,              -- raw natural-language instruction
    op_type VARCHAR(24) NOT NULL CHECK (op_type IN (
        'translate', 'rotate', 'scale', 'mirror', 'extend', 'trim',
        'fillet', 'chamfer', 'add', 'remove', 'copy', 'modify_param', 'align', 'distribute')),
    params JSONB NOT NULL,                  -- exact numeric parameters, meters at 4 dp
    risk_level VARCHAR(10) NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    affected_element_count INTEGER NOT NULL DEFAULT 0,
    solver_iterations INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN (
        'proposed', 'previewed', 'applied', 'rejected', 'rolled_back')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_operations_session ON operations(session_id, created_at DESC);
CREATE INDEX idx_operations_applied ON operations(status) WHERE status = 'applied';
```

### cached_elements -- cached geometry and metadata per element

```sql
CREATE TABLE cached_elements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES cad_sessions(id) ON DELETE CASCADE,
    element_ref VARCHAR(64) NOT NULL,       -- native CAD id, e.g. 'wall_47'
    element_type VARCHAR(32) NOT NULL,      -- wall, door, beam, pipe, ...
    bbox_min JSONB NOT NULL,                -- [x, y, z] in meters
    bbox_max JSONB NOT NULL,
    centroid JSONB NOT NULL,
    properties JSONB,                       -- area, volume, topology type, tolerances
    embedding vector(768),                  -- element-description embedding for semantic lookup
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, element_ref)
);
CREATE INDEX idx_elements_type ON cached_elements(session_id, element_type);
CREATE INDEX idx_elements_embedding ON cached_elements USING hnsw (embedding vector_cosine_ops);
```

### change_audit -- audit trail of applied changes

```sql
CREATE TABLE change_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id UUID NOT NULL REFERENCES operations(id),
    change_ref VARCHAR(64) NOT NULL,        -- e.g. 'ch-89'
    from_checkpoint UUID REFERENCES model_checkpoints(id),
    to_checkpoint UUID REFERENCES model_checkpoints(id),
    validation_report JSONB NOT NULL,       -- per-check pass/fail: geometry, dims, structural, clearance
    confirmed_by VARCHAR(64),               -- user id for high/critical typed confirmation
    confirmation_type VARCHAR(20) CHECK (confirmation_type IN ('auto', 'click', 'typed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_operation ON change_audit(operation_id);
```

---

## Failure Modes / Production Issues

In a domain where approximate answers are unacceptable, most production incidents come from silent geometric corruption rather than crashes. The failure modes below map directly to the validator gate, the constraint solver, and the checkpoint-before-execute invariant.

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Modified model fails to regenerate / rebuild after an operation | A parametric edit invalidated a downstream feature or broke a B-Rep face loop | Regenerate on the cloned state first; on regeneration error reject the operation and roll back to the pre-operation checkpoint before any commit; surface the failing feature to the user |
| Dimensions drift by fractions of a millimeter over a session | Repeated float conversions between the model unit and internal representation accumulate rounding error | Store all coordinates as fixed-precision `NUMERIC` in meters at 4 dp; convert exactly once at parse and once at export; compare with `tolerance_mm`, never exact float equality |
| Boolean / union produces non-manifold or self-intersecting geometry | Coincident faces or near-zero-thickness walls from a scaled or mirrored operation | Run manifold and self-intersection checks in the validator gate; snap near-coincident vertices within tolerance; reject and report the offending elements instead of committing |
| A destructive change cannot be undone | Operation committed before a checkpoint was created, or the checkpoint delta was empty | Enforce the checkpoint-before-execute ordering; treat a missing or empty delta as a hard failure that blocks the commit |
| Constraint solver never converges (hits the 50-iteration limit) | Over-constrained or cyclic constraint graph; conflicting dimensional constraints | Detect cycles before solving and cap traversal depth at 5; on non-convergence report the unsatisfied constraints with suggested parameter relaxations rather than applying a partial result |
| Instruction applied to the wrong element | A natural-language reference resolved to the wrong candidate when several elements matched | Never guess on multiple matches -- raise an ambiguity error and open a clarification dialog; record the resolved `element_ref` in the audit trail |

---

## Trade-offs & Alternatives

| Decision | Rationale | Alternative | Why Not |
|----------|-----------|-------------|---------|
| Late fusion for NL understanding (separate intent, parameter, ambiguity stages) | Each stage can be debugged and improved independently; ambiguity resolution needs user interaction | Single-shot LLM call to generate operation directly | Loses the ability to ask clarifying questions; harder to debug wrong operations |
| Constraint graph with iterative solver | Guarantees model integrity; handles cascading dependencies automatically | Manual dependency tracking per operation type | Does not scale to complex models; easy to miss dependencies; no convergence guarantee |
| Delta-based version storage | Storage-efficient; enables fast undo by replaying deltas | Full model snapshots at each checkpoint | Prohibitively expensive for large models; 50K-element model at every checkpoint wastes storage |
| Tiered safety confirmation | Proportional friction -- low-risk changes are fast, high-risk changes get scrutiny | Uniform confirmation for all operations | Too much friction for simple changes drives users away; too little for destructive changes is dangerous |
| R-tree spatial index | Industry-standard for spatial queries; memory-efficient for typical model sizes | Octree or brute-force spatial search | Octree is better for 3D but overkill for many 2D/2.5D CAD models; brute-force does not scale |

---

## Interview Tips

:::tip How to Present This (35 minutes)
- **Minutes 1-5:** Clarify requirements -- which CAD formats, modification complexity (single vs. cascading), standalone vs. plugin, safety expectations
- **Minutes 5-15:** Draw the architecture -- NL understanding pipeline (intent, parameter extraction, ambiguity resolution), geometry engine (parser, spatial index, constraint graph), operation execution (translator, solver, validator, renderer)
- **Minutes 15-25:** Deep dive into the constraint solver (graph traversal, iterative propagation, convergence guarantee) and NL-to-parametric-operation translation (reference resolution strategies, precision enforcement)
- **Minutes 25-30:** Discuss the safety tier system, version control with delta snapshots, and scaling strategies for large models
- **Minutes 30-35:** Trade-offs (iterative solver vs. manual tracking, delta vs. full snapshots) and edge cases (sub-millimeter precision, numerical stability, unit conversion errors)
:::
