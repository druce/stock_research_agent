# Report Writer Agent Design v2

## Overview

A robust, reusable report writer agent using a beads-first research workflow. Designed for stock research reports but extensible to other research domains through YAML configuration.

Reference implementation: `~/projects/stock_research_agent`

## Core Principles

- **Single source of truth**: Beads + local files (no SQL/vector stores)
- **Provenance first**: All data traceable to original sources with links
- **Phase gating**: Clear boundaries with critic-optimizer loops
- **YAML-driven**: Report structure and prompts externalized for reusability
- **Robustness**: Error handling, validation, and recovery built-in
- **Observable**: Progress tracking, logging, and debugging support

## YAML-Driven Configuration

Report structure lives in YAML files for reusability across report types:

- `research_report.yaml`: Run-level config (ticker, template, phase ordering)
- `phase1.yaml`: Research tasks, source types, charts/tables required
- `phase2.yaml`: Section definitions, prompts, dependencies, quality thresholds
- `phase3.yaml`: Full-report critic/optimizer prompts and tasks
- `phase4.yaml`: Template rendering configuration

### New: Validation Schemas

Each YAML must include a schema version and validation rules:

```yaml
schema_version: "2.0"
validation:
  required_sections: ["company_profile", "valuation"]
  min_beads_per_section: 5
  min_section_length: 300
  max_section_length: 1500
  required_charts: ["price_chart"]
  required_tables: ["peer_comparison"]
```

## Data Model: Beads and Local Files

### Bead Types (minimal, extensible)

Core types:
- `source`: Raw content metadata (document, URL, timestamp, relevance)
- `fact`: Atomic factual statements with citations
- `metric`: Numeric values with units, period, and provenance
- `event`: Dated events with impact notes
- `quote`: Direct quotes with speaker and source
- `insight`: Analyst synthesis or interpretation (flagged as opinion)
- `table`: References to local table files with schema notes
- `chart`: References to local chart files with caption notes
- `question`: User-specific or critic-identified questions

**New relationship types:**
- `relationship`: Models connections between beads (supports, contradicts, elaborates, replaces)

### Bead Fields (extended)

Required fields:
- `id`: Unique bead identifier (format: `bead_{YYYYMMDD}_{HHMMSS}_{counter}`)
- `type`: One of the bead types above
- `title`: Short label (max 100 chars)
- `summary`: 1-2 sentences (max 300 chars)
- `content`: Structured payload or text
- `source`: Citation details and file/URL links
- `timestamp`: ISO 8601 capture time
- `tags.section`: List of outline sections (section IDs)
- `tags.topic`: Cross-cutting tags

**New fields for robustness:**
- `confidence`: Float 0.0-1.0 (not just categorical)
- `quality_score`: Float 0.0-1.0 computed from validation rules
- `freshness`: ISO 8601 date of underlying data
- `version`: Integer version for bead updates
- `supersedes`: Bead ID this version replaces (if any)
- `validated_by`: List of validation checks passed
- `relationships`: List of `{type, target_bead_id, strength}` objects
- `extraction_method`: How bead was created (llm, api, manual, computed)
- `review_status`: (unreviewed, approved, flagged, rejected)

### Bead Schema Example v2

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
    "period": "FY2023",
    "currency": "USD"
  },
  "source": {
    "type": "SEC_10K",
    "title": "Form 10-K FY2023",
    "url": "https://www.sec.gov/...",
    "file_path": "sources/sec_10k_fy2023.txt",
    "page_or_section": "Item 8",
    "retrieved_at": "2026-01-15T10:30:42Z"
  },
  "confidence": 0.95,
  "quality_score": 0.92,
  "freshness": "2023-10-31",
  "timestamp": "2026-01-15T10:30:42Z",
  "extraction_method": "llm",
  "review_status": "approved",
  "validated_by": ["schema_check", "source_verification", "unit_consistency"],
  "tags": {
    "section": ["company_profile", "financials"],
    "topic": ["revenue", "scale"]
  },
  "relationships": [
    {
      "type": "supports",
      "target_bead_id": "bead_20260115_103040_002",
      "strength": 0.8
    }
  ]
}
```

### Local Files Structure

```
WORKDIR = work/{TICKER}_{DATE}/

sources/               # Raw source documents
  ├── sec_filings/    # 10-K, 10-Q, 8-K, etc.
  ├── news/           # News articles
  ├── earnings/       # Earnings call transcripts
  ├── fundamentals/   # Financial data dumps
  └── research/       # Third-party research

