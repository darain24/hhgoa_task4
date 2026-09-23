# Social post draft — insert the real links before publishing

We built Trace for Hacker House Goa: an agentic fraud investigator on TigerGraph.

First thing we did was check the bank's own fraud model against its own closed cases.
ROC-AUC 0.053. Inverted. Every cleared case had scored 0.82 or higher.

It isn't broken — it's what decides which alerts get opened, and the ones it shouts
loudest about are the customers who bought a new phone or went on a trip. So we threw the
score away and scored the evidence instead: eleven named findings, each with a weight
fitted on the bank's own closed investigations. Holdout ROC-AUC 0.849.

The agent grounds every claim in GSQL over TigerGraph and refuses to continue if the graph
disagrees, retrieves the policy it cites from TigerGraph's vector store, asks the customer
when the evidence is too thin to act, and writes each closed case back into the graph so
the next investigation can find it by traversal.

Our first hand-tuned version produced twenty perfectly valid JSON files and scored 0/40 on
the only holdout we had. A clean schema tells you nothing about whether the investigation
is right.

Demo: [link]
Write-up: [link]
Code: [link]

@TigerGraphDB #TigerGraph #GraphRAG #AgenticAI
