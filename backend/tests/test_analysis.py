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
    }


def test_high_risk_score_is_not_a_verdict():
    a = assess(packet(), {"trigger_type": "risk_score", "case_id": "x"})
    assert a["verdict"] == "legitimate"
    assert a["probability"] < 0.95


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