tables/               # Data tables (CSV/JSON)
  ├── schema/         # Table schemas for validation
  └── [section_id]_[name].{csv,json}

charts/               # Visualizations (PNG/SVG)
  ├── metadata/       # Chart specs and captions
  └── [section_id]_[name].{png,svg}

drafts/               # Work-in-progress
  ├── sections/       # Section drafts
  ├── critiques/      # Critic feedback
  └── optimizations/  # Optimizer notes

sections/             # Final section outputs
  └── [section_id].md

beads/                # Bead storage and indexing
  ├── index.json      # Primary index
  ├── by_section/     # Section-based index
  ├── by_topic/       # Topic-based index
  ├── by_source/      # Source-based index
  ├── relationships.json  # Bead relationship graph
  └── archive/        # Superseded bead versions

cache/                # Research cache for reuse
  └── queries/        # Cached query results with TTL

logs/                 # Execution logs
  ├── phase0.log
  ├── phase1.log
  ├── phase2.log
  ├── phase3.log
  └── phase4.log

checkpoints/          # Recovery checkpoints
  ├── phase1_complete.json
  ├── phase2_complete.json
  └── phase3_complete.json

report/               # Final outputs
  ├── report.md
  ├── report.pdf
  └── report_metadata.json

outline.json          # Report outline and structure
metadata.json         # Ticker and run metadata
quality_report.json   # Quality metrics and validation results
```

### Bead Index Schema v2

Enhanced index with multiple views:

```json
{
  "version": "2.0",
  "generated_at": "2026-01-15T10:30:42Z",
  "stats": {
    "total_beads": 342,
    "by_type": {"metric": 89, "fact": 156, "event": 42, "quote": 32, "insight": 23},
    "avg_confidence": 0.84,
    "avg_quality_score": 0.81
  },
  "beads": {
    "bead_20260115_103042_001": {
      "type": "metric",
      "version": 1,
      "sections": ["company_profile", "financials"],
      "topics": ["revenue", "scale"],
      "sources": ["sources/sec_10k_fy2023.txt"],
      "confidence": 0.95,
      "quality_score": 0.92,
      "freshness": "2023-10-31",
      "review_status": "approved"
    }
  },
  "relationships": {
    "bead_20260115_103042_001": {
      "supports": ["bead_20260115_103040_002"],
      "supported_by": ["bead_20260115_103030_005"]
    }
  }
}
```

## Phase 0: Intake and Outline Confirmation

### Objectives

- Validate ticker and gather metadata
- Present and confirm report outline
- Capture custom questions and requirements
- Initialize workspace and logging

### Pseudocode

```
initialize_logger()
try:
  prompt_user_for_ticker()
  validate_ticker_or_retry()  # yfinance lookup with fallback
  fetch_metadata(ticker)  # name, sector, market cap, exchange
  save_metadata_json()

  present_standard_outline()
  confirm_or_edit_outline()  # loop until confirmed
  capture_custom_questions()
  capture_special_requirements()  # e.g., focus areas, exclusions

  save_outline_json()
  create_workspace_directories()

  # Create initial beads
  create_source_bead_for_metadata()
  create_question_beads_for_custom_questions()
  create_section_map_bead()

  save_phase0_checkpoint()
  log_phase0_complete()

except ValidationError as e:
  log_error(e)
  prompt_user_retry_or_abort()
```

### Output

- `WORKDIR/outline.json`
- `WORKDIR/metadata.json`
- `WORKDIR/beads/` with initial beads
- `WORKDIR/checkpoints/phase0_complete.json`
- `WORKDIR/logs/phase0.log`

### New: Outline Schema with Dependencies

```json
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "date": "2026-01-15",
  "report_type": "full_research",
  "sections": [
    {
      "id": "section_1",
      "title": "Section title",
      "depends_on": [],
      "min_beads": 5,
      "target_length": 500,
      "priority": "high"
    },
    {
      "id": "section_2",
      "title": "Another section",
      "depends_on": ["section_1"],
      "min_beads": 8,
      "target_length": 800,
      "priority": "medium"
    }
  ],
  "custom_questions": [
    {
      "id": "q1",
      "text": "How exposed is the company to China demand?",
      "section_id": "section_2",
      "priority": "high"
    }
  ],
  "special_requirements": {
    "focus_areas": ["competitive positioning", "margin trends"],
    "exclude_topics": [],
    "regulatory_disclaimers": true
  }
}
```

## Phase 1: Research and Capture (Beads + Files)

### Objectives

- Gather research data for all sections (parallelized where possible)
- Save raw sources with metadata
- Extract and validate beads with section tags
- Answer custom questions
- Build searchable indexes

### Enhanced Pseudocode with Error Handling

```
load_phase1_config()  # from phase1.yaml
initialize_research_cache()

