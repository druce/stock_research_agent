# Report Writer Agent Design

## Beads-First Research Workflow 

Create a reusable report writer flow. Use ~/projects/stock_research_agent directory as a reference (previously created implementation).

## Goals and Constraints

- Single source of truth: beads + local files.
- No SQL, knowledge graph, or vector store.
- Clear phase gating with one critic-optimizer loop per section, and for the final text.
- Output assembled through Jinja2 templates with charts/tables.
- All data must have provenance and be traceable to original sources, with links.

## YAML-Driven Report Definitions

Report structure, section prompts, and phase task graphs live in YAML so the agent can be reused for different report formats without changing this design doc.

- `research_report.yaml`: run-level config (ticker, template, and phase file order).
- `phase1.yaml`: research and capture tasks, plus required charts/tables.
- `phase2.yaml`: section definitions and per-section prompt additions.
- `phase3.yaml`: full-report critic/optimizer prompts and tasks.
- `phase4.yaml`: final template rendering task.

## Data Model: Beads and Local Files

### Bead Types (minimal, extensible)

- `source`: raw content metadata (document, URL, timestamp, section relevance).
- `fact`: atomic factual statements with citations.
- `metric`: numeric values with units, period, and provenance.
- `event`: dated events with impact notes.
- `quote`: direct quotes with speaker and source.
- `insight`: analyst synthesis or interpretation (flagged as opinion).
- `table`: references to local table files with schema notes.
- `chart`: references to local chart files with caption notes.
- `question`: user-specific or critic-identified questions.

### Bead Fields (suggested)

- `id`: unique bead identifier.
- `type`: one of the bead types above.
- `title`: short label.
- `summary`: 1-2 sentences.
- `content`: structured payload or text.
- `source`: citation details and file/URL links.
- `confidence`: numeric or categorical confidence.
- `timestamp`: capture time and document date if available.
- `tags.section`: list of outline sections the bead is relevant to.
- `tags.topic`: cross-cutting tags (e.g., "competition", "valuation").

### Local Files

These will be created in current work directory which will be work/{ticker}\_{date} , e.g. work/MSFT_20260115 

- `sources/`: raw text or PDFs converted to text.
- `tables/`: CSV/JSON tables for metrics, comps, financials.
- `charts/`: images and metadata for visuals.
- `drafts/`: section drafts, critic notes, optimizer notes.
- `sections/`: final section outputs.
- `beads/index.json`: directory of bead IDs, section tags, and source paths.

### Section Relevance Tagging

- Every bead gets `tags.section` with one or more outline section IDs.
- A separate `outline.json` maps section IDs to titles and question lists.
- Use a "section map" bead that stores the outline and any custom sections.

## Phase 0: Intake and Outline Confirmation

### Objectives

- Validate ticker.
- Show standard outline. ask user to confirm or paste an edited version.
- Ask user if there are any specific research questions to investigate.

### Pseudocode

- prompt user for ticker
- validate ticker (yfinance profile lookup)
- fetch basic company info (name, sectors, market cap, any other basic identifying information), save in work as metadata.json
- present standard outline
- ask for custom sections and research questions
- update outline until confirmed
- save `outline.json`
- create beads:
  - `source` bead for ticker validation info
  - `question` beads for each custom question
  - `section map` bead for the final outline

### Output
WORKDIR = work/{TICKER}\_{DATE}
- `WORKDIR/outline.json`
- `WORKDIR/metadata.json`
- `WORKDIR/beads/` with section map and question beads

## Phase 1: Research and Capture (Beads + Files)

### Objectives

- Gather broad research data for all sections.
- Save raw sources to local files.
- Create beads with section tags.
- Answer custom questions via targeted prompts.

### Pseudocode

- for each evergreen source
  - identify required source categories (filings, news, fundamentals, comps)
  - collect sources and save to `sources/`
  - extract facts, metrics, events, and quotes into beads
  - tag beads with `tags.section`
- for each user question
  - send targeted prompt to Perplexity or equivalent
  - save raw response in `sources/`
  - create a `question` bead and `fact`/`insight` beads from the response
  - assign each bead to the best-fitting outline section

### Bead/Source Indexing

- update `beads/index.json` with:
  - bead ID
  - type
  - section tags
  - source file paths or URLs

## Phase 2: Section Writing with Critic-Optimizer

### Objectives

- Write each section using Claude agent SDK and bead tools.
- One critic-optimizer iteration per section.
- Provide links to original sources.

### Prompt Templates

Section writer, critic, and optimizer prompts live in `phase2.yaml` to keep report-specific wording out of this design doc.

### Pseudocode

- for each section in outline order
  - fetch beads by `tags.section`
  - write section draft
  - run critic
  - revise once using critic feedback
  - save draft and critique to `drafts/`
  - save final section to `sections/`

