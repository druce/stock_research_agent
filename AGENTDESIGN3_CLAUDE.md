# Report Writer Agent Design v3: DVC + Promptflow Edition

## Overview

A production-grade research report generator using **DVC for data pipeline orchestration** and **Promptflow for LLM workflow management**. This design maintains the beads-first research approach from v2 while adding:

- **DAG-based execution**: True dependency graphs, not just sequential phases
- **Data versioning**: Every artifact tracked and versioned with DVC
- **Prompt engineering**: Promptflow for prompt versioning, testing, and evaluation
- **Reproducibility**: Complete lineage from sources to final report
- **Experiment tracking**: Compare prompts, models, and configurations
- **Incremental execution**: Only rerun changed stages

Reference implementation: `~/projects/stock_research_agent`

## Core Principles

1. **Separation of Concerns**:
   - DVC: Data pipeline orchestration, versioning, caching
   - Promptflow: LLM workflow execution, prompt management, evaluation
   - Beads: Single source of truth for research data

2. **DAG-First Design**:
   - All dependencies explicit in `dvc.yaml`
   - Parallel execution where possible
   - Automatic invalidation and recomputation

3. **Version Everything**:
   - Source data (DVC)
   - Prompts (Promptflow + Git)
   - Beads and indexes (DVC)
   - Configurations (Git)
   - Models and parameters (DVC params)

