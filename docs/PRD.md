# Trace product requirements

## Product promise

An investigator should be able to explain what happened, what is uncertain, what additional evidence matters, and which action the supplied bank policy permits. A compelling submission combines accurate graph investigation with visible decision changes and complete audit records.

Primary audience: fraud analysts and hackathon judges. Constraints: no paid services; local development on an M3/8 GB Mac; TigerGraph remains required. The deadline prioritizes the delivery sequence without redefining the product's ambition.

## Scoring alignment

| Criterion | Weight | Implementation |
|---|---:|---|
| Investigation accuracy | 25% | Temporal evidence, customer baselines, identity signals, episode scoping, connected profiles and prior case outcomes |
| Next best action | 25% | Policy-controlled actions, initial/final recommendations, explicit verification and escalation |
| Explainability | 10% | Provenance, evidence graph, supporting/contradicting findings, short case summaries |
| Agentic engineering | 15% | Stateful workflow, bounded local-model tool selection, durable events, idempotent evidence/approval operations |
| Innovation | 15% | Decision-changing evidence scenarios, undocumented-pattern corroboration, candidate discovery, replay |
| Demo completeness | 10% | Real-data workbench and reproducible exports; live TigerGraph remains an integration gate |

## Required workflow

Trigger → retrieve → compare explanations → assess → apply policy → request evidence if needed → reassess → stop or escalate → persist → export.

The state includes immutable initial actions, current actions, exposure, verdict, pattern, evidence, prior-case references, simulation assumptions, decision revision, approvals, graph-persistence status, tool counts, tokens, and latency.

## Functional requirements

1. All 20 organizer cases load into a searchable queue and can be investigated independently.
2. Transaction, customer, card, device-profile, and region data are traceable to actual organizer rows.
3. Card IDs are anchored and ambiguity is explicit; unnamed model features retain unnamed semantics.
4. Existing confirmed and cleared historical cases inform evidence; new predictions never masquerade as confirmed outcomes.
5. Device sharing needs behavioral corroboration. Graph links alone do not imply guilt.
6. The documented patterns are investigated; supported coordinated abuse may remain `undocumented` rather than being forced into a category.
7. Every next action obeys the supplied policy and approval route. Missing settlement data prevents a claim that a purchase cleared.
8. An original customer denial is distinguished from a simulated response. Scenario exploration is non-mutating; recorded simulated responses are visibly labeled.
9. The interface supports evidence selection, graph inspection, timeline review, action history, approval simulation, SAR preview, export, and recorded replay.
10. Graph records and vector grounding are required for submission readiness. Local-mode drafts cannot be silently promoted.
11. Candidate discovery stays outside the benchmark folder. Evaluation reports actual measurements and limitations.
12. Local model and embedding calls cannot fall back to paid endpoints.

## Acceptance and operational quality

- Exact answer schema and dataset-ID checks; exposure is computed from selected transactions.
- SAR fields agree with final actions; legitimate verdicts carry no affected fraud transactions or exposure.
- No restricted action runs without matching approval, and this demo never performs actual financial operations.
- Duplicate responses and approvals are idempotent; stale-revision approvals fail.
- All evidence retrieval respects the investigation cutoff.
- Service failures are visible. A failed query is never interpreted as an absence of suspicious activity.
- Graph writes are independently read back before persistence is claimed.
- Desktop and narrow-screen workflows remain usable; fonts are bundled locally.

## Submission deliverables

Working application, reproducible repository, twenty verified answer files in `cases/`, a 3–5 minute demo, technical blog, and social post linking the blog/demo and tagging TigerGraph. Publishing and real service setup require appropriate user-owned access.

## Current gates

Local functionality and draft generation are implemented. Live TigerGraph setup, remote query compilation, full graph/vector loading, final output promotion, and recorded/published submission media remain gates. Historical scoring is explicitly advisory because its selected training cohort differs from benchmark cases. No claim of winning or hidden-key accuracy is made.
