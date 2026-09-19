"""Reassess untouched drafts after engine changes, preserving prior snapshots in the event log."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tracework import engine, store
from tracework.config import ROOT


async def main():
    store.init()
    with store.connect() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM cases ORDER BY id")]
    for id in ids:
        r = store.get_case(id)
        if r["result"] and r["result"]["evidence_requests"]:
            continue
        with store.connect() as c:
            if c.execute("SELECT 1 FROM approvals WHERE case_id=?", (id,)).fetchone():
                continue
        if r["result"]:
            store.event(
                id,
                "revision",
                "Previous draft archived before re-assessment",
                {"answer": r["result"]},
            )
        with store.connect() as c:
            c.execute(
                "UPDATE cases SET result_json=NULL,detail_json=NULL,state='queued' WHERE id=?",
                (id,),
            )
        r = await engine.investigate(id, False)
        (ROOT / "output/draft-cases" / f"{id}.json").write_text(
            json.dumps(r["result"], indent=2)
        )
        print(
            id,
            r["result"]["case"]["verdict"],
            r["result"]["case"]["pattern"],
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
