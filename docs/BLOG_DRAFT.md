# Trace: making fraud decisions inspectable

**Draft — update integration status and measured results before publication.**

An unusually large purchase, a new device, or a high model score can justify investigation. None necessarily tells an analyst what to do next. For the TigerGraph Hacker House Goa challenge, we built Trace around that gap: evidence, uncertainty, policy, and a complete record of how a decision changes.

## What we built

Trace is a React analyst workbench with a Python investigation engine. Analysts can inspect a transaction timeline, follow connected profiles, compare suspicious and legitimate explanations, explore hypothetical responses, and record simulated customer evidence. The original recommendation remains visible after the new evidence changes the case. Approval routes and SAR recommendations come from the supplied policy.

The current local build uses the organizer's 590,742 transactions, 144,432 identity records, 5,565 historical investigations, and twenty benchmark cases. It does not use original Kaggle outcomes. Local language-model inference and embeddings run through Ollama, with no paid API fallback.

## How the graph fits

Customers own cards, cards connect to transactions, and transactions connect to device profiles, regions, and email domains. Historical cases link to the investigated transactions. The TigerGraph integration includes GSQL traversal, time-bounded network expansion, vector retrieval, and independently verified case write/read-back through the official MCP server.

**At the time of this draft, live TigerGraph access has not been configured.** The workbench labels its local SQLite projection explicitly and blocks final submission export until real graph/vector evidence and persistence are verified. Replace this paragraph only after recording successful integration evidence.

## What makes the investigation agentic

The investigator gathers a bounded evidence packet. A local model selects relevant evidence and an allowed follow-up tool. The engine compares supporting and opposing findings, then evaluates the next action against deterministic policy rules. When a simulated response arrives, the state progresses and the evidence trail remains intact.

A scenario panel shows why evidence matters: confirmation, denial, and no reply lead to different permitted actions. Exploring those branches never silently changes the case. Recorded simulations are labeled as assumptions.

## What we learned

The first hand-written scoring rules performed poorly on historical diagnostics. We preserved that result and added a temporal statistical comparison, trained only on earlier organizer cases. The historical model performed better on the October development cohort, but its predictions did not obviously transfer to the benchmark distribution. We therefore kept it advisory. A polished interface and passing schema checks are not evidence of investigation accuracy.

We also observed that a local model could produce an unsupported summary statement. Trace now renders factual summaries from verbatim evidence selected by the model. This preserves model-assisted selection without letting generated facts enter the record unchecked.

Finally, shared device profiles are not unique devices, and billing-region codes are not physical geolocation. Useful graph reasoning requires corroboration, not dramatic-looking connections.

## What comes next

Complete live TigerGraph verification; evaluate more held-out episodes; improve hypothesis ranking and stopping quality; validate calibration under changed case selection; and add production identity, authorization, and observability if taking the project beyond the hackathon. The current app intentionally simulates banking and regulatory actions.

The aim is a workflow where an analyst can inspect every important claim and understand why the next action follows from the evidence.
