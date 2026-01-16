# Stock Research Agent Design

## Beads-First Stock Research Workflow 

Create a new stock research agent flow. use ~/projects/stock_research_agent directory as a reference (previously created implementation).

## Goals and Constraints

- Single source of truth: beads + local files.
- No SQL, knowledge graph, or vector store.
- Clear phase gating with one critic-optimizer loop per section, and for the final text.
- Output assembled through Jinja2 templates with charts/tables.
- All data must have provenance and be traceable to original sources, with links.

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

### Section Writer Prompt Template

- role: professional equity research analyst
- inputs: section outline, relevant beads (by section tag), tables/charts list
- requirements:
  - incorporate cited facts and metrics
  - include relevant charts/tables with captions
  - maintain analyst tone
  - note unanswered questions or data gaps
  - target 300-1000 words (soft limit)
- output:
  - section text
  - list of bead IDs and file paths used

### Section Writer Prompt (Ready-to-Run)

```
You are a professional equity research analyst. Write the report section below using ONLY the provided beads and local files. Do not invent facts.

Section:
- id: {section_id}
- title: {section_title}
- outline: {section_outline}

Inputs:
- relevant beads: {beads_json}
- tables/charts: {tables_and_charts_list}

Requirements:
- Target 300-1000 words (soft limit).
- Use cited facts/metrics from beads; cite bead IDs inline like [bead:1234].
- Mention any unanswered questions or data gaps at the end of the section.
- If a chart/table is listed, reference it with a caption placeholder.
- Maintain professional analyst tone; no marketing language.

Output format:
1) section_text
2) citations_used: [bead_id,...]
3) files_used: [file_path,...]
```

## Section-Specific Prompt Variants

Use the general Section Writer Prompt and add one of the following per section.

### 1) Short Summary / Overall Assessment

Add:
- Provide a concise thesis, key positives/negatives, and a 3-5 bullet takeaway list.
- Reference only the most material beads (no deep dives).

### 2) Company Profile

Add:
- Cover founding, milestones, segments, and geographic mix.
- Include a short timeline of major events.

### 3) Business Model

Add:
- Explain revenue streams, pricing, distribution, and customer segments.
- Describe any switching costs or network effects with evidence.

### 4) Competitive Landscape

Add:
- Identify direct, adjacent, and emerging competitors.
- Compare differentiation, pricing power, and innovation pace.

### 5) Supply Chain Positioning

Add:
- Analyze upstream suppliers and downstream channels.
- Highlight concentration risks and mitigation.

### 6) Financial and Operating Leverage

Add:
- Quantify leverage, coverage, and margin sensitivity.
- Call out fixed vs variable cost structure.

### 7) Valuation

Add:
- Summarize primary valuation methods used and assumptions.
- Include peer multiple comparisons and sensitivity notes.

### 8) Recent Developments and Risk Factors

Add:
- Separate near-term developments from structural risks.
- Rate materiality (low/medium/high) for each risk.

### 9) SWOT Analysis, Bull and Bear Case

Add:
- Provide SWOT grid format.
- Present bull/base/bear cases with key triggers.

### 10) Overall Assessment and Watch Points

Add:
- Provide watch points with specific metrics/events to track.
- State a clear recommendation stance and confidence.

### Critic Prompt Template

- role: critical reviewer
- check:
  - missing questions or data
  - unsupported assertions
  - clarity and structure
  - contradictions or redundancy with other sections
- output:
  - targeted gaps and questions
  - recommended fixes

### Critic Prompt (Ready-to-Run)

```
You are a critical reviewer of an equity research report section.
Review the draft below and identify gaps, weak evidence, and unanswered questions.

Inputs:
- section: {section_id} {section_title}
- outline: {section_outline}
- draft: {section_text}
- beads_used: {beads_used}

Return:
1) gaps: list of missing items or thinly supported claims
2) unanswered_questions: list of questions the section raises
3) redundancy_risks: overlaps with other sections to avoid
4) fixes: actionable edits or data needed
```

### Optimizer Prompt Template

- role: editor/analyst
- fix:
  - address critic gaps
  - add missing data from beads/files
  - refine tone and structure
  - rewrite to fit 300-1000 words (soft limit, no hard cutoff)
- output:
  - revised section
  - updated citations

### Optimizer Prompt (Ready-to-Run)

```
You are the editor-analyst improving the section based on the critic feedback.

Inputs:
- section: {section_id} {section_title}
- outline: {section_outline}
- draft: {section_text}
- critic: {critic_output}
- beads_available: {beads_json}

Requirements:
- Address critic gaps using available beads/files only.
- Rewrite to 300-1000 words (soft limit; do not hard-truncate).
- Reduce redundancy with other sections where noted.
- Keep analyst tone and clear structure.
- Cite beads inline like [bead:1234].

Output format:
1) revised_section_text
2) citations_used: [bead_id,...]
3) files_used: [file_path,...]
```

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

## Outline Sections (Default)

1. Short summary / overall assessment
2. Stock chart, technicals, comparison vs peers, sankey of income statement
3. Company profile
4. Business model
5. Competitive landscape
6. Supply chain positioning
7. Financial and operating leverage
8. Valuation
9. Recent developments and risk factors
10. SWOT analysis, bull and bear case
11. Overall assessment and watch points

## Notes on Chart and Table Handling

- Each chart/table should have a bead that references the file path and caption.
- Use a consistent naming scheme: `charts/{section_id}_{name}.png`, `tables/{section_id}_{name}.csv`.
- Required visuals:
  - Price chart
  - Income statement sankey
- Required tables:
  - Technical levels table
  - Peer ratios/fundamentals comparison table

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
    {"id": "summary", "title": "Short summary / overall assessment"},
    {"id": "technicals", "title": "Stock chart, technicals, comparison vs peers, sankey of income statement"},
    {"id": "company_profile", "title": "Company profile"},
    {"id": "business_model", "title": "Business model"},
    {"id": "competitive_landscape", "title": "Competitive landscape"},
    {"id": "supply_chain", "title": "Supply chain positioning"},
    {"id": "leverage", "title": "Financial and operating leverage"},
    {"id": "valuation", "title": "Valuation"},
    {"id": "developments_risks", "title": "Recent developments and risk factors"},
    {"id": "swot_cases", "title": "SWOT analysis, bull and bear case"},
    {"id": "overall_assessment", "title": "Overall assessment and watch points"}
  ],
  "custom_questions": [
    {"id": "q1", "text": "How exposed is the company to China demand?", "section_id": "developments_risks"}
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

## Decisions Locked

- Required charts: price chart and income statement sankey.
- Required tables: technical levels and peer ratios/fundamentals comparison.
- Section length target: 300-1000 words (soft limit, optimizer rewrites to fit).