# Parallel research streams
research_tasks = []
for source_type in required_sources:
  task = async_research_source(source_type, ticker)
  research_tasks.append(task)

# Execute with rate limiting and retries
results = await_all_with_rate_limit_and_retry(
  research_tasks,
  max_concurrent=5,
  rate_limit_per_minute=60,
  max_retries=3,
  exponential_backoff=True
)

# Process results and create beads
for result in results:
  if result.success:
    save_source_file(result.content, result.metadata)
    beads = extract_beads_from_source(result)
    for bead in beads:
      validate_bead_schema(bead)
      assign_confidence_score(bead)
      assign_quality_score(bead)
      tag_with_sections(bead, outline)
      detect_relationships(bead, existing_beads)
      save_bead(bead)
  else:
    log_research_failure(result.source_type, result.error)
    create_gap_marker(result.source_type)

# Handle custom questions with targeted prompts
for question in custom_questions:
  try:
    response = query_with_cache(question, cache_ttl=3600)
    save_source_file(response)
    beads = extract_beads_from_response(response, question)
    assign_beads_to_section(beads, question.section_id)
  except APIError as e:
    log_error(e)
    mark_question_incomplete(question.id)

# Detect conflicts and duplicates
detect_conflicting_beads()
deduplicate_sources()

# Build indexes
update_primary_index()
update_section_indexes()
update_topic_indexes()
update_relationship_graph()

# Validate Phase 1 completion
validate_minimum_beads_per_section(outline.sections)
generate_phase1_quality_report()

save_phase1_checkpoint()
```

### New: Research Source Configuration

In `phase1.yaml`:

```yaml
sources:
  - type: sec_filings
    priority: critical
    required_forms: [10-K, 10-Q]
    max_age_days: 365
    retry_policy:
      max_attempts: 3
      backoff: exponential

  - type: news
    priority: high
    lookback_days: 90
    min_articles: 10
    sources_preferred: [bloomberg, reuters, wsj]

  - type: fundamentals
    priority: critical
    metrics_required: [revenue, margins, fcf, debt]

  - type: earnings_transcripts
    priority: medium
    quarters: 4

validation:
  min_sources_per_type: 2
  min_total_beads: 50
  min_beads_per_section: 5
```

### New: Conflict Detection

When beads contradict:

```python
def detect_conflicting_beads():
  conflicts = []
  for metric in group_by_metric_type(beads):
    values = [b.content.value for b in metric.beads]
    if has_significant_variance(values):
      conflict = {
        "type": "metric_conflict",
        "metric": metric.name,
        "beads": metric.beads,
        "resolution_strategy": resolve_by_source_priority(metric.beads)
      }
      conflicts.append(conflict)
      log_conflict(conflict)
  return conflicts
```

### Output

- `sources/` with categorized raw sources
- `beads/` with validated beads and indexes
- `cache/` with cached query results
- `checkpoints/phase1_complete.json`
- `logs/phase1.log` with warnings about gaps or conflicts
- `quality_report.json` with Phase 1 metrics

## Phase 2: Section Writing with Critic-Optimizer

### Objectives

- Write sections in dependency order (respect `depends_on`)
- Execute one critic-optimizer loop per section
- Validate section quality before proceeding
- Track and link all citations

### Enhanced Pseudocode

```
load_phase2_config()  # section prompts, quality thresholds

# Topologically sort sections by dependencies
section_order = topological_sort(outline.sections)

