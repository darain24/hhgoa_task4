"""Run local evidence selection on all saved benchmark cases; no paid services."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tracework import engine, store
from tracework.config import ROOT


async def main():
    with store.connect() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM cases ORDER BY id")]
    for id in ids:
        try:
            r = await engine.review(id)
            (ROOT / "output/draft-cases" / f"{id}.json").write_text(
                json.dumps(r["result"], indent=2)
            )
            print(id, "reviewed", r["result"]["tokens"], "tokens", flush=True)
        except Exception as e:
            print(id, "FAILED", str(e), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
