from tracework.analysis import assess


def transaction(id="f", **kw):
    return {
        "id": id,
        "customer_id": "u",
        "card_id": "c",
        "ts": "2016-11-01 12:00:00",
        "amount": 50,
        "channel": "online",
        "risk": 0.95,
        "region": "r",
        "product": "C",
        "device": "common phone",
        "new_device": "",
        "proxy": "",
        "match_flags": "{}",
        "card_verified": 1,
        **kw,
    }


def packet():
    f = transaction()
    baseline = [
        transaction(str(i), ts=f"2016-10-{i + 1:02d} 12:00:00") for i in range(10)
    ]
    return {
        "flagged": f,
        "baseline": baseline,
        "timeline": [f],
        "neighbors": [],
        "history": [],
        "card48": [f],
        "cust48": [f],
        "prior30": 14,
        "region_run": [f],
    }


def test_high_risk_score_is_not_a_verdict():
    """A 0.95 model score with nothing behind it must not reach a fraud verdict,
    and the score must not contribute any weight to the assessment."""
    from tracework.analysis import WEIGHTS

    a = assess(packet(), {"trigger_type": "risk_score", "case_id": "x"})
    assert a["verdict"] != "fraud"
    assert a["probability"] < 0.95
    assert "risk" not in WEIGHTS
    assert not any(x["name"] == "risk" for x in a["findings"])


def test_score_alone_cannot_move_the_assessment():
    """Two identical cases differing only in the bank's score assess identically."""
    low, high = packet(), packet()
    low["flagged"] = {**low["flagged"], "risk": 0.02}
    high["flagged"] = {**high["flagged"], "risk": 0.99}
    trigger = {"trigger_type": "risk_score", "case_id": "x"}
    assert assess(low, trigger)["probability"] == assess(high, trigger)["probability"]


def test_shared_profile_is_not_a_fraud_ring():
    p = packet()
    p["neighbors"] = [
        transaction(
            str(i),
            card_id=f"c{i}",
            customer_id=f"u{i}",
            new_device="New",
            proxy="anonymous",
            amount=300,
        )
        for i in range(5)
    ]
    a = assess(p, {"trigger_type": "risk_score", "case_id": "x"})
    assert not a["shared_fraud"]
    assert not a["connected_cards"]


def test_testing_sequence_requires_three_small_prior_transactions():
    p = packet()
    p["flagged"] = transaction(amount=250)
    p["timeline"] = [
        transaction(str(i), amount=2, ts=f"2016-11-01 11:{10 + i:02d}:00")
        for i in range(3)
    ] + [p["flagged"]]
    a = assess(p, {"trigger_type": "risk_score", "case_id": "x"})
    assert a["testing"]
    assert a["pattern"] == "card_testing"
    assert a["exposure"] == 256