for section in section_order:
  log_section_start(section.id)

  # Gather inputs
  beads = fetch_beads_by_section(section.id, min_quality=0.7)

  # Validate sufficient data
  if len(beads) < section.min_beads:
    log_warning(f"Section {section.id} has only {len(beads)} beads, minimum {section.min_beads}")
    if section.priority == "critical":
      trigger_additional_research(section.id)
      beads = fetch_beads_by_section(section.id)

  tables = fetch_tables_for_section(section.id)
  charts = fetch_charts_for_section(section.id)

  # Load section-specific prompt from phase2.yaml
  prompt_template = load_section_prompt(section.id)

  # Write draft
  try:
    draft = write_section(
      section=section,
      beads=beads,
      tables=tables,
      charts=charts,
      prompt=prompt_template,
      target_length=section.target_length
    )
    save_draft(section.id, draft, version="v1")

    # Critic review
    critique = run_critic(
      section=section,
      draft=draft,
      beads=beads,
      outline=outline
    )
    save_critique(section.id, critique)

    # Optimizer revision
    revised = run_optimizer(
      section=section,
      draft=draft,
      critique=critique,
      beads=beads
    )
    save_draft(section.id, revised, version="v2")

    # Validate quality
    quality = validate_section_quality(revised, section)
    if quality.score < section.quality_threshold:
      log_warning(f"Section {section.id} quality {quality.score} below threshold")
      if section.priority == "critical":
        # Optional: trigger manual review or additional iteration
        pass

    # Save final section
    save_section(section.id, revised)
    update_citations_map(section.id, revised.citations)

  except Exception as e:
    log_error(f"Section {section.id} failed: {e}")
    save_error_marker(section.id, str(e))
    if section.priority == "critical":
      raise  # Cannot proceed without critical section
    else:
      continue  # Skip non-critical section

save_phase2_checkpoint()
generate_phase2_quality_report()
```

### New: Section Quality Validation

```python
def validate_section_quality(section_text, section_spec):
  metrics = {
    "length": len(section_text.split()),
    "citations_count": count_citations(section_text),
    "unique_sources": count_unique_sources(section_text),
    "readability": compute_readability_score(section_text),
    "completeness": check_required_elements(section_text, section_spec),
    "factual_density": count_facts_per_paragraph(section_text)
  }

  # Weighted composite score
  score = (
    0.2 * min(1.0, metrics["citations_count"] / 10) +
    0.2 * min(1.0, metrics["unique_sources"] / 5) +
    0.3 * metrics["completeness"] +
    0.2 * metrics["readability"] +
    0.1 * min(1.0, metrics["factual_density"] / 3)
  )

  return QualityReport(score=score, metrics=metrics)
```

### New: Cross-Reference Management

Track citations across sections:

```json
{
  "citations_map": {
    "section_1": {
      "beads_used": ["bead_001", "bead_005", "bead_012"],
      "sources_used": ["sources/sec_10k_fy2023.txt", "sources/news_20260110.txt"]
    },
    "section_2": {
      "beads_used": ["bead_001", "bead_015"],
      "sources_used": ["sources/sec_10k_fy2023.txt"]
    }
  },
  "bead_usage_count": {
    "bead_001": 2,
    "bead_005": 1
  }
}
```

### Output

- `drafts/sections/` with v1 and v2 drafts
- `drafts/critiques/` with critic feedback
- `sections/` with final section text
- `citations_map.json`
- `checkpoints/phase2_complete.json`
- `logs/phase2.log`

## Phase 3: Report Assembly and Global Critic

### Objectives

- Concatenate sections with transitions
- Run full-report critic for redundancy and coherence
- Execute optimizer to polish final text
- Validate global quality metrics

### Enhanced Pseudocode

```
# Assemble sections in order
full_text = ""
for section in section_order:
  section_text = load_section(section.id)
  full_text += f"\n\n## {section.title}\n\n{section_text}"

save_draft("full_report", full_text, version="v1")

# Global critique
global_critique = run_full_report_critic(
  text=full_text,
  outline=outline,
  check_for=[
    "redundancy_across_sections",
    "contradictions",
    "tone_consistency",
    "logical_flow",
    "citation_completeness"
  ]
)
save_critique("full_report", global_critique)

# Global optimization
optimized_text = run_full_report_optimizer(
  text=full_text,
  critique=global_critique,
  goals=[
    "remove_redundancy",
    "improve_transitions",
    "normalize_tone",
    "strengthen_conclusion"
  ]
)
save_draft("full_report", optimized_text, version="v2")

# Validate final quality
final_quality = validate_report_quality(optimized_text, outline)
log_final_quality_metrics(final_quality)

save_file("drafts/report_body.md", optimized_text)
save_phase3_checkpoint()
```

### Output

- `drafts/report_body.md`
- `drafts/critiques/full_report_critique.json`
- `quality_report.json` updated with Phase 3 metrics
- `checkpoints/phase3_complete.json`
- `logs/phase3.log`

## Phase 4: Template Rendering and Export

### Objectives

- Render final report through Jinja2 template
- Embed charts and tables
- Generate table of contents and citations
- Export to multiple formats (MD, PDF, HTML)
- Add regulatory disclaimers if required

### Enhanced Pseudocode

```
load_phase4_config()  # template path, export formats

