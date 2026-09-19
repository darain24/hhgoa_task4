import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tracework import engine, store
from tracework.config import ROOT


async def main(use_llm):
    store.init()
    with store.connect() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM cases ORDER BY id")]
    target = ROOT / "output" / "draft-cases"
    target.mkdir(parents=True, exist_ok=True)
    for id in ids:
        try:
            r = await engine.investigate(id, use_llm)
            (target / f"{id}.json").write_text(json.dumps(r["result"], indent=2))
            a = r["result"]["case"]
            print(id, a["verdict"], a["pattern"], a["exposure_usd"], flush=True)
        except Exception as e:
            print(id, "FAILED", str(e), flush=True)
    print(
        "Drafts only: graph-backed retrieval and persistence must be verified before submission."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--llm", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.llm))
