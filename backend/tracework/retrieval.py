"""TigerGraph graph/vector grounding and local, cached embeddings."""

import hashlib
import json
from datetime import timedelta

import httpx

from . import analysis, store, tigergraph
from .config import OLLAMA, TG_GRAPH

EMBED_MODEL = "all-minilm"


async def embed(text):
    key = "embed:" + hashlib.sha256((EMBED_MODEL + text).encode()).hexdigest()
    with store.connect() as c:
        r = c.execute("SELECT value FROM llm_cache WHERE key=?", (key,)).fetchone()
    if r:
        return json.loads(r[0])
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            OLLAMA + "/api/embed", json={"model": EMBED_MODEL, "input": text[:6000]}
        )
        r.raise_for_status()
        vector = r.json()["embeddings"][0]
    with store.connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO llm_cache VALUES(?,?)", (key, json.dumps(vector))
        )
    return vector


def attributes(value, vertex_type):
    found = []

    def walk(v):
        if isinstance(v, dict):
            if v.get("v_type") == vertex_type and "attributes" in v:
                found.append(
                    {
                        **v["attributes"],
                        "id": str(v.get("v_id", v["attributes"].get("id", ""))),
                    }
                )
            else:
                for child in v.values():
                    walk(child)
        elif isinstance(v, list):
            for child in v:
                walk(child)

    walk(value)
    return found


async def ground(packet, trigger):
    raw = await tigergraph.query(
        "trace_customer_window",
        {"customer_id": trigger["customer_id"], "cutoff": trigger["opened_at"]},
    )
    tx = attributes(raw, "Transaction")
    lookup = {t["id"]: t for t in tx}
    for t in packet["baseline"] + packet["timeline"]:
        other = lookup.get(t["id"])
        if (
            not other
            or any(str(other.get(k)) != str(t[k]) for k in ["ts", "card_id", "region"])
            or abs(float(other.get("amount", 0)) - t["amount"]) > 0.001
        ):
            raise tigergraph.TigerGraphUnavailable(
                "Graph/local evidence mismatch: " + t["id"]
            )
    calls = 1
    if packet["flagged"]["device"]:
        f = packet["flagged"]
        raw = await tigergraph.query(
            "trace_device_window",
            {
                "device_id": hashlib.sha256(f["device"].encode()).hexdigest(),
                "cutoff": trigger["opened_at"],
                "start_at": (analysis.dt(f["ts"]) - timedelta(days=30)).isoformat(
                    sep=" "
                ),
            },
        )
        lookup = {t["id"]: t for t in attributes(raw, "Transaction")}
        calls += 1
        for t in packet["neighbors"]:
            if (
                t["id"] not in lookup
                or abs(float(lookup[t["id"]].get("amount", 0)) - t["amount"]) > 0.001
            ):
                raise tigergraph.TigerGraphUnavailable(
                    "Device query failed evidence parity check"
                )
    for h in packet["history"]:
        raw = await tigergraph.call(
            "tigergraph__get_node",
            {"graph_name": TG_GRAPH, "vertex_type": "ClosedCase", "vertex_id": h["id"]},
        )
        calls += 1
        matches = attributes(raw, "ClosedCase")
        if (
            not matches
            or matches[0]["closed_at"] >= trigger["opened_at"]
            or matches[0]["notes"] != h["notes"]
        ):
            raise tigergraph.TigerGraphUnavailable(
                "Historical case verification failed"
            )
    # Retrieve policies and pattern context from the actual TigerGraph vector index.
    vector = await embed(
        trigger.get("trigger_text", "") + " " + packet["flagged"]["channel"]
    )
    raw = await tigergraph.call(
        "tigergraph__search_top_k_similarity",
        {
            "graph_name": TG_GRAPH,
            "vertex_type": "Document",
            "vector_attribute": "embedding",
            "query_vector": vector,
            "top_k": 8,
        },
    )
    calls += 1
    docs = [
        d
        for d in attributes(raw, "Document")
        if not d.get("closed_at") or d["closed_at"] < trigger["opened_at"]
    ]
    if not docs:
        raise tigergraph.TigerGraphUnavailable(
            "No admissible vector context returned; GraphRAG is not verified"
        )
    await tigergraph.query(
        "trace_network_bfs",
        {"seeds": [trigger["card_id"]], "max_hops": 2, "cutoff": trigger["opened_at"]},
    )
    calls += 1
    packet["graph_documents"] = docs
    packet["source"] = "tigergraph"
    packet["tool_calls"] += calls
    return packet