# Gather all components
report_body = load_file("drafts/report_body.md")
metadata = load_metadata()
outline = load_outline()
charts = load_all_charts_with_metadata()
tables = load_all_tables_with_metadata()
citations = build_citations_list_from_beads()

# Build template context
context = {
  "metadata": metadata,
  "outline": outline,
  "report_body": report_body,
  "charts": charts,
  "tables": tables,
  "citations": citations,
  "generated_date": now_iso8601(),
  "disclaimers": get_regulatory_disclaimers() if outline.special_requirements.regulatory_disclaimers
}

# Load and render template
template = load_jinja2_template(phase4_config.template_path)
rendered_md = template.render(context)
save_file("report/report.md", rendered_md)

# Export to additional formats
if "pdf" in phase4_config.export_formats:
  export_to_pdf("report/report.md", "report/report.pdf")

if "html" in phase4_config.export_formats:
  export_to_html("report/report.md", "report/report.html")

# Generate metadata file
report_metadata = {
  "ticker": metadata.ticker,
  "generated_at": context.generated_date,
  "total_beads_used": count_total_beads_used(),
  "total_sources": count_unique_sources(),
  "quality_score": load_final_quality_score(),
  "sections_count": len(outline.sections),
  "word_count": count_words(rendered_md)
}
save_file("report/report_metadata.json", report_metadata)

save_phase4_checkpoint()
log_phase4_complete()
```

### Output

- `report/report.md`
- `report/report.pdf` (optional)
- `report/report_html` (optional)
- `report/report_metadata.json`
- `checkpoints/phase4_complete.json`
- `logs/phase4.log`

## Tool Surface (Function Signatures)

### Bead Tools

```python
# Core operations
beads.create(bead_json: dict) -> str  # returns bead_id
beads.update(bead_id: str, patch_json: dict) -> str
beads.get(bead_id: str) -> dict
beads.delete(bead_id: str) -> bool  # soft delete, moves to archive
beads.supersede(old_bead_id: str, new_bead_json: dict) -> str

# Search and filter
beads.search(filters: dict) -> list[dict]
  # filters: {"section": "valuation", "type": "metric", "topic": "margin",
  #           "min_confidence": 0.8, "min_quality": 0.7, "review_status": "approved"}

beads.search_related(bead_id: str, relationship_type: str = None) -> list[dict]
  # relationship_type: "supports", "contradicts", "elaborates", "replaces"

# Indexing
beads.rebuild_index() -> str  # returns index_path
beads.get_index_stats() -> dict

# Validation
beads.validate_schema(bead_json: dict) -> ValidationResult
beads.compute_quality_score(bead_json: dict) -> float

# Relationships
beads.add_relationship(source_id: str, target_id: str, rel_type: str, strength: float = 1.0) -> bool
beads.get_relationship_graph() -> dict

# Conflict detection
beads.detect_conflicts(scope: str = "all") -> list[dict]  # scope: "all", "section", "topic"
beads.resolve_conflict(conflict_id: str, resolution: dict) -> bool
```

### File Tools

```python
files.read(path: str) -> str
files.write(path: str, content: str) -> str
files.list(dir_path: str, pattern: str = "*") -> list[str]
files.copy(src: str, dst: str) -> str
files.delete(path: str) -> bool
files.exists(path: str) -> bool
files.get_metadata(path: str) -> dict  # size, modified_time, hash
```

### Research Tools (Phase 1 only)

```python
# Web search
web.search(query: str, max_results: int = 10) -> dict
web.fetch(url: str, cache_ttl: int = 3600) -> str

# LLM queries
perplexity.query(prompt: str, cache_ttl: int = 3600) -> str

# Financial data
sec.fetch(ticker: str, form_type: str, lookback_days: int = 365) -> list[str]
sec.search_filings(ticker: str, keywords: list[str]) -> list[dict]

marketdata.fetch(ticker: str, fields: list[str]) -> dict
marketdata.get_peers(ticker: str, count: int = 10) -> list[str]
marketdata.get_fundamentals(ticker: str, periods: int = 8) -> dict

# News and transcripts
news.fetch(ticker: str, lookback_days: int = 90, min_relevance: float = 0.7) -> list[dict]
transcripts.fetch(ticker: str, quarters: int = 4) -> list[str]

# Caching
cache.get(key: str) -> str | None
cache.set(key: str, value: str, ttl: int) -> bool
cache.clear(pattern: str = "*") -> int
```

### Reporting Tools

```python
# Tables
tables.build(data: dict, output_path: str, schema: dict = None) -> str
tables.validate(path: str, schema: dict) -> ValidationResult
tables.to_markdown(path: str) -> str

