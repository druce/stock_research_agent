# Repository Guidelines

## Project Structure & Module Organization

- `skills/` holds standalone skills; `skills/research_stock.py` orchestrates the multi-phase research workflow.
- `templates/` stores Jinja2 report templates, charts, and table partials used for final report assembly.
- `work/` contains per-run outputs (e.g., `work/AAPL_20260114/`) with standardized subfolders:
  - `beads/` for structured research beads and indexes.
  - `sources/` for raw source captures (SEC, news, web pages).
  - `drafts/` for section drafts and critic notes.
  - `sections/` for finalized section text.
  - `tables/` and `charts/` for numeric outputs and visuals.
  - `critique/` for critic outputs and optimizer plans.
  - `logs/` for runtime logs and tool transcripts.
- `requirements.txt` defines Python dependencies; `CLAUDE.md` captures environment setup.

## Research Workflow: `skills/research_stock.py`

Phase 0: Intake and outline
- Validate ticker and show a standard outline.
- Capture user confirmation plus any custom sections or questions to research.
- Persist the outline and questions as beads plus a local `outline.json`.

Phase 1: Research and capture
- Gather information using available tools and save raw outputs to `sources/`.
- Create structured beads for facts, metrics, events, quotes, and source metadata.
- For user questions, send targeted prompts (Perplexity or equivalent), store answers as beads, and tag each bead with one or more outline sections.

Phase 2: Section writing with critic/optimizer
- For each outline section, run a Claude agent with access to bead tools and local files.
- Produce one draft, run a critic pass, then optimize once per section.
- Save outputs to `drafts/`, finalize to `sections/`, and attach bead/file citations used.
- Target 300-1000 words per section (soft limit), and have the optimizer rewrite to fit without hard truncation.

Phase 3: Assembly and global polish
- Assemble sections into a unified report body.
- Run a critic/optimizer pass over the full report, focusing on gaps, unanswered questions, and redundancy.
- Rewrite to a professional analyst tone with clear, non-duplicative structure.

Phase 4: Jinja2 report rendering
- Use Jinja2 templates to build the final report, inserting charts, tables, and section text.
- Emit the final report to `work/{TICKER}_{YYYYMMDD}/report/` in markdown and any desired export formats.

## Beads & Local File Strategy

- Beads are the single source of truth (no SQL, knowledge graph, or vector store).
- Each bead has: `id`, `type`, `title`, `summary`, `content`, `source`, `confidence`, `timestamp`, `tags`.
- Use `tags.section` to map beads to outline sections, and `tags.topic` for cross-cutting themes.
- Maintain a bead index file (e.g., `beads/index.json`) that links bead IDs to source files and sections.
- Store raw source text in `sources/` and create a companion bead that references the file path.
- Required visuals: price chart and income statement sankey.
- Required tables: technical levels and peer ratios/fundamentals comparison.

## Tools Exposure (Section Agents)

- Bead tools: create, update, search, and fetch by ID or section tag.
- File tools: read and write local files (sources, charts, tables, drafts).
- Reporting tools: table builder, chart renderer, and Jinja2 template renderer.
- Web tools only for research-phase agents; writing agents should rely on beads and local files.

## Build, Test, and Development Commands

- `conda activate mcpskills` activates the Python 3.11 environment.
- `pip install -r requirements.txt` installs dependencies.
- `python ./skills/research_stock.py AAPL` runs the end-to-end workflow.

## Coding Style & Naming Conventions

- Use Python 3.11, 4-space indentation, and PEP 8 conventions.
- Prefer `snake_case` for functions/variables and `UPPER_SNAKE_CASE` for constants.
- Skills are CLI-first: include a top-of-file docstring with usage, use `argparse`, and keep error messages actionable.
- Templates in `templates/` use Jinja2; keep variable names aligned with skill outputs.

## Testing Guidelines

- No automated tests yet. Validate by running the skill and inspecting outputs under `work/`.
- When adding tests, use `tests/` and standard `test_*.py` names.

## Security & Configuration Tips

- Store API keys in `.env` (`PERPLEXITY_API_KEY`, `ANTHROPIC_API_KEY`, data-provider keys).
