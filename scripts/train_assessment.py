"""Train July–August, calibrate September, evaluate October. Never use exam outcomes."""

import csv
import json
import math
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from tracework import store
from tracework.config import DATA, ROOT


def main():
    store.init()
    start = time.monotonic()
    with store.connect() as c:
        histories = [
            dict(r) for r in c.execute("SELECT * FROM history ORDER BY opened_at")
        ]
        targets = {h["txn_ids"].split("|")[0] for h in histories}
        targets.update(
            json.loads(r[0])["flagged_txn_id"]
            for r in c.execute("SELECT trigger_json FROM cases")
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS scoring_features(id TEXT PRIMARY KEY,features TEXT NOT NULL)"
        )
        found = {}
        with open(DATA / "raw/transactions.csv") as f:
            reader = csv.DictReader(f)
            # Numeric anonymous features are signals, with no invented real-world meanings.
            cols = [
                k
                for k in reader.fieldnames
                if k.startswith(("V", "C", "D", "M"))
                and k not in ["TransactionDT", "TransactionID"]
            ]
            cols = [k for k in cols if k not in ["DeviceInfo", "DeviceType"]]
            cols += ["TransactionAmt", "risk_score", "addr1", "addr2", "dist1", "dist2"]
            for row in reader:
                if row["TransactionID"] not in targets:
                    continue
                values = []
                for k in cols:
                    v = row.get(k, "")
                    if v in ("T", "F"):
                        value = 1.0 if v == "T" else 0.0
                    else:
                        try:
                            value = float(v)
                        except (ValueError, TypeError):
                            value = float("nan")
                    values.append(value if math.isfinite(value) else None)
                found[row["TransactionID"]] = values
        c.executemany(
            "INSERT OR REPLACE INTO scoring_features VALUES(?,?)",
            [(id, json.dumps(v)) for id, v in found.items()],
        )

    def get_data(group):
        selected = [
            h for h in histories if group(h) and h["txn_ids"].split("|")[0] in found
        ]
        X = np.array([found[h["txn_ids"].split("|")[0]] for h in selected], dtype=float)
        y = np.array([int(h["outcome"] == "confirmed_fraud") for h in selected])
        return X, y, selected

    def train(h):
        return h["opened_at"] < "2016-09-01" and h["closed_at"] < "2016-09-01"

    def calibrate(h):
        return (
            "2016-09-01" <= h["opened_at"] < "2016-10-01"
            and h["closed_at"] < "2016-10-01"
        )

    def test(h):
        return h["opened_at"] >= "2016-10-01"

    X, y, tr = get_data(train)
    CX, cy, cal = get_data(calibrate)
    TX, ty, te = get_data(test)
    assert not (
        {h["txn_ids"].split("|")[0] for h in tr}
        & {h["txn_ids"].split("|")[0] for h in cal + te}
    )
    assert not (
        {h["txn_ids"].split("|")[0] for h in cal}
        & {h["txn_ids"].split("|")[0] for h in te}
    )
    estimator = HistGradientBoostingClassifier(
        max_iter=150,
        max_leaf_nodes=15,
        max_depth=5,
        learning_rate=0.08,
        min_samples_leaf=20,
        early_stopping=False,
        random_state=42,
    )
    mask = np.array(
        [len(np.unique(X[:, i][np.isfinite(X[:, i])])) > 1 for i in range(X.shape[1])]
    )
    Xfit = np.nan_to_num(X[:, mask], nan=-999)
    Cfit = np.nan_to_num(CX[:, mask], nan=-999)
    Tfit = np.nan_to_num(TX[:, mask], nan=-999)
    estimator.fit(Xfit, y)
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        estimator.predict_proba(Cfit)[:, 1], cy
    )
    p = calibrator.predict(estimator.predict_proba(Tfit)[:, 1])
    bank = TX[:, -5]

    def metrics(prob):
        return {
            "n": len(ty),
            "brier": round(brier_score_loss(ty, prob), 4),
            "roc_auc": round(roc_auc_score(ty, prob), 4),
            "accuracy_at_0_5": round(accuracy_score(ty, prob >= 0.5), 4),
            "confusion_matrix": confusion_matrix(ty, prob >= 0.5).tolist(),
        }

    report = {
        "train_cases": len(tr),
        "calibration_cases": len(cal),
        "test_cases": len(te),
        "feature_count": len(cols),
        "train": "Opened and closed before September 1",
        "calibration": "Opened in September and closed before October 1",
        "test": "All October historical cases; not the hidden benchmark",
        "version": "historical-v1",
        "metrics": {"historical_model": metrics(p), "bank_score": metrics(bank)},
        "elapsed_s": round(time.monotonic() - start, 2),
        "limitations": [
            "Labels come from selected investigations, so calibration is not a population fraud probability.",
            "October was previously used for heuristic diagnostics; this is a development comparison, not a pristine final holdout.",
            "Anonymous numeric features are not interpreted as named real-world behaviors.",
            "Assessment probabilities do not replace evidence, policy, or required customer verification.",
        ],
    }
    bundle = {
        "estimator": estimator,
        "calibrator": calibrator,
        "columns": cols,
        "mask": mask,
        "version": report["version"],
    }
    with open(DATA / "historical_model.pkl", "wb") as f:
        pickle.dump(bundle, f)
    with store.connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO metadata VALUES(?,?)",
            ("scoring_model", json.dumps(report)),
        )
    (ROOT / "output" / "historical-model-evaluation.json").write_text(
        json.dumps(report, indent=2)
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