# Charts
charts.render(spec: dict, output_path: str) -> str
  # spec: {"type": "line", "data": [...], "options": {...}}
charts.embed_metadata(path: str, metadata: dict) -> str

# Templates
templates.render(template_path: str, context: dict, output_path: str) -> str
templates.validate(template_path: str) -> ValidationResult

# Export
export.to_pdf(md_path: str, output_path: str, options: dict = None) -> str
export.to_html(md_path: str, output_path: str, options: dict = None) -> str
```

### Quality and Validation Tools

```python
quality.validate_bead(bead: dict) -> ValidationResult
quality.validate_section(text: str, spec: dict) -> ValidationResult
quality.compute_bead_quality_score(bead: dict) -> float
quality.compute_section_quality_score(text: str, spec: dict) -> float
quality.generate_quality_report(phase: str) -> dict
```

### Checkpoint and Recovery Tools

```python
checkpoint.save(phase: str, data: dict) -> str
checkpoint.load(phase: str) -> dict
checkpoint.exists(phase: str) -> bool
checkpoint.list_all() -> list[str]

recovery.resume_from_phase(phase: str) -> dict  # returns phase state
recovery.rollback_to_phase(phase: str) -> bool
```

### Logging and Monitoring Tools

```python
log.info(message: str, context: dict = None)
log.warning(message: str, context: dict = None)
log.error(message: str, context: dict = None, exception: Exception = None)
log.debug(message: str, context: dict = None)

monitor.track_progress(phase: str, step: str, percent_complete: float)
monitor.get_progress() -> dict
monitor.estimate_time_remaining() -> int  # seconds
```

## Error Handling and Recovery Strategies

### API Failures and Rate Limits

```python
@retry_with_exponential_backoff(max_attempts=3, base_delay=1.0)
@rate_limit(max_calls_per_minute=60)
def fetch_with_resilience(url):
  try:
    response = fetch(url)
    return response
  except RateLimitError as e:
    log.warning(f"Rate limit hit: {e}, backing off...")
    raise  # Will be retried by decorator
  except NetworkError as e:
    log.error(f"Network error: {e}")
    return fallback_source() if has_fallback() else None
```

### Source Unavailability

- Use cached results if available and not stale
- Try alternative sources for the same data
- Mark data gap in beads index
- Continue with degraded data if section is non-critical
- Alert user if critical data missing

### Conflict Resolution

When beads contradict:
1. Score sources by priority (SEC filings > earnings transcripts > news > third-party)
2. Use most recent data if temporal
3. Flag conflict in quality report
4. Let critic/optimizer address in narrative

### Mid-Phase Crashes

```python
def resume_from_checkpoint():
  last_checkpoint = get_latest_checkpoint()
  if last_checkpoint:
    log.info(f"Resuming from {last_checkpoint.phase}")
    state = checkpoint.load(last_checkpoint.phase)
    return continue_from_state(state, last_checkpoint.phase)
  else:
    log.info("No checkpoint found, starting from Phase 0")
    return run_phase0()
```

## Quality Metrics and Reporting

### Bead-Level Metrics

- `confidence`: Source quality and extraction accuracy (0.0-1.0)
- `quality_score`: Schema compliance, completeness, and validation (0.0-1.0)
- `freshness_score`: Decay function based on data age
- `validation_pass_rate`: Percentage of validation checks passed

### Section-Level Metrics

- `completeness`: Required elements present (0.0-1.0)
- `citation_density`: Citations per paragraph
- `source_diversity`: Unique sources used
- `readability_score`: Flesch-Kincaid or similar
- `length_adherence`: How close to target length

### Report-Level Metrics

- `overall_quality_score`: Weighted average of section scores
- `total_beads_used`: Count and breakdown by type
- `source_coverage`: Percentage of required sources obtained
- `conflict_rate`: Percentage of beads involved in conflicts
- `validation_pass_rate`: Overall validation success rate

### Quality Report Example

```json
{
  "phase": "phase2_complete",
  "timestamp": "2026-01-15T14:23:45Z",
  "overall_quality": 0.87,
  "sections": {
    "company_profile": {
      "quality_score": 0.92,
      "completeness": 0.95,
      "citation_density": 2.3,
      "source_diversity": 8,
      "length": 823,
      "warnings": []
    },
    "valuation": {
      "quality_score": 0.79,
      "completeness": 0.85,
      "citation_density": 1.8,
      "source_diversity": 5,
      "length": 645,
      "warnings": ["Below minimum citations threshold"]
    }
  },
  "beads": {
    "total": 342,
    "avg_confidence": 0.84,
    "avg_quality": 0.81,
    "conflicts_detected": 3,
    "conflicts_resolved": 2
  },
  "sources": {
    "required": 15,
    "obtained": 14,
    "missing": ["competitor_research"]
  },
  "recommendations": [
    "Consider additional research for valuation section",
    "Resolve remaining bead conflict in financials"
  ]
}
```

## Advanced Features

### Parallel Processing

Phase 1 research can parallelize:
```python
# Execute multiple research streams concurrently
async def parallel_research():
  tasks = [
    fetch_sec_filings(ticker),
    fetch_news(ticker),
    fetch_fundamentals(ticker),
    fetch_transcripts(ticker)
  ]
  results = await asyncio.gather(*tasks, return_exceptions=True)
  return [r for r in results if not isinstance(r, Exception)]
