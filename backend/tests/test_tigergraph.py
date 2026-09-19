import asyncio
import json
from types import SimpleNamespace

import pytest
from tracework import tigergraph


def test_partial_vector_upload_is_not_success():
    result = SimpleNamespace(
        isError=False,
        content=[
            SimpleNamespace(
                type="text",
                text=json.dumps({"success": True, "data": {"failed_count": 1}}),
            )
        ],
    )
    with pytest.raises(tigergraph.TigerGraphUnavailable):
        tigergraph.unpack(result)


def test_write_without_readback_cannot_claim_persistence(monkeypatch):
    async def call(name, arguments):
        return [{"success": True, "data": {}}]

    monkeypatch.setattr(tigergraph, "call", call)
    with pytest.raises(tigergraph.TigerGraphUnavailable, match="Read-back"):
        asyncio.run(
            tigergraph.persist(
                {
                    "case_id": "x",
                    "case": {
                        "written_to_graph": False,
                        "graph_case_id": "",
                        "affected_txn_ids": [],
                    },
                }
            )
        )


def test_verified_readback_matches_exported_graph_fields(monkeypatch):
    saved = {}

    async def call(name, arguments):
        if name == "tigergraph__add_node":
            saved.update(arguments["attributes"])
            return []
        return [{"attributes": saved}]

    monkeypatch.setattr(tigergraph, "call", call)
    answer = {
        "case_id": "x",
        "case": {
            "written_to_graph": False,
            "graph_case_id": "",
            "affected_txn_ids": [],
        },
    }
    assert asyncio.run(tigergraph.persist(answer)) == "x"
    payload = json.loads(saved["payload"])
    assert payload["case"]["written_to_graph"] is True
    assert payload["case"]["graph_case_id"] == "x"
    assert answer["case"]["written_to_graph"] is False


def test_missing_service_never_reports_available(monkeypatch):
    monkeypatch.setattr(tigergraph, "TG_URL", "")
    result = asyncio.run(tigergraph.health())
    assert not result["available"] and not result["verified"]
