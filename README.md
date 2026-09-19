# Trace

**Evidence before action.** A local-first fraud investigation workbench built for TigerGraph × Hacker House Goa Task 4.

React/TypeScript interface, Python investigation engine, deterministic policy gates, real organizer data, local Ollama inference, and an official TigerGraph MCP adapter. No paid API provider or paid hosting dependency.

## Current implementation status

The workbench runs locally on the supplied dataset. It supports all twenty cases, evidence graphs, competing explanations, timelines, initial/final decisions, simulated customer responses and approvals, immutable event history, scenario exploration, draft JSON export, historical evaluation, and discovery candidates.

**TigerGraph access is not configured.** Local analysis uses a SQLite projection explicitly labeled as local evidence. TigerGraph schema, queries, upload/vector scripts, and MCP grounding/read-back verification are implemented but have not been executed against a live TigerGraph workspace. This is **not yet a compliant final hackathon submission**. Official submission export is blocked until its graph requirements pass.

## Run locally

Prerequisites: Python 3.11+, Node 22+, uv, and Ollama. The local model was tested on an Apple M3 with 8 GB memory.

```bash
uv sync --extra dev
npm ci --prefix frontend
uv run python scripts/download_data.py
uv run python scripts/ingest.py
ollama pull qwen3:4b
ollama pull all-minilm
uv run python scripts/train_assessment.py
uv run python scripts/run_benchmark.py
./scripts/dev.sh
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs.

The dataset download is approximately 740 MB. Models and Python dependencies require additional disk space. Data, model artifacts, and credentials stay outside Git.

To review all saved cases with the local LLM:

```bash
uv run python scripts/review_all.py
```

The local model selects supporting evidence and a permitted follow-up tool. Displayed factual summaries use verbatim source claims rather than trusting free-form model statements. Deterministic evidence review and policy routing remain in control. Requests are bounded and cached; tokens and latency are measured. Model failure is visible and does not produce a fake successful review.

## TigerGraph integration

Use an existing organizer workspace or verified no-charge credits. **Do not enable billing to follow this guide.** Savanna trial credits are not the same as permanently free instances. If no free workspace is available, keep using the explicitly labeled local workbench and leave submission readiness pending.

1. Copy `.env.example` to `.env` and configure your authorized workspace credentials. Keep `.env` private.
2. Start the official MCP server locally:

   ```bash
   uv run tigergraph-mcp --env-file .env --transport streamable-http --host 127.0.0.1 --port 9001
   ```

3. Set `TG_MCP_URL=http://127.0.0.1:9001/mcp`, `TG_GRAPH=Trace`, and `TG_GRAPHNAME=Trace`; restart the backend.
4. For a fresh namespace, inspect and execute the included schema and queries. The scripts contain no destructive DROP operations:

   ```bash
   uv run python scripts/provision_tigergraph.py --schema
   uv run python scripts/provision_tigergraph.py --data
   uv run python scripts/provision_tigergraph.py --documents
   uv run python scripts/verify_tigergraph.py
   ```

5. Resolve any server-version GSQL/vector compatibility errors before claiming integration. TigerVector requires compatible TigerGraph support. The client validates tool arguments against the actual MCP schema and treats partial upload failures as errors.
6. Reassess untouched drafts with `scripts/refresh_drafts.py`, then run `scripts/export_submission.py`. That exporter refuses incomplete graph-backed submissions.

The provisioning scripts are intentionally explicit and resumable by idempotent upserts, but full-data upload through MCP can take time. They must be validated against your workspace before a live demo. Auto-stop/auto-start should be enabled in Savanna.

## Verification

```bash
uv run pytest -q
npm run build --prefix frontend
uv run python scripts/check_outputs.py
```

Tests cover policy thresholds, approval routes and revisions, non-mutating scenarios, evidence-response idempotency, preserved initial actions, schema constraints, fabricated IDs, and submission guards.

Historical evaluation reports its actual sample and limitations. The official benchmark answer key is hidden. Export validity and policy checks do not establish investigation accuracy. `output/historical-model-evaluation.json` records the temporal statistical-model comparison. Its probabilities are calibrated for the selected historical-case sample, not the general transaction population.

## Important data semantics

- Risk scores initiate investigations; they are not labels.
- No original public Kaggle files or recovered outcomes are used.
- Card IDs are propagated from organizer anchors only when the exact six-field card signature maps unambiguously. Unresolved cards have internal IDs and cannot appear as canonical connected cards in submissions.
- Device profiles and billing regions are shared attributes, not proof of physical-device identity or geolocation.
- Merchant identity and authorization settlement status are not supplied. The app does not invent them.
- Numerical Vesta features are used only as anonymous signals.
- Prior case outcomes are retrieved only if closed before the investigation cutoff.
- Simulated replies are recorded as assumptions. No customer message, card block, or regulatory filing occurs.
- Approvals are demo controls, not production role-based authentication.

## Repository map

- `backend/tracework/`: API, state, evidence analysis, scoring, policy, local model, graph adapter, evaluation.
- `frontend/`: React workbench with local bundled fonts and interactive relationship visualization.
- `tigergraph/`: graph schema and reviewed query definitions awaiting live verification.
- `scripts/`: acquisition, ingestion, model training, benchmark execution, graph setup and validation.
- `docs/`: PRD, architecture, demo script, technical blog draft, and submission checklist.
- `output/draft-cases/`: twenty generated draft answers (ignored by Git).
- `cases/`: reserved for verified submission outputs. Drafts are never silently promoted.

## Attribution

Organizer dataset: IEEE-CIS Fraud Detection, Vesta Corporation, via IEEE Computational Intelligence Society; adapted by TigerGraph for Hacker House Goa 2026. Use the organizer's shared files and respect their distribution terms. No dataset is re-published in this repository.