```

Phase 2 can parallelize independent sections:
```python
# Identify sections with no dependencies
independent_sections = [s for s in sections if not s.depends_on]
# Write them in parallel
results = parallel_map(write_section, independent_sections, max_workers=3)
```

### Incremental Updates

For report refreshes:
```python
def incremental_update(ticker, existing_report_dir):
  # Reuse cached research if fresh enough
  cached_beads = load_beads(existing_report_dir)
  fresh_beads = [b for b in cached_beads if is_fresh(b, max_age_days=7)]

  # Only re-fetch stale sources
  stale_sources = identify_stale_sources(fresh_beads)
  new_beads = fetch_and_extract(stale_sources)

  # Merge and update only affected sections
  merged_beads = merge_beads(fresh_beads, new_beads)
  affected_sections = identify_affected_sections(new_beads)
  rewrite_sections(affected_sections, merged_beads)
```

### Multi-Ticker Comparative Reports

Extension for peer comparisons:
```python
def comparative_report(tickers: list[str]):
  # Run Phase 0-1 for each ticker in parallel
  ticker_data = parallel_map(run_phase0_and_phase1, tickers)

  # Build comparative beads
  comp_beads = build_comparative_beads(ticker_data)

  # Use comparative outline and prompts
  outline = load_outline("comparative_report.yaml")
  sections = write_comparative_sections(comp_beads, outline)
```

### Dynamic Outline Adjustment

After Phase 1, adjust outline based on findings:
```python
def adjust_outline_post_research(outline, beads):
  # Identify topics with rich data that merit sections
  topic_coverage = analyze_topic_coverage(beads)
  high_coverage_topics = [t for t, count in topic_coverage.items() if count > 20]

  # Suggest additional sections
  suggested_sections = []
  for topic in high_coverage_topics:
    if topic not in outline.section_topics:
      suggested_sections.append(create_section_spec(topic))

  if suggested_sections:
    present_suggestions_to_user(suggested_sections)
    if user_approves():
      outline.sections.extend(suggested_sections)
      save_outline(outline)
```

## Testing and Validation Strategies

### Unit Testing

- Test bead schema validation
- Test conflict detection algorithms
- Test quality score computation
- Test search and filter logic

### Integration Testing

- Test full Phase 1 with mock APIs
- Test section writing with sample beads
- Test template rendering with sample data

### End-to-End Testing

- Test full workflow with known ticker
- Validate output quality against benchmarks
- Test recovery from simulated failures

### Validation Modes

- `--dry-run`: Execute without writing files, report what would happen
- `--validate-only`: Check all schemas and configs, don't execute
- `--debug-mode`: Verbose logging, save intermediate outputs

## Observability and Debugging

### Progress Tracking

Real-time progress display:
```
Phase 1: Research and Capture [=====>           ] 35% (ETA: 8 min)
  ├─ SEC filings    [==========>] 100% ✓
  ├─ News articles  [======>    ] 60% ...
  ├─ Fundamentals   [=====>     ] 50% ...
  └─ Transcripts    [=>         ] 10% ...
