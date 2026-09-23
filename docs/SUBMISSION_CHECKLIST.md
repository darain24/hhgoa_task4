# Submission gates

## Done

- [x] Read the full task PDF and the dataset README.
- [x] Load all organizer transactions, identity records, historical cases and benchmark triggers.
- [x] Build the React workbench, the investigation engine and the deterministic policy layer.
- [x] Run local-model inference and local embeddings with no paid API.
- [x] Stand up TigerGraph Community Edition and the official TigerGraph MCP server locally.
- [x] Compile and validate the schema and queries on that instance.
- [x] Load the benchmark subgraph: 42,566 transactions, 2,203 cards, 2,651 device profiles,
      5,565 closed cases, and their relationships.
- [x] Load the GraphRAG corpus into the TigerGraph vector store: 503 documents at 384
      dimensions, covering the policy, the patterns, the regulatory references and the
      closed-case narratives.
- [x] Verify graph/local evidence parity, vector retrieval and case write/read-back for
      every benchmark case.
- [x] Replace the hand-tuned scoring with weights fitted on the organizer's own closed
      cases, and hold them out (`scripts/fit_evidence_model.py`).
- [x] Validate episode scope against 250 October confirmed-fraud episodes.
- [x] Record evidence requests, simulated replies and their basis, and both the initial
      and final recommendation with approval routes.
- [x] Write SAR narratives that stand on their own, at the specified length.
- [x] Generate twenty answers and promote them into `cases/` through the guarded exporter.
- [x] Audit all twenty against the organizer's Answer Format: field sets, enums, ID
      existence, exposure arithmetic, SAR/action agreement, narrative and summary length.
- [x] Isolate the test suite from the live graph.
- [x] Tests, production frontend build, output checks and lint all pass.

## Remaining, and owned by the team

- [ ] Record the 3–5 minute end-to-end demo video.
- [ ] Publish the technical blog post from `docs/BLOG_DRAFT.md`.
- [ ] Publish the social post from `docs/SOCIAL_DRAFT.md` with the real links, tagging
      @TigerGraphDB.
- [ ] Push the repository publicly, with no credentials and no dataset redistribution.
- [ ] Submit the form by Sept 24, 2026, 23:59 IST. One submission, by the team lead.

## What the numbers do and do not mean

Holdout accuracy on October alerts is a development measurement, not benchmark accuracy;
the answer key is hidden. Twenty valid, graph-backed, policy-consistent answers is a
completeness result, not a correctness one. The assessment is calibrated for the
investigated-alert population, which is not the general transaction population. No real
customer, card, or regulator is contacted by this application.