## Phase 3: Report Assembly and Global Critic

### Objectives

- Assemble all sections into a single report body.
- Run critic-optimizer pass on the full report.
- Reduce redundancy and normalize tone.

### Pseudocode

- concatenate sections in outline order
- run full-report critic
- run optimizer to:
  - remove redundancy
  - enforce professional analyst style
  - ensure section transitions
- save final body text to `drafts/report_body.md`

## Phase 4: Jinja2 Template Rendering

### Objectives

- Produce final report with charts, tables, and metadata.
- Ensure templated sections and appendix content are consistent.

### Pseudocode

- load Jinja2 template
- pass in:
  - report metadata
  - section text
  - charts/tables references
  - citations list
- render final report to `report/report.md`
- optionally export PDF or other formats

## Tooling and Agent Access

### Research Phase Tools

- web search and fetch
- financial data providers
- filings retrieval
- perplexity query tool
- file read/write
- beads create/update/search

### Writing Phase Tools

- beads search and fetch by section tag or ID
- file read for tables/charts
- file write for drafts/sections

### Synthesis Phase Tools

- file read/write
- beads search for global consistency checks

## Report Structure and Assets

- Default sections, required charts, and required tables live in the YAML configs (see `phase1.yaml` and `phase2.yaml`).
- Each chart/table should have a bead that references the file path and caption.
- Use a consistent naming scheme: `charts/{section_id}_{name}.png`, `tables/{section_id}_{name}.csv`.

## Bead Schema and Index Examples

### Bead JSON (example)

```
{
  "id": "bead_20260114_000123",
  "type": "metric",
  "title": "FY2023 revenue",
  "summary": "Company revenue for FY2023.",
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
    "page_or_section": "Item 8"
  },
  "confidence": 0.92,
  "timestamp": "2026-01-14T10:15:02Z",
  "tags": {
    "section": ["company_profile", "financials"],
    "topic": ["revenue", "scale"]
  }
}
```

### Bead Index (example)

```
{
  "bead_20260114_000123": {
    "type": "metric",
    "sections": ["company_profile", "financials"],
    "topics": ["revenue", "scale"],
    "sources": ["sources/sec_10k_fy2023.txt"]
  },
  "bead_20260114_000456": {
    "type": "event",
    "sections": ["recent_developments", "risks"],
    "topics": ["regulatory", "litigation"],
    "sources": ["sources/news_20260110_regulatory.txt"]
  }
}
```

## Tool Surface (Function Signatures)

### Bead Tools

- `beads.create(bead_json) -> bead_id`
- `beads.update(bead_id, patch_json) -> bead_id`
- `beads.get(bead_id) -> bead_json`
- `beads.search(filters_json) -> [bead_json]`
  - filters: `{"section": "valuation", "type": "metric", "topic": "margin"}`
- `beads.index(list_of_beads) -> index_path`

### File Tools

- `files.read(path) -> text`
- `files.write(path, text) -> path`
- `files.list(dir_path) -> [path]`

### Research Tools (Phase 1 only)

- `web.search(query) -> results_json`
- `web.fetch(url) -> text`
- `perplexity.query(prompt) -> response_text`
- `sec.fetch(ticker, form_type) -> text`
- `marketdata.fetch(ticker, fields) -> json`

### Reporting Tools

- `tables.build(data_json, output_path) -> output_path`
- `charts.render(chart_spec_json, output_path) -> output_path`
- `templates.render(template_path, context_json, output_path) -> output_path`

## Outline Schema and Section ID Map

### outline.json (example)

```
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "date": "2026-01-14",
  "sections": [
    {"id": "section_1", "title": "Section title"},
    {"id": "section_2", "title": "Another section title"}
  ],
  "custom_questions": [
    {"id": "q1", "text": "How exposed is the company to China demand?", "section_id": "section_2"}
  ]
}
```

## Orchestration Pseudocode (Phase Gating)

- initialize run context (ticker, date, work directory)
- Phase 0:
  - validate ticker
  - build outline.json
  - create section map bead and question beads
- Phase 1:
  - for each section in outline
    - collect sources
    - save to sources/
    - extract beads with section tags
  - for each custom question
    - query research tool
    - save response to sources/
    - create question/answer beads tagged to section
  - update beads index
- Phase 2:
  - for each section in outline order
    - gather beads by section tag
    - write section draft
    - run critic
    - run optimizer once
    - save drafts and final section
- Phase 3:
  - assemble section text into full body
  - run full-report critic
  - run optimizer to reduce redundancy and align tone
  - save report body
- Phase 4:
  - render Jinja2 template with sections, charts, tables, citations
  - export final report artifacts