```

### Structured Logging

```json
{
  "timestamp": "2026-01-15T10:30:42Z",
  "level": "INFO",
  "phase": "phase1",
  "step": "fetch_sec_filings",
  "ticker": "AAPL",
  "message": "Retrieved 10-K for FY2023",
  "metadata": {
    "form_type": "10-K",
    "filing_date": "2023-10-31",
    "size_bytes": 2456789
  }
}
```

### Debugging Tools

- `debug.dump_beads_for_section(section_id)`: Export beads to readable format
- `debug.visualize_relationship_graph()`: Generate graph visualization
- `debug.compare_drafts(version1, version2)`: Show diff of section versions
- `debug.trace_citation(bead_id)`: Show full provenance chain

## Configuration Examples

### phase1.yaml (Extended)

```yaml
schema_version: "2.0"

sources:
  sec_filings:
    priority: critical
    required_forms: [10-K, 10-Q]
    max_age_days: 365
    retry_policy:
      max_attempts: 3
      backoff: exponential
      initial_delay: 1.0

  news:
    priority: high
    lookback_days: 90
    min_articles: 10
    sources_preferred: [bloomberg, reuters, wsj]
    min_relevance: 0.7

  fundamentals:
    priority: critical
    metrics_required:
      - revenue
      - operating_margin
      - fcf
      - debt_to_equity
      - roic
    periods: 8

  earnings_transcripts:
    priority: medium
    quarters: 4

research_strategies:
  parallel_execution: true
  max_concurrent: 5
  rate_limit_per_minute: 60
  cache_ttl: 3600

validation:
  min_sources_per_type: 2
  min_total_beads: 50
  min_beads_per_section: 5
  min_confidence: 0.7
  required_bead_types: [source, fact, metric]

quality_thresholds:
  min_avg_confidence: 0.75
  min_avg_quality: 0.70
  max_conflict_rate: 0.05
```

### phase2.yaml (Extended)

```yaml
schema_version: "2.0"

sections:
  company_profile:
    prompt_template: "templates/section_company_profile.txt"
    target_length: 600
    min_beads: 8
    quality_threshold: 0.80
    depends_on: []
    priority: high

  valuation:
    prompt_template: "templates/section_valuation.txt"
    target_length: 800
    min_beads: 12
    quality_threshold: 0.85
    depends_on: [company_profile, financials]
    priority: critical

critic_config:
  model: "claude-opus-4"
  check_for:
    - missing_questions
    - unsupported_assertions
    - clarity_issues
    - contradictions
    - redundancy_with_other_sections

optimizer_config:
  model: "claude-opus-4"
  max_iterations: 1
  goals:
    - address_critic_gaps
    - improve_flow
    - normalize_tone
    - ensure_citations

quality_validation:
  min_citations_per_section: 5
  min_unique_sources_per_section: 3
  max_section_length: 1500
  min_section_length: 300
```

## Regulatory Compliance Features

### Disclaimers and Disclosures

Auto-insert required disclaimers:
```markdown
## Disclaimers

This report is for informational purposes only and does not constitute investment advice or a recommendation to buy or sell any security. The information contained herein is based on sources believed to be reliable but is not guaranteed to be accurate or complete.

**Forward-Looking Statements**: This report may contain forward-looking statements that involve risks and uncertainties. Actual results may differ materially from those expressed or implied.

**Conflicts of Interest**: [Auto-populated based on configuration]

**Data Sources**: All data and analysis are based on publicly available information as of [date].
```

### Audit Trail

Maintain complete audit trail:
```json
{
  "report_id": "AAPL_20260115",
  "generated_by": "agent_v2",
  "timestamp": "2026-01-15T14:23:45Z",
  "beads_used": [
    {
      "bead_id": "bead_001",
      "used_in_sections": ["company_profile", "valuation"],
      "source_url": "https://www.sec.gov/...",
      "retrieved_at": "2026-01-15T10:30:42Z"
    }
  ],
  "models_used": {
    "research": "claude-sonnet-4",
    "writing": "claude-opus-4",
    "critic": "claude-opus-4"
  },
  "human_review": {
    "reviewed": false,
    "reviewer": null,
    "review_date": null
  }
}
```

## Summary of Improvements Over v1

1. **Robustness**: Error handling, retries, fallbacks, recovery checkpoints
2. **Quality**: Validation schemas, quality metrics, conflict detection
3. **Performance**: Parallelization, caching, incremental updates
4. **Relationships**: Bead relationship graph, cross-reference tracking
5. **Observability**: Progress tracking, structured logging, debugging tools
6. **Extensibility**: Multi-ticker support, dynamic outlines, sub-sections
7. **Compliance**: Disclaimers, audit trails, source verification
8. **Testing**: Validation modes, testing strategies, quality benchmarks

This design maintains the simplicity of beads + files while adding the robustness needed for production use.
