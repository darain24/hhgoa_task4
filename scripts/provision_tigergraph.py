"""Install and load ONLY an already-authorized, no-charge TigerGraph workspace.
No account creation, billing, instance provisioning, or destructive DDL.
"""

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tracework import retrieval, store, tigergraph
from tracework.config import DATA, ROOT, TG_GRAPH


def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()


async def nodes(kind, values):
    if values:
        await tigergraph.call(
            "tigergraph__add_nodes",
            {"graph_name": TG_GRAPH, "vertex_type": kind, "vertices": values},
        )


async def edges(kind, source, target, values):
    if values:
        await tigergraph.call(
            "tigergraph__add_edges",
            {
                "graph_name": TG_GRAPH,
                "edge_type": kind,
                "edges": [
                    {
                        "source_type": source,
                        "source_id": s,
                        "target_type": target,
                        "target_id": t,
                    }
                    for s, t in values
                ],
            },
        )


async def load():
    with store.connect() as c:
        total = c.execute("SELECT count(*) FROM transactions").fetchone()[0]
        last = ""
        done = 0
        while True:
            batch = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM transactions WHERE id>? ORDER BY id LIMIT 500",
                    (last,),
                )
            ]
            if not batch:
                break
            await nodes(
                "Customer",
                [{"id": v} for v in sorted({t["customer_id"] for t in batch})],
            )
            cards = {t["card_id"]: bool(t["card_verified"]) for t in batch}
            await nodes("Card", [{"id": k, "verified": v} for k, v in cards.items()])
            await nodes(
                "Transaction",
                [{k: v for k, v in t.items() if k != "signature"} for t in batch],
            )
            await nodes(
                "DeviceProfile",
                [
                    {"id": digest(v), "description": v}
                    for v in sorted({t["device"] for t in batch if t["device"]})
                ],
            )
            await nodes(
                "BillingRegion",
                [
                    {"id": v}
                    for v in sorted({t["region"] for t in batch if t["region"]})
                ],
            )
            await nodes(
                "EmailDomain",
                [{"id": v} for v in sorted({t["email"] for t in batch if t["email"]})],
            )
            await edges(
                "OWNS",
                "Customer",
                "Card",
                list({(t["customer_id"], t["card_id"]) for t in batch}),
            )
            await edges(
                "MADE", "Card", "Transaction", [(t["card_id"], t["id"]) for t in batch]
            )
            await edges(
                "FROM_DEVICE",
                "Transaction",
                "DeviceProfile",
                [(t["id"], digest(t["device"])) for t in batch if t["device"]],
            )
            await edges(
                "BILLED_IN",
                "Transaction",
                "BillingRegion",
                [(t["id"], t["region"]) for t in batch if t["region"]],
            )
            await edges(
                "PURCHASER_EMAIL",
                "Transaction",
                "EmailDomain",
                [(t["id"], t["email"]) for t in batch if t["email"]],
            )
            last = batch[-1]["id"]
            done += len(batch)
            print(f"Uploaded {done}/{total}", flush=True)
        history = [dict(r) for r in c.execute("SELECT * FROM history")]
        for offset in range(0, len(history), 100):
            part = history[offset : offset + 100]
            await nodes(
                "ClosedCase",
                [{k: v for k, v in h.items() if k != "raw_json"} for h in part],
            )
            await edges(
                "INVOLVES",
                "ClosedCase",
                "Transaction",
                [(h["id"], tid) for h in part for tid in h["txn_ids"].split("|")],
            )
        previous = {}
        sequence = []
        for r in c.execute(
            "SELECT id,card_id FROM transactions ORDER BY card_id,ts,id"
        ):
            if r["card_id"] in previous:
                sequence.append((previous[r["card_id"]], r["id"]))
            previous[r["card_id"]] = r["id"]
            if len(sequence) >= 1000:
                await edges("NEXT", "Transaction", "Transaction", sequence)
                sequence = []
        await edges("NEXT", "Transaction", "Transaction", sequence)


async def documents():
    readme = (DATA / "raw" / "README.md").read_text()
    text = (
        readme.split("# Fraud Policy", 1)[1].split("# Answer Format", 1)[0]
        + "\n\n"
        + readme.split("## The five known fraud patterns", 1)[1].split(
            "## Regulatory references", 1
        )[0]
    )
    # Stable paragraph chunks retain policy names and source provenance.
    docs = [
        {
            "id": "README-" + str(i),
            "text": s[:6000],
            "kind": "policy_or_pattern",
            "closed_at": "",
        }
        for i, s in enumerate(text.split("\n\n"))
        if len(s.strip()) > 50
    ]
    with store.connect() as c:
        docs += [
            {
                "id": r["id"],
                "text": r["notes"],
                "kind": "historical_case",
                "closed_at": r["closed_at"],
            }
            for r in c.execute("SELECT * FROM history")
        ]
    for i, d in enumerate(docs):
        vector = await retrieval.embed(d["text"])
        await tigergraph.call(
            "tigergraph__upsert_vectors",
            {
                "graph_name": TG_GRAPH,
                "vertex_type": "Document",
                "vector_attribute": "embedding",
                "vectors": [
                    {
                        "vertex_id": d["id"],
                        "vector": vector,
                        "attributes": {k: v for k, v in d.items() if k != "id"},
                    }
                ],
            },
        )
        if i % 100 == 0:
            print(f"Embedded {i}/{len(docs)} documents", flush=True)


async def main(args):
    store.init()
    if TG_GRAPH != "Trace":
        raise SystemExit("Schema currently names Trace; use TG_GRAPH=Trace.")
    if args.schema:
        await tigergraph.call(
            "tigergraph__gsql",
            {"command": (ROOT / "tigergraph/schema.gsql").read_text()},
        )
        await tigergraph.call(
            "tigergraph__gsql",
            {
                "command": (ROOT / "tigergraph/queries.gsql").read_text(),
                "graph_name": TG_GRAPH,
            },
        )
        await tigergraph.call(
            "tigergraph__add_vector_attribute",
            {
                "graph_name": TG_GRAPH,
                "vertex_type": "Document",
                "vector_name": "embedding",
                "dimension": 384,
                "metric": "COSINE",
            },
        )
    if args.data:
        await load()
    if args.documents:
        await documents()
    print(
        "Provisioning operations finished. Run integration verification; do not assume compliance from upload success."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--schema", action="store_true")
    p.add_argument("--data", action="store_true")
    p.add_argument("--documents", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args))
