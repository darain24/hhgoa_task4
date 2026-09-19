"""Real TigerGraph MCP adapter. Never reports persistence on unavailable/mock services."""

import json
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import TG_GRAPH, TG_URL


class TigerGraphUnavailable(RuntimeError):
    pass


@asynccontextmanager
async def session():
    if not TG_URL:
        raise TigerGraphUnavailable(
            "TG_MCP_URL is not configured. Local analysis is not TigerGraph compliance."
        )
    async with streamablehttp_client(TG_URL, timeout=30) as (read, write, _):
        async with ClientSession(read, write) as client:
            await client.initialize()
            yield client


def unpack(result):
    if result.isError:
        raise TigerGraphUnavailable("TigerGraph MCP rejected the operation")
    texts = [x.text for x in result.content if getattr(x, "type", "") == "text"]
    values = []
    for t in texts:
        try:
            values.append(json.loads(t))
        except ValueError:
            values.append(t)
    for v in values:
        if isinstance(v, dict) and (
            v.get("error")
            or v.get("success") is False
            or (v.get("data") or {}).get("failed_count", 0)
        ):
            raise TigerGraphUnavailable(str(v.get("error", "TigerGraph query failed")))
    return values


async def health():
    if not TG_URL:
        return {
            "configured": False,
            "available": False,
            "verified": False,
            "reason": "Set TG_MCP_URL for the official TigerGraph MCP server. No paid account is configured.",
        }
    try:
        async with session() as client:
            tools = await client.list_tools()
        return {
            "configured": True,
            "available": True,
            "verified": False,
            "tools": [t.name for t in tools.tools],
            "reason": "MCP reachable; query and persistence verification still required.",
        }
    except Exception as e:
        return {
            "configured": True,
            "available": False,
            "verified": False,
            "reason": str(e)[:250],
        }


async def call(name, arguments):
    async with session() as client:
        listed = await client.list_tools()
        tool = next((t for t in listed.tools if t.name == name), None)
        if not tool:
            raise TigerGraphUnavailable(f"Required tool unavailable: {name}")
        # Validate against the actual server schema before submitting.
        import jsonschema

        jsonschema.validate(arguments, tool.inputSchema)
        return unpack(await client.call_tool(name, arguments))


async def query(name, params):
    return await call(
        "tigergraph__run_installed_query",
        {"graph_name": TG_GRAPH, "query_name": name, "params": params},
    )


async def persist(answer):
    # Installed query writes a JSON case payload; the independent read verifies exact payload.
    candidate = json.loads(json.dumps(answer))
    candidate["case"]["written_to_graph"] = True
    candidate["case"]["graph_case_id"] = answer["case_id"]
    payload = json.dumps(candidate, sort_keys=True, separators=(",", ":"))
    await call(
        "tigergraph__add_node",
        {
            "graph_name": TG_GRAPH,
            "vertex_type": "Investigation",
            "vertex_id": answer["case_id"],
            "attributes": {"payload": payload, "outcome_verified": False},
        },
    )
    read = await call(
        "tigergraph__get_node",
        {
            "graph_name": TG_GRAPH,
            "vertex_type": "Investigation",
            "vertex_id": answer["case_id"],
        },
    )

    def contains(value):
        if value == payload:
            return True
        if isinstance(value, dict):
            return any(contains(v) for v in value.values())
        if isinstance(value, list):
            return any(contains(v) for v in value)
        return False

    if not contains(read):
        raise TigerGraphUnavailable(
            "Read-back did not match the saved case; persistence remains unverified"
        )
    for tid in answer["case"]["affected_txn_ids"]:
        await call(
            "tigergraph__add_edges",
            {
                "graph_name": TG_GRAPH,
                "edge_type": "FINDING",
                "edges": [
                    {
                        "source_type": "Investigation",
                        "source_id": answer["case_id"],
                        "target_type": "Transaction",
                        "target_id": tid,
                    }
                ],
            },
        )
    return answer["case_id"]