4. **Reproducibility**:
   - `dvc repro` recreates entire report
   - Git hash + DVC cache = exact reproduction
   - Experiment tracking for prompt iterations

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Git Repository                           │
│  • YAML configs (dvc.yaml, params.yaml, prompts/*.yaml)     │
│  • Promptflow definitions (flows/*.yaml)                     │
│  • Python code (stages/*.py, tools/*.py)                     │
│  • Templates (templates/*.jinja2)                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     DVC Pipeline (dvc.yaml)                  │
│                                                               │
│  Stage 0: intake           → outline.json, metadata.json     │
│  Stage 1: research         → sources/, beads/index.json      │
│  Stage 2: section_*        → sections/*.md (parallel DAG)    │
│  Stage 3: assemble         → drafts/full_report.md           │
│  Stage 4: render           → report/report.{md,pdf}          │
│                                                               │
│  Each stage tracks: inputs, outputs, params, metrics         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Promptflow Flows (one per section)              │
│                                                               │
│  flow_section_writer/                                        │
│    ├─ flow.dag.yaml       # DAG: retrieve → write → critique│
│    ├─ prompts/            # Version-controlled prompts       │
│    └─ evaluate/           # Quality evaluators               │
│                                                               │
│  Visual DAG editor, A/B testing, metrics tracking            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Data Layer (DVC-tracked)                   │
│                                                               │
│  work/{ticker}_{date}/                                       │
│    ├─ sources/          (.dvc tracked)                       │
│    ├─ beads/            (.dvc tracked)                       │
│    ├─ tables/           (.dvc tracked)                       │
│    ├─ charts/           (.dvc tracked)                       │
│    ├─ sections/         (.dvc tracked)                       │
│    └─ report/           (.dvc tracked)                       │
│                                                               │
│  Remote storage: S3/Azure/GCS for large files               │
└─────────────────────────────────────────────────────────────┘
```

## DVC Pipeline Definition

### Primary Pipeline: `dvc.yaml`

```yaml
stages:
  # Stage 0: Intake and validation
  intake:
    cmd: python stages/intake.py --ticker ${ticker} --output-dir work/${ticker}_${date}
    params:
      - params.yaml:
          - ticker
          - date
          - report_config
    outs:
      - work/${ticker}_${date}/outline.json
      - work/${ticker}_${date}/metadata.json
    metrics:
      - work/${ticker}_${date}/metrics/phase0.json:
          cache: false

  # Stage 1: Research (parallelized by source type)
  research_sec:
    cmd: python stages/research.py --source sec --ticker ${ticker} --workdir work/${ticker}_${date}
    deps:
      - work/${ticker}_${date}/metadata.json
      - stages/research.py
    params:
      - params.yaml:
          - research.sec
    outs:
      - work/${ticker}_${date}/sources/sec_filings/
      - work/${ticker}_${date}/beads/sec/:
          cache: true
    metrics:
      - work/${ticker}_${date}/metrics/research_sec.json:
          cache: false

  research_news:
    cmd: python stages/research.py --source news --ticker ${ticker} --workdir work/${ticker}_${date}
    deps:
      - work/${ticker}_${date}/metadata.json
      - stages/research.py
    params:
      - params.yaml:
          - research.news
    outs:
      - work/${ticker}_${date}/sources/news/
      - work/${ticker}_${date}/beads/news/:
          cache: true
    metrics:
      - work/${ticker}_${date}/metrics/research_news.json:
          cache: false

  research_fundamentals:
    cmd: python stages/research.py --source fundamentals --ticker ${ticker} --workdir work/${ticker}_${date}
    deps:
      - work/${ticker}_${date}/metadata.json
      - stages/research.py
    params:
      - params.yaml:
          - research.fundamentals
    outs:
      - work/${ticker}_${date}/sources/fundamentals/
      - work/${ticker}_${date}/beads/fundamentals/:
          cache: true
    metrics:
      - work/${ticker}_${date}/metrics/research_fundamentals.json:
          cache: false

  research_transcripts:
    cmd: python stages/research.py --source transcripts --ticker ${ticker} --workdir work/${ticker}_${date}
    deps:
      - work/${ticker}_${date}/metadata.json
      - stages/research.py
    params:
      - params.yaml:
          - research.transcripts
    outs:
      - work/${ticker}_${date}/sources/transcripts/
      - work/${ticker}_${date}/beads/transcripts/:
          cache: true
    metrics:
      - work/${ticker}_${date}/metrics/research_transcripts.json:
          cache: false

  # Consolidate research results
  consolidate_research:
    cmd: python stages/consolidate_beads.py --workdir work/${ticker}_${date}
    deps:
      - work/${ticker}_${date}/beads/sec/
      - work/${ticker}_${date}/beads/news/
      - work/${ticker}_${date}/beads/fundamentals/
      - work/${ticker}_${date}/beads/transcripts/
      - stages/consolidate_beads.py
    params:
      - params.yaml:
          - beads.validation
    outs:
      - work/${ticker}_${date}/beads/index.json:
          cache: true
      - work/${ticker}_${date}/beads/by_section/:
          cache: true
      - work/${ticker}_${date}/beads/relationships.json:
          cache: true
    metrics:
      - work/${ticker}_${date}/metrics/research_consolidated.json:
          cache: false

  # Stage 2: Section writing (parallelized by section dependencies)
  section_company_profile:
    cmd: |
      pf run create --flow flows/section_writer \
        --data work/${ticker}_${date}/section_inputs/company_profile.jsonl \
        --run section_company_profile_${date} \
        --stream
    deps:
      - work/${ticker}_${date}/beads/index.json
      - work/${ticker}_${date}/outline.json
      - flows/section_writer/
      - stages/prepare_section_input.py
    params:
      - params.yaml:
          - sections.company_profile
    outs:
      - work/${ticker}_${date}/sections/company_profile.md
      - work/${ticker}_${date}/sections/company_profile_metadata.json
    metrics:
      - work/${ticker}_${date}/metrics/section_company_profile.json:
          cache: false

  section_business_model:
    cmd: |
      pf run create --flow flows/section_writer \
        --data work/${ticker}_${date}/section_inputs/business_model.jsonl \
        --run section_business_model_${date} \
        --stream
    deps:
      - work/${ticker}_${date}/beads/index.json
      - work/${ticker}_${date}/sections/company_profile.md  # dependency
      - flows/section_writer/
    params:
      - params.yaml:
          - sections.business_model
    outs:
      - work/${ticker}_${date}/sections/business_model.md
      - work/${ticker}_${date}/sections/business_model_metadata.json
    metrics:
      - work/${ticker}_${date}/metrics/section_business_model.json:
          cache: false

  section_financials:
    cmd: |
      pf run create --flow flows/section_writer \
        --data work/${ticker}_${date}/section_inputs/financials.jsonl \
        --run section_financials_${date} \
        --stream
    deps:
      - work/${ticker}_${date}/beads/index.json
      - work/${ticker}_${date}/sections/company_profile.md
      - flows/section_writer/
    params:
      - params.yaml:
          - sections.financials
    outs:
      - work/${ticker}_${date}/sections/financials.md
      - work/${ticker}_${date}/sections/financials_metadata.json
    metrics:
      - work/${ticker}_${date}/metrics/section_financials.json:
          cache: false

  section_valuation:
    cmd: |
      pf run create --flow flows/section_writer \
        --data work/${ticker}_${date}/section_inputs/valuation.jsonl \
        --run section_valuation_${date} \
        --stream
    deps:
      - work/${ticker}_${date}/beads/index.json
      - work/${ticker}_${date}/sections/company_profile.md
      - work/${ticker}_${date}/sections/financials.md  # dependency
      - flows/section_writer/
    params:
      - params.yaml:
          - sections.valuation
    outs:
      - work/${ticker}_${date}/sections/valuation.md
      - work/${ticker}_${date}/sections/valuation_metadata.json
    metrics:
      - work/${ticker}_${date}/metrics/section_valuation.json:
          cache: false

  # ... additional sections follow same pattern

  # Stage 3: Assembly and global critique
  assemble:
    cmd: |
      pf run create --flow flows/report_assembler \
        --data work/${ticker}_${date}/assembly_input.jsonl \
        --run report_assembly_${date} \
        --stream
    deps:
      - work/${ticker}_${date}/sections/company_profile.md
      - work/${ticker}_${date}/sections/business_model.md
      - work/${ticker}_${date}/sections/financials.md
      - work/${ticker}_${date}/sections/valuation.md
      # ... all other sections
      - flows/report_assembler/
    params:
      - params.yaml:
          - assembly
    outs:
      - work/${ticker}_${date}/drafts/full_report.md
      - work/${ticker}_${date}/drafts/critique_global.json
    metrics:
      - work/${ticker}_${date}/metrics/assembly.json:
          cache: false

  # Stage 4: Render final outputs
  render:
    cmd: python stages/render.py --workdir work/${ticker}_${date}
    deps:
      - work/${ticker}_${date}/drafts/full_report.md
      - work/${ticker}_${date}/beads/index.json
      - work/${ticker}_${date}/outline.json
      - templates/report_template.jinja2
      - stages/render.py
    params:
      - params.yaml:
          - rendering
    outs:
      - work/${ticker}_${date}/report/report.md
      - work/${ticker}_${date}/report/report.pdf
      - work/${ticker}_${date}/report/report_metadata.json
    metrics:
      - work/${ticker}_${date}/metrics/final.json:
          cache: false
    plots:
      - work/${ticker}_${date}/metrics/quality_metrics.json:
          x: section
          y: quality_score

# Metrics aggregation
  aggregate_metrics:
    cmd: python stages/aggregate_metrics.py --workdir work/${ticker}_${date}
    deps:
      - work/${ticker}_${date}/metrics/
    outs:
      - work/${ticker}_${date}/quality_report.json
    metrics:
      - work/${ticker}_${date}/quality_report.json:
          cache: false
```

### Parameter Configuration: `params.yaml`

```yaml
ticker: AAPL
date: 2026-01-15

report_config:
  type: full_research
  template: standard_equity_research

# Research source configurations
research:
  sec:
    required_forms: [10-K, 10-Q]
    max_age_days: 365
    retry_policy:
      max_attempts: 3
      backoff: exponential

  news:
    lookback_days: 90
    min_articles: 10
    min_relevance: 0.7
    sources_preferred: [bloomberg, reuters, wsj]

  fundamentals:
    metrics_required:
      - revenue
      - operating_margin
      - fcf
      - debt_to_equity
      - roic
    periods: 8

  transcripts:
    quarters: 4

# Bead validation rules
beads:
  validation:
    min_confidence: 0.7
    min_quality_score: 0.7
    required_types: [source, fact, metric]
    relationship_strength_threshold: 0.5

  indexing:
    enable_by_section: true
    enable_by_topic: true
    enable_by_source: true
    enable_relationships: true

# Section configurations
sections:
  company_profile:
    target_length: 600
    min_beads: 8
    quality_threshold: 0.80
    depends_on: []
    priority: high
    model: claude-opus-4

  business_model:
    target_length: 700
    min_beads: 10
    quality_threshold: 0.82
    depends_on: [company_profile]
    priority: high
    model: claude-opus-4

  financials:
    target_length: 900
    min_beads: 15
    quality_threshold: 0.85
    depends_on: [company_profile]
    priority: critical
    model: claude-opus-4

  valuation:
    target_length: 800
    min_beads: 12
    quality_threshold: 0.85
    depends_on: [company_profile, financials]
    priority: critical
    model: claude-opus-4

# Assembly configuration
assembly:
  model: claude-opus-4
  critique:
    check_for:
      - redundancy_across_sections
      - contradictions
      - tone_consistency
      - logical_flow
      - citation_completeness
  optimization:
    goals:
      - remove_redundancy
      - improve_transitions
      - normalize_tone
      - strengthen_conclusion

# Rendering configuration
rendering:
  formats: [md, pdf, html]
  template: templates/report_template.jinja2
  include_disclaimers: true
  include_toc: true
  include_citations: true
```

## Promptflow Integration

### Flow Definition: `flows/section_writer/flow.dag.yaml`

Each section is written using a Promptflow flow with a clear DAG:

```yaml
# flows/section_writer/flow.dag.yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
inputs:
  section_id:
    type: string
  beads:
    type: object
  outline:
    type: object
  config:
    type: object

outputs:
  section_text:
    type: string
    reference: ${optimize.output}
  metadata:
    type: object
    reference: ${quality_check.output}

nodes:
  # Step 1: Retrieve and filter beads
  - name: retrieve_beads
    type: python
    source:
      type: code
      path: retrieve_beads.py
    inputs:
      section_id: ${inputs.section_id}
      beads: ${inputs.beads}
      min_quality: ${inputs.config.min_quality}

  # Step 2: Prepare context
  - name: prepare_context
    type: python
    source:
      type: code
      path: prepare_context.py
    inputs:
      section_id: ${inputs.section_id}
      beads: ${retrieve_beads.output}
      outline: ${inputs.outline}

  # Step 3: Write section draft
  - name: write_draft
    type: llm
    source:
      type: code
      path: write_section_prompt.jinja2
    inputs:
      deployment_name: ${inputs.config.model}
      temperature: 0.3
      max_tokens: 3000
      section_spec: ${prepare_context.output}
    connection: anthropic_connection
    api: chat

  # Step 4: Critique
  - name: critique
    type: llm
    source:
      type: code
      path: critique_prompt.jinja2
    inputs:
      deployment_name: ${inputs.config.model}
      temperature: 0.2
      max_tokens: 1500
      draft: ${write_draft.output}
      section_spec: ${prepare_context.output}
    connection: anthropic_connection
    api: chat

  # Step 5: Optimize based on critique
  - name: optimize
    type: llm
    source:
      type: code
      path: optimize_prompt.jinja2
    inputs:
      deployment_name: ${inputs.config.model}
      temperature: 0.3
      max_tokens: 3000
      draft: ${write_draft.output}
      critique: ${critique.output}
      section_spec: ${prepare_context.output}
    connection: anthropic_connection
    api: chat

  # Step 6: Quality validation
  - name: quality_check
    type: python
    source:
      type: code
      path: quality_check.py
    inputs:
      section_text: ${optimize.output}
      section_id: ${inputs.section_id}
      config: ${inputs.config}
      beads: ${retrieve_beads.output}
```

### Prompt Template Example: `flows/section_writer/write_section_prompt.jinja2`

```jinja2
system:
You are a professional equity research analyst writing a section of a comprehensive research report.

Your task: Write the "{{ section_spec.title }}" section.

Guidelines:
- Target length: {{ section_spec.target_length }} words (±10%)
- Use only the provided beads and data as sources
- Cite all facts with [bead_id] references
- Maintain professional, analytical tone
- Focus on material information

user:
# Section: {{ section_spec.title }}

## Available Research Data (Beads)

{% for bead in section_spec.beads %}
### [{{ bead.id }}] {{ bead.title }}
**Type**: {{ bead.type }}
**Confidence**: {{ bead.confidence }}
**Summary**: {{ bead.summary }}
**Content**: {{ bead.content | tojson }}
**Source**: {{ bead.source.title }} ({{ bead.source.url }})
**Tags**: {{ bead.tags.topic | join(", ") }}

{% endfor %}

## Tables
{% for table in section_spec.tables %}
- {{ table.name }}: {{ table.description }}
{% endfor %}

## Charts
{% for chart in section_spec.charts %}
- {{ chart.name }}: {{ chart.description }}
{% endfor %}

## Instructions

Write the "{{ section_spec.title }}" section following these requirements:
1. Synthesize the beads into a coherent narrative
2. Address these specific points:
{% for requirement in section_spec.requirements %}
   - {{ requirement }}
{% endfor %}
3. Use citations [bead_id] for all factual claims
4. Reference tables and charts where relevant
5. Maintain logical flow and clear structure

Begin your section now:
```

### Evaluation Flow: `flows/section_writer/evaluate/flow.dag.yaml`

Promptflow includes built-in evaluation:

```yaml
# flows/section_writer/evaluate/flow.dag.yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json

inputs:
  section_text:
    type: string
  ground_truth:
    type: object
  section_spec:
    type: object

outputs:
  metrics:
    type: object
    reference: ${aggregate_metrics.output}

nodes:
  # Evaluate citation completeness
  - name: eval_citations
    type: python
    source:
      type: code
      path: eval_citations.py
    inputs:
      section_text: ${inputs.section_text}
      beads: ${inputs.ground_truth.beads}

  # Evaluate factual accuracy
  - name: eval_accuracy
    type: llm
    source:
      type: code
      path: eval_accuracy_prompt.jinja2
    inputs:
      section_text: ${inputs.section_text}
      beads: ${inputs.ground_truth.beads}

  # Evaluate coherence
  - name: eval_coherence
    type: llm
    source:
      type: code
      path: eval_coherence_prompt.jinja2
    inputs:
      section_text: ${inputs.section_text}

  # Evaluate completeness
  - name: eval_completeness
    type: python
    source:
      type: code
      path: eval_completeness.py
    inputs:
      section_text: ${inputs.section_text}
      requirements: ${inputs.section_spec.requirements}

  # Aggregate metrics
  - name: aggregate_metrics
    type: python
    source:
      type: code
      path: aggregate.py
    inputs:
      citations: ${eval_citations.output}
      accuracy: ${eval_accuracy.output}
      coherence: ${eval_coherence.output}
      completeness: ${eval_completeness.output}
```

## Data Model (Enhanced for DVC)

### Bead Schema (Same as v2, DVC-tracked)

```json
{
  "id": "bead_20260115_103042_001",
  "version": 1,
  "type": "metric",
  "title": "FY2023 revenue",
  "summary": "Company revenue for FY2023 from audited 10-K.",
  "content": {
    "metric": "revenue",
    "value": 383.3,
    "unit": "USD_B",
    "period": "FY2023"
  },
  "source": {
    "type": "SEC_10K",
    "title": "Form 10-K FY2023",
    "url": "https://www.sec.gov/...",
    "file_path": "sources/sec_10k_fy2023.txt",
    "dvc_hash": "md5:a1b2c3d4...",  # DVC tracks the file
    "retrieved_at": "2026-01-15T10:30:42Z"
  },
  "confidence": 0.95,
  "quality_score": 0.92,
  "freshness": "2023-10-31",
  "timestamp": "2026-01-15T10:30:42Z",
  "extraction_method": "llm",
  "review_status": "approved",
  "tags": {
    "section": ["company_profile", "financials"],
    "topic": ["revenue", "scale"]
  }
}
```

### DVC Metadata Files

DVC generates `.dvc` files for tracked directories:

```yaml
# work/AAPL_20260115/beads/index.json.dvc
outs:
- md5: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  size: 45632
  path: index.json
```

### Directory Structure (DVC-aware)

```
stock_research_agent/
├── .dvc/                     # DVC cache and config
│   ├── cache/                # Local cache of all tracked files
│   └── config                # Remote storage config
│
├── .git/                     # Git repository
│
├── dvc.yaml                  # Main pipeline definition
├── params.yaml               # Parameterized configuration
├── dvc.lock                  # Lock file for reproducibility
│
├── flows/                    # Promptflow definitions (Git-tracked)
│   ├── section_writer/
│   │   ├── flow.dag.yaml
│   │   ├── prompts/
│   │   │   ├── write_section_prompt.jinja2
│   │   │   ├── critique_prompt.jinja2
│   │   │   └── optimize_prompt.jinja2
│   │   ├── evaluate/
│   │   │   └── flow.dag.yaml
│   │   ├── retrieve_beads.py
│   │   ├── prepare_context.py
│   │   └── quality_check.py
│   │
│   ├── report_assembler/
│   │   ├── flow.dag.yaml
│   │   └── prompts/
│   │
│   └── research_extractor/
│       ├── flow.dag.yaml
│       └── prompts/
│
├── stages/                   # DVC stage scripts (Git-tracked)
│   ├── intake.py
│   ├── research.py
│   ├── consolidate_beads.py
│   ├── prepare_section_input.py
│   ├── render.py
│   └── aggregate_metrics.py
│
├── tools/                    # Shared utilities (Git-tracked)
│   ├── beads.py
│   ├── files.py
│   ├── quality.py
│   └── validation.py
│
├── templates/                # Report templates (Git-tracked)
│   ├── report_template.jinja2
│   └── section_templates/
│
├── work/                     # Working directory (DVC-tracked)
│   └── {TICKER}_{DATE}/
│       ├── sources/          # DVC-tracked
│       ├── beads/            # DVC-tracked
│       ├── tables/           # DVC-tracked
│       ├── charts/           # DVC-tracked
│       ├── sections/         # DVC-tracked
│       ├── drafts/           # DVC-tracked
│       ├── report/           # DVC-tracked
│       ├── metrics/          # DVC metrics (not cached)
│       ├── outline.json      # DVC-tracked
│       └── metadata.json     # DVC-tracked
│
├── .dvcignore                # Files to ignore in DVC
├── .gitignore                # Files to ignore in Git
└── README.md
```

## Execution Workflows

### 1. Initial Run (Full Pipeline)

```bash
# Configure ticker and date
dvc params diff  # Review current params

# Run full pipeline
dvc repro

# View metrics
dvc metrics show

# View plots
dvc plots show work/AAPL_20260115/metrics/quality_metrics.json

# Push to remote storage (optional)
dvc push
git add dvc.lock params.yaml .dvc
git commit -m "Report for AAPL 2026-01-15"
git push
```

### 2. Incremental Update (Change Parameters)

```bash
# Update ticker or config
vim params.yaml  # Change ticker: MSFT

# DVC automatically detects changes and reruns affected stages
dvc repro

# Only changed stages execute
# Cached stages are skipped
```

### 3. Prompt Iteration (A/B Testing)

```bash
# Create experiment branch
git checkout -b experiment/better-valuation-prompt

# Edit prompt
vim flows/section_writer/prompts/write_section_prompt.jinja2

# Rerun only valuation section
dvc repro section_valuation

# Compare metrics
dvc metrics diff main

# If better, merge; otherwise discard
```

### 4. Reproduce Exact Report

```bash
# Clone repository
git clone <repo-url>
cd stock_research_agent

# Checkout specific commit
git checkout a1b2c3d4

# Pull DVC-tracked files from remote
dvc pull

# Reproduce pipeline (uses cached data)
dvc repro

# Result: Exact same report as original run
```

### 5. Parallel Execution

DVC automatically parallelizes independent stages:

```bash
# Run with 4 parallel jobs
dvc repro -j 4

# Research stages (sec, news, fundamentals, transcripts) run in parallel
# Section stages run in parallel when dependencies met
```

### 6. Development Mode (Single Section)

```bash
# Work on just one section
dvc repro section_company_profile

# Test changes quickly
# All dependencies auto-resolved
```

## Promptflow Development Workflow

### 1. Interactive Flow Development

```bash
# Start Promptflow UI
pf flow test --flow flows/section_writer --ui

# Interactively test with sample inputs
# Debug each node
# Adjust prompts in real-time
```

### 2. Batch Evaluation

```bash
# Prepare test dataset
cat > test_data.jsonl << EOF
{"section_id": "company_profile", "beads": {...}, "outline": {...}}
{"section_id": "financials", "beads": {...}, "outline": {...}}
EOF

# Run batch test
pf run create --flow flows/section_writer --data test_data.jsonl

# Run evaluation
pf run create --flow flows/section_writer/evaluate \
  --data test_data.jsonl \
  --run <run-id>

# View results
pf run show-metrics --run <run-id>
```

### 3. Prompt Versioning

All prompts are version-controlled in Git:

```bash
# View prompt history
git log flows/section_writer/prompts/write_section_prompt.jinja2

# Compare prompt versions
git diff v1.0 v2.0 -- flows/section_writer/prompts/

# Rollback to previous prompt
git checkout v1.0 -- flows/section_writer/prompts/write_section_prompt.jinja2
```

### 4. Model Comparison

```yaml
# params.yaml
sections:
  valuation:
    model: claude-opus-4  # Try different models
    # model: claude-sonnet-4
    # model: gpt-4
```

```bash
# Run with Claude Opus
dvc repro section_valuation

# Save metrics
dvc metrics show > metrics_opus.txt

# Change to Sonnet
vim params.yaml  # Change model

# Rerun
dvc repro section_valuation

# Compare
dvc metrics diff
```

## Advanced DVC Features

### 1. Remote Storage Configuration

```bash
# Configure S3 remote
dvc remote add -d myremote s3://my-bucket/stock-research-data

# Or Azure
dvc remote add -d myremote azure://mycontainer/stock-research-data

# Or GCS
dvc remote add -d myremote gs://my-bucket/stock-research-data

# Push data
dvc push

# Team members can pull
dvc pull
```

### 2. Experiment Tracking

```bash
# Run experiment with different parameters
dvc exp run -S research.news.lookback_days=180

# Compare experiments
dvc exp show --include-params research.news

# Apply best experiment
dvc exp apply <exp-name>
```

### 3. Metrics and Plots

Define metrics in `params.yaml`:

```yaml
# dvc.yaml (metrics section)
metrics:
  - work/${ticker}_${date}/quality_report.json:
      cache: false

plots:
  - work/${ticker}_${date}/metrics/section_scores.csv:
      x: section
      y: quality_score
      title: Section Quality Scores

  - work/${ticker}_${date}/metrics/bead_distribution.json:
      template: bar
      x: section
      y: bead_count
```

```bash
# Show all metrics
dvc metrics show

# Show metrics diff
dvc metrics diff HEAD~1

# Generate HTML plots
dvc plots show --open
```

### 4. Pipeline Visualization

```bash
# View pipeline DAG
dvc dag

# HTML visualization
dvc dag --dot | dot -Tpng -o pipeline.png
```

Output:
```
         +--------+
         | intake |
         +--------+
              *
              *
              *
    *********************
    *        *          *
+----------+ * +-----------------+
| research_| * | research_news   |
| sec      | * +-----------------+
+----------+ *          *
    *        *          *
    *********************
              *
              *
    +-----------------+
    | consolidate_    |
    | research        |
    +-----------------+
         ***  ***
        *        *
+----------+  +----------+
| section_ |  | section_ |
| company_ |  | business |
| profile  |  | _model   |
+----------+  +----------+
    |            |
    +-----+------+
          |
    +----------+
    | section_ |
    | valuation|
    +----------+
          |
          v
    (assemble, render)
```

## Quality Assurance with Promptflow Evaluation

### Evaluation Metrics

Promptflow tracks multiple metrics per section:

```json
{
  "run_id": "section_valuation_20260115",
  "metrics": {
    "citation_completeness": 0.92,
    "factual_accuracy": 0.88,
    "coherence_score": 0.85,
    "completeness_score": 0.90,
    "readability_score": 0.87,
    "length_adherence": 0.95,
    "composite_quality": 0.89
  },
  "line_metrics": [
    {
      "line_number": 0,
      "section_id": "valuation",
      "citation_count": 12,
      "unique_sources": 6,
      "word_count": 847
    }
  ]
}
```

### Custom Evaluators

Create custom Python evaluators:

```python
# flows/section_writer/evaluate/eval_citations.py
from typing import Dict, Any

def eval_citation_completeness(
    section_text: str,
    beads: list[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Evaluate whether all critical facts are cited.
    """
    # Extract citations from text
    citations = extract_citations(section_text)

    # Get high-confidence beads (should be cited)
    critical_beads = [b for b in beads if b["confidence"] > 0.9]

    # Check coverage
    cited_count = sum(1 for b in critical_beads if b["id"] in citations)
    completeness = cited_count / len(critical_beads) if critical_beads else 1.0

    return {
        "citation_completeness": completeness,
        "total_citations": len(citations),
        "critical_beads": len(critical_beads),
        "critical_cited": cited_count
    }
```

### Evaluation Runs

```bash
# Run evaluation on completed sections
pf run create \
  --flow flows/section_writer/evaluate \
  --data work/AAPL_20260115/section_inputs/valuation.jsonl \
  --column-mapping section_text='${run.outputs.section_text}' \
  --run eval_valuation_20260115

# View results
pf run show-metrics --run eval_valuation_20260115

# Visualize
pf run visualize --runs section_valuation_20260115
```

## Error Handling and Recovery

### DVC Checkpoint Recovery

DVC automatically handles recovery:

```bash
# Pipeline crashes mid-run
# Some stages completed, others didn't

# Simply rerun
dvc repro

# DVC skips completed stages (based on checksums)
# Only reruns failed/incomplete stages
```

### Stage-Level Error Handling

```python
# stages/research.py
import sys
import logging
from tools.checkpoint import save_checkpoint, load_checkpoint

def main():
    try:
        # Try to resume from checkpoint
        state = load_checkpoint("research_sec")
        if state:
            logging.info("Resuming from checkpoint")
            # Continue from saved state
        else:
            # Fresh start
            state = initialize_research()

        # Execute with retries
        results = fetch_with_retry(ticker, source_type)

        # Save checkpoint periodically
        save_checkpoint("research_sec", state)

        # Process results
        beads = extract_beads(results)
        save_beads(beads)

    except Exception as e:
        logging.error(f"Stage failed: {e}")
        save_error_state(e)
        sys.exit(1)  # DVC marks stage as failed

if __name__ == "__main__":
    main()
```

### Promptflow Error Handling

Promptflow nodes can have error handling:

```python
# flows/section_writer/write_draft_with_retry.py
from promptflow import tool
from tenacity import retry, stop_after_attempt, wait_exponential

@tool
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def write_section_with_retry(section_spec: dict, config: dict) -> str:
    """
    Write section with automatic retry on failure.
    """
    try:
        # Call LLM
        result = llm_call(section_spec, config)
        return result
    except RateLimitError:
        # Will be retried by decorator
        raise
    except Exception as e:
        # Log and reraise
        logging.error(f"LLM call failed: {e}")
        raise
```

## Performance Optimization

### 1. DVC Cache Optimization

```bash
# Enable shared cache for team
dvc cache dir --shared /shared/dvc-cache

# Link instead of copy (faster)
dvc config cache.type symlink

# Parallel downloads
dvc pull -j 8
```

### 2. Promptflow Caching

Promptflow caches LLM responses:

```yaml
# flows/section_writer/flow.dag.yaml
nodes:
  - name: write_draft
    type: llm
    source:
      type: code
      path: write_section_prompt.jinja2
    inputs:
      # ...
    use_variants: false
    enable_cache: true  # Cache LLM responses
```

### 3. Parallel Research

DVC runs independent stages in parallel:

```yaml
# dvc.yaml - These run in parallel
stages:
  research_sec: {...}
  research_news: {...}
  research_fundamentals: {...}
  research_transcripts: {...}
```

```bash
# Specify parallelism
dvc repro -j 4  # 4 parallel jobs
```

### 4. Incremental Beads

Only reprocess changed sources:

```python
# stages/consolidate_beads.py
def consolidate_beads(workdir):
    # Load existing index if available
    existing_index = load_if_exists(f"{workdir}/beads/index.json")

    # Check which source dirs changed (DVC provides this)
    changed_sources = get_changed_sources()

    if existing_index and not changed_sources:
        # No changes, return existing
        return existing_index

    # Only reprocess changed sources
    new_beads = []
    for source_type in changed_sources:
        beads = load_beads(f"{workdir}/beads/{source_type}")
        new_beads.extend(beads)

    # Merge with existing
    merged = merge_beads(existing_index, new_beads)
    return merged
```

## Experiment Tracking and Comparison

### Experiment Workflow

```bash
# Baseline run
dvc repro
dvc metrics show > baseline_metrics.txt

# Experiment 1: Different model
dvc exp run -n "try-sonnet" -S sections.valuation.model=claude-sonnet-4

# Experiment 2: Different prompt temperature
dvc exp run -n "higher-temp" -S sections.valuation.temperature=0.5

# Experiment 3: More beads
dvc exp run -n "more-beads" -S sections.valuation.min_beads=15

# Show all experiments
dvc exp show --include-params sections.valuation

# Output:
# ┌─────────────────┬────────────┬───────────┬──────────┬────────────┐
# │ Experiment      │ quality    │ model     │ temp     │ min_beads  │
# ├─────────────────┼────────────┼───────────┼──────────┼────────────┤
# │ workspace       │ -          │ opus-4    │ 0.3      │ 12         │
# │ baseline        │ 0.85       │ opus-4    │ 0.3      │ 12         │
# │ try-sonnet      │ 0.82       │ sonnet-4  │ 0.3      │ 12         │
# │ higher-temp     │ 0.84       │ opus-4    │ 0.5      │ 12         │
# │ more-beads      │ 0.88       │ opus-4    │ 0.3      │ 15         │
# └─────────────────┴────────────┴───────────┴──────────┴────────────┘

# Apply best experiment
dvc exp apply more-beads

# Persist to Git
dvc exp branch more-beads experiment/more-beads
git checkout experiment/more-beads
```

### Multi-Metric Comparison

```python
# stages/aggregate_metrics.py
def aggregate_metrics(workdir):
    """
    Aggregate all section metrics into report-level metrics.
    """
    metrics = {}

    # Collect section metrics
    section_scores = []
    for section_file in glob(f"{workdir}/metrics/section_*.json"):
        data = json.load(open(section_file))
        section_scores.append(data["composite_quality"])

    # Report-level aggregations
    metrics["avg_section_quality"] = np.mean(section_scores)
    metrics["min_section_quality"] = np.min(section_scores)
    metrics["quality_std"] = np.std(section_scores)

    # Research coverage
    research_metrics = json.load(open(f"{workdir}/metrics/research_consolidated.json"))
    metrics["total_beads"] = research_metrics["total_beads"]
    metrics["avg_bead_confidence"] = research_metrics["avg_confidence"]

    # Assembly metrics
    assembly = json.load(open(f"{workdir}/metrics/assembly.json"))
    metrics["redundancy_score"] = assembly["redundancy_score"]
    metrics["coherence_score"] = assembly["coherence_score"]

    # Final report
    final = json.load(open(f"{workdir}/metrics/final.json"))
    metrics["total_word_count"] = final["word_count"]
    metrics["total_citations"] = final["citation_count"]

    return metrics
```

## Integration with External Tools

### 1. CI/CD Pipeline

```yaml
# .github/workflows/report-generation.yml
name: Generate Report

on:
  workflow_dispatch:
    inputs:
      ticker:
        description: 'Stock ticker'
        required: true
      date:
        description: 'Report date (YYYY-MM-DD)'
        required: true

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup DVC
        run: |
          pip install dvc[s3]
          dvc remote modify myremote access_key_id ${{ secrets.AWS_ACCESS_KEY }}
          dvc remote modify myremote secret_access_key ${{ secrets.AWS_SECRET_KEY }}

      - name: Setup Promptflow
        run: |
          pip install promptflow promptflow-tools

      - name: Update parameters
        run: |
          sed -i "s/ticker: .*/ticker: ${{ github.event.inputs.ticker }}/" params.yaml
          sed -i "s/date: .*/date: ${{ github.event.inputs.date }}/" params.yaml

      - name: Run pipeline
        run: |
          dvc repro -j 4

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: report-${{ github.event.inputs.ticker }}-${{ github.event.inputs.date }}
          path: work/${{ github.event.inputs.ticker }}_${{ github.event.inputs.date }}/report/

      - name: Push to DVC remote
        run: dvc push
```

### 2. Monitoring Dashboard

Use DVC Studio or custom dashboard:

```python
# dashboard/app.py
import streamlit as st
import json
from pathlib import Path

st.title("Stock Research Report Dashboard")

# Select ticker
ticker = st.selectbox("Ticker", get_available_tickers())

# Load metrics
metrics_path = f"work/{ticker}_{date}/quality_report.json"
metrics = json.load(open(metrics_path))

# Display overall quality
st.metric("Overall Quality", f"{metrics['overall_quality']:.2f}")

# Section breakdown
st.subheader("Section Quality")
sections_df = pd.DataFrame(metrics["sections"]).T
st.bar_chart(sections_df["quality_score"])

# Bead statistics
st.subheader("Research Coverage")
st.json(metrics["beads"])

# Download report
report_path = f"work/{ticker}_{date}/report/report.pdf"
with open(report_path, "rb") as f:
    st.download_button("Download Report", f, file_name=f"{ticker}_report.pdf")
```

### 3. Slack Notifications

```python
# stages/notify.py
import requests
import json

def notify_slack(ticker, date, metrics):
    """
    Send completion notification to Slack.
    """
    quality = metrics["overall_quality"]
    color = "good" if quality > 0.85 else "warning" if quality > 0.75 else "danger"

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    payload = {
        "attachments": [{
            "color": color,
            "title": f"Report Complete: {ticker}",
            "fields": [
                {"title": "Date", "value": date, "short": True},
                {"title": "Quality", "value": f"{quality:.2f}", "short": True},
                {"title": "Sections", "value": str(metrics["sections_count"]), "short": True},
                {"title": "Beads", "value": str(metrics["total_beads"]), "short": True},
            ],
            "actions": [{
                "type": "button",
                "text": "View Report",
                "url": f"https://dashboard.example.com/reports/{ticker}/{date}"
            }]
        }]
    }

    requests.post(webhook_url, json=payload)
```

## Testing Strategy

### 1. Unit Tests (Python Tools)

```python
# tests/test_beads.py
import pytest
from tools.beads import create_bead, validate_bead

def test_create_bead():
    bead = create_bead(
        type="metric",
        title="Test metric",
        content={"value": 100, "unit": "USD"},
        source={"url": "http://example.com"}
    )
    assert bead["id"].startswith("bead_")
    assert bead["type"] == "metric"
    assert validate_bead(bead).is_valid

def test_invalid_bead():
    bead = {"type": "invalid"}
    result = validate_bead(bead)
    assert not result.is_valid
    assert "missing required fields" in result.error
```

### 2. Integration Tests (DVC Stages)

```python
# tests/test_stages.py
import subprocess
import json

def test_research_stage():
    """
    Test research stage with mock data.
    """
    # Run stage with test params
    result = subprocess.run(
        ["dvc", "repro", "research_sec", "--force"],
        env={"TICKER": "TEST", "USE_MOCK_DATA": "1"}
    )
    assert result.returncode == 0

    # Validate outputs
    beads = json.load(open("work/TEST_20260115/beads/sec/index.json"))
    assert len(beads) > 0
    assert all(b["source"]["type"] == "SEC_10K" for b in beads)
```

### 3. End-to-End Tests

```bash
# tests/e2e/test_full_pipeline.sh
#!/bin/bash

# Setup test environment
export TICKER="AAPL"
export DATE="2026-01-15"
export USE_CACHE="0"

# Run full pipeline
dvc repro --force

# Validate outputs
if [ ! -f "work/AAPL_20260115/report/report.md" ]; then
    echo "Report not generated"
    exit 1
fi

# Check quality metrics
quality=$(jq '.overall_quality' work/AAPL_20260115/quality_report.json)
if (( $(echo "$quality < 0.75" | bc -l) )); then
    echo "Quality too low: $quality"
    exit 1
fi

echo "E2E test passed"
```

### 4. Promptflow Evaluation Tests

```bash
# Run evaluation on test dataset
pf run create \
  --flow flows/section_writer \
  --data tests/test_data/sections.jsonl \
  --run test_run_$(date +%s)

# Run evaluators
pf run create \
  --flow flows/section_writer/evaluate \
  --data tests/test_data/sections.jsonl \
  --column-mapping section_text='${run.outputs.section_text}' \
  --run test_eval_$(date +%s)

# Assert metrics above threshold
python tests/assert_metrics.py --run test_eval_* --min-quality 0.80
```

## Migration from v2 to v3

### Migration Steps

1. **Install Dependencies**
```bash
pip install dvc[s3] promptflow promptflow-tools
```

2. **Initialize DVC**
```bash
dvc init
```

3. **Convert Phase Scripts to DVC Stages**
```python
# Old: phases/phase1.py (monolithic)
# New: stages/research.py (modular, one per source)
```

4. **Create dvc.yaml**
Convert sequential phases to DAG stages

5. **Move Prompts to Promptflow**
```bash
mkdir -p flows/section_writer/prompts
# Move prompt templates
# Create flow.dag.yaml
```

6. **Add DVC Tracking**
```bash
dvc add work/
git add work/.dvc
```

7. **Test Pipeline**
```bash
dvc repro
```

### Backward Compatibility

Keep v2 tools interface:

```python
# tools/beads.py - Same API, DVC-aware implementation
def create_bead(bead_json: dict) -> str:
    """
    Create bead (v2 API, v3 implementation).
    DVC automatically tracks the file.
    """
    bead_id = generate_bead_id()
    bead_json["id"] = bead_id

    # Save to DVC-tracked directory
    save_path = get_bead_path(bead_id)
    with open(save_path, "w") as f:
        json.dump(bead_json, f)

    # DVC will track on next `dvc add` or stage completion
    return bead_id
```

## Summary of Improvements Over v2

### 1. **DAG-Based Execution**
- **v2**: Sequential phases (0→1→2→3→4)
- **v3**: True DAG with parallelism and dependencies
- **Benefit**: Faster execution, better resource utilization

### 2. **Reproducibility**
- **v2**: Manual checkpointing, file hashes
- **v3**: DVC automatic versioning, `dvc repro` guarantees exact reproduction
- **Benefit**: Full audit trail, experiment reproducibility

### 3. **Prompt Management**
- **v2**: YAML-defined prompts, manual versioning
- **v3**: Promptflow with visual DAG, built-in evaluation, A/B testing
- **Benefit**: Easier prompt iteration, systematic evaluation

### 4. **Caching and Incremental Execution**
- **v2**: Custom caching logic
- **v3**: DVC automatic caching based on checksums
- **Benefit**: Intelligent reruns, faster iterations

### 5. **Collaboration**
- **v2**: Shared file system
- **v3**: DVC remote storage (S3/Azure/GCS), Git for code
- **Benefit**: Team collaboration, cloud-native

### 6. **Experiment Tracking**
- **v2**: Manual comparison of runs
- **v3**: `dvc exp` with automatic metric tracking and comparison
- **Benefit**: Systematic experimentation, easy rollback

### 7. **Observability**
- **v2**: Custom logging
- **v3**: DVC metrics/plots + Promptflow monitoring
- **Benefit**: Built-in dashboards, visual metrics

### 8. **Testability**
- **v2**: Custom test infrastructure
- **v3**: Promptflow evaluation flows, DVC stage tests
- **Benefit**: Systematic quality assurance

### 9. **Scalability**
- **v2**: Limited parallelism
- **v3**: DAG-based parallel execution (`dvc repro -j N`)
- **Benefit**: Linear scaling with resources

### 10. **Standardization**
- **v2**: Custom pipeline framework
- **v3**: Industry-standard tools (DVC, Promptflow)
- **Benefit**: Ecosystem compatibility, community support

## Conclusion

This v3 design transforms the stock research agent from a custom pipeline framework into a production-grade system built on industry-standard tools:

- **DVC** provides robust data pipeline orchestration, versioning, and reproducibility
- **Promptflow** enables systematic prompt engineering, evaluation, and monitoring
- **DAG architecture** allows parallel execution and intelligent caching
- **Version control** (Git + DVC) ensures complete lineage and reproducibility
- **Experiment tracking** makes prompt iteration and model comparison systematic

The result is a system that is:
- **Faster**: Parallel execution, intelligent caching
- **More reliable**: Automatic recovery, checksumming
- **More collaborative**: Remote storage, version control
- **More observable**: Metrics, plots, monitoring
- **More testable**: Built-in evaluation, systematic testing
- **More maintainable**: Standard tools, clear interfaces

All while maintaining the core beads-first research workflow and YAML-driven configuration that made v2 effective.
