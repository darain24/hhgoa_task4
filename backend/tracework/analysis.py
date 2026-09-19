"""Transparent local evidence workbench. These are heuristics, not calibrated probabilities."""

from collections import Counter
from datetime import datetime, timedelta
from statistics import median

from . import store


def dt(s):
    return datetime.fromisoformat(s)


def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def collect(trigger, include_memory=True):
    calls = 0
    with store.connect() as c:

        def query(sql, args=()):
            nonlocal calls
            calls += 1
            return rows(c, sql, args)

        flagged = query(
            "SELECT * FROM transactions WHERE id=?", (trigger["flagged_txn_id"],)
        )
        if not flagged:
            raise ValueError("Flagged transaction is missing from the dataset")
        f = flagged[0]
        cutoff = trigger["opened_at"]
        when = dt(f["ts"])
        start = (when - timedelta(days=7)).isoformat(sep=" ")
        baseline = query(
            "SELECT * FROM transactions WHERE customer_id=? AND ts<? ORDER BY ts DESC LIMIT 300",
            (f["customer_id"], start),
        )
        timeline = query(
            "SELECT * FROM transactions WHERE customer_id=? AND ts>=? AND ts<=? ORDER BY ts,id",
            (f["customer_id"], start, cutoff),
        )
        neighbors = []
        if f["device"]:
            neighbors = query(
                "SELECT * FROM transactions WHERE device=? AND customer_id!=? AND ts BETWEEN ? AND ? ORDER BY ts DESC LIMIT 150",
                (
                    f["device"],
                    f["customer_id"],
                    (when - timedelta(days=30)).isoformat(sep=" "),
                    cutoff,
                ),
            )
        region_neighbors = []
        if f["channel"] == "in_person" and f["region"]:
            region_neighbors = query(
                "SELECT * FROM transactions WHERE region=? AND customer_id!=? AND ts BETWEEN ? AND ? ORDER BY ts LIMIT 80",
                (
                    f["region"],
                    f["customer_id"],
                    (when - timedelta(hours=24)).isoformat(sep=" "),
                    cutoff,
                ),
            )
        # Only previous closed cases are admissible as memory.
        history = []
        if include_memory:
            candidates = query(
                "SELECT * FROM history WHERE closed_at<? AND (customer_id=? OR card_id IN (SELECT card_id FROM transactions WHERE device=? AND device!=?)) ORDER BY closed_at DESC LIMIT 20",
                (cutoff, f["customer_id"], f["device"], ""),
            )
            history = candidates
            if f["device"]:
                device_ids = {
                    r["id"]
                    for r in query(
                        "SELECT id FROM transactions WHERE device=? AND ts<?",
                        (f["device"], cutoff),
                    )
                }
                all_closed = query(
                    "SELECT * FROM history WHERE closed_at<? ORDER BY closed_at DESC",
                    (cutoff,),
                )
                exact = [
                    h
                    for h in all_closed
                    if device_ids.intersection(h["txn_ids"].split("|"))
                ]
                # Exact episode/profile matches outrank a case on a merely related card.
                history = sorted(
                    exact,
                    key=lambda h: (h["pattern"] == "undocumented", h["closed_at"]),
                    reverse=True,
                )[:8]
                history += [
                    h for h in candidates if h["id"] not in {x["id"] for x in history}
                ][:4]
    return {
        "flagged": f,
        "baseline": baseline,
        "timeline": timeline,
        "neighbors": neighbors,
        "region_neighbors": region_neighbors,
        "history": history,
        "tool_calls": calls,
        "cutoff": cutoff,
        "source": "local_sqlite",
        "include_memory": include_memory,
    }


def assess(packet, trigger):
    f = packet["flagged"]
    baseline = packet["baseline"]
    same = [t for t in packet["timeline"] if t["card_id"] == f["card_id"]]
    evidence = []
    support = []
    counter = []
    groups = set()
    p = 0.35
    pattern = "none"
    affected = []
    conflict = False

    def ev(claim, ref, ids, side="support", group="behavior"):
        evidence.append(
            {
                "claim": claim,
                "source": "external",
                "ref": "local_sqlite:" + ref,
                "entity_ids": ids,
            }
        )
        (support if side == "support" else counter).append(claim)
        if side == "support":
            groups.add(group)

    ev(
        f"Organizer model risk score is {f['risk']:.2f}; this is an alert input, not a fraud verdict.",
        "flagged_transaction",
        [f["id"]],
        "counter",
    )
    amount_median = median([abs(t["amount"]) for t in baseline]) if baseline else None
    typical = bool(amount_median and abs(f["amount"]) <= max(20, amount_median * 1.8))
    regions = {t["region"] for t in baseline if t["region"]}
    products = {t["product"] for t in baseline}
    hour = [
        t
        for t in same
        if timedelta(0) <= dt(f["ts"]) - dt(t["ts"]) <= timedelta(hours=1)
    ]
    tiny = [
        t
        for t in hour
        if t["channel"] == "online" and 0 < abs(t["amount"]) < 5 and t["ts"] < f["ts"]
    ]
    testing = (
        len(tiny) >= 3
        and f["channel"] == "online"
        and abs(f["amount"]) > max(abs(t["amount"]) for t in tiny)
    )
    recent = [
        t
        for t in same
        if timedelta(0) <= dt(f["ts"]) - dt(t["ts"]) <= timedelta(hours=48)
    ]
    online = [t for t in recent if t["channel"] == "online"]
    new_device = f["new_device"] == "New"
    proxy = bool(f["proxy"])
    recurring_matches = [
        t
        for t in baseline
        if abs(abs(t["amount"]) - abs(f["amount"]))
        <= max(0.10, abs(f["amount"]) * 0.015)
        and 25 <= (dt(f["ts"]) - dt(t["ts"])).days <= 100
        and t["product"] == f["product"]
    ]
    recurring = len(recurring_matches) >= 2
    if baseline:
        ev(
            f"Customer baseline contains {len(baseline)} transactions before the episode; median amount ${amount_median:.2f}.",
            "customer_baseline",
            [t["id"] for t in baseline[:8]],
            "counter",
        )
    else:
        counter.append(
            "Historical baseline is insufficient; absence of history is not evidence of fraud."
        )
    if typical:
        p -= 0.12
        ev(
            "Flagged amount is within 1.8× the customer historical median (with a $20 floor).",
            "amount_baseline",
            [f["id"]] + [t["id"] for t in baseline[:3]],
            "counter",
        )
    if f["product"] in products and typical:
        p -= 0.04
        ev(
            "The product code has historical precedent and the amount is within the baseline range.",
            "product_baseline",
            [f["id"]],
            "counter",
        )
    if f["region"] in regions:
        p -= 0.06
        ev(
            "Billing region appears in the customer historical baseline.",
            "region_baseline",
            [f["id"]],
            "counter",
        )
    if amount_median and abs(f["amount"]) > max(amount_median * 3, 200):
        p += 0.20
        ev(
            "Amount is more than three times the historical median and exceeds $200.",
            "amount_anomaly",
            [f["id"]],
            group="amount",
        )
    if testing:
        p = 0.89
        pattern = "card_testing"
        affected = tiny + [f]
        ev(
            "At least three sub-$5 online transactions in one hour precede a larger purchase.",
            "testing_sequence",
            [t["id"] for t in affected],
            group="sequence",
        )
    elif f["channel"] == "online":
        if new_device:
            p += 0.12
            pattern = "card_not_present_new_device"
            ev(
                "Identity record marks this device as New for the account; a new phone remains a legitimate explanation.",
                "identity",
                [f["id"]],
                group="identity",
            )
        if proxy:
            p += 0.05
            ev(
                f"Identity proxy indicator is {f['proxy']}; not conclusive by itself.",
                "proxy",
                [f["id"]],
                group="identity",
            )
        unusual = [
            t
            for t in online
            if amount_median and abs(t["amount"]) > max(30, amount_median * 2)
        ]
        if len(unusual) >= 2:
            p += 0.20
            affected = unusual
            pattern = pattern if new_device else "card_not_present_fraud"
            ev(
                "Multiple unusual online amounts occur on this card within 48 hours.",
                "online_burst",
                [t["id"] for t in unusual],
                group="sequence",
            )
    elif f["region"] and regions and f["region"] not in regions:
        p += 0.14
        pattern = "out_of_region_use"
        affected = [f]
        ev(
            "Billing region is absent from the historical baseline; the code is not a physical geolocation.",
            "new_region",
            [f["id"]],
            group="region",
        )
        new_region = [t for t in same if t["region"] == f["region"]]
        days = len({t["ts"][:10] for t in new_region})
        if days >= 3:
            p -= 0.23
            ev(
                "Activity spans at least three days in the new billing region, supporting a travel explanation.",
                "regional_continuity",
                [t["id"] for t in new_region],
                "counter",
            )
        home = [
            t for t in recent if t["region"] in regions and t["region"] != f["region"]
        ]
        if home:
            p += 0.12
            ev(
                "Other activity within 48 hours retains familiar billing-region codes; this requires interpretation, not impossible-travel claims.",
                "region_overlap",
                [f["id"]] + [t["id"] for t in home],
                group="sequence",
            )
    if recurring:
        p = min(p, 0.40)
        ev(
            "Similar amounts and product codes recur roughly monthly. Merchant identity is not available, so this is a recurring-charge hypothesis only.",
            "recurring_amount",
            [f["id"]] + [t["id"] for t in recurring_matches],
            "counter",
        )
    relevant_history = packet["history"][:6]
    history_fraud = [h for h in relevant_history if h["outcome"] == "confirmed_fraud"]
    history_clear = [h for h in relevant_history if h["outcome"] == "cleared"]
    if relevant_history:
        ev(
            f"Retrieved {len(history_fraud)} confirmed-fraud and {len(history_clear)} cleared historical cases closed before this alert; similarity does not transfer their verdict.",
            "prior_cases",
            [h["id"] for h in relevant_history],
            "counter",
        )
    # Shared profiles are candidates; corroborate behavior on each connected card.
    neighbor_candidates = [
        t
        for t in packet["neighbors"]
        if t["card_verified"] and t["new_device"] == "New" and t["proxy"]
    ]
    card_counts = Counter(t["card_id"] for t in neighbor_candidates)
    suspicious_neighbors = [
        t for t in neighbor_candidates if card_counts[t["card_id"]] >= 2
    ]
    connected = sorted({t["card_id"] for t in suspicious_neighbors})
    historical_network = (
        len(
            {
                h["customer_id"]
                for h in history_fraud
                if h["customer_id"] != f["customer_id"]
                and h["pattern"] == "undocumented"
            }
        )
        >= 2
    )
    current_profile_episode = [
        t
        for t in same
        if t["device"] == f["device"] and t["new_device"] == "New" and t["proxy"]
    ]
    shared_fraud = bool(
        len(connected) >= 2
        and (testing or (historical_network and len(current_profile_episode) >= 2))
    )
    if packet["neighbors"]:
        ev(
            f"The same device profile occurs on {len({t['customer_id'] for t in packet['neighbors']})} other customers in the prior 30 days. A shared profile is not a unique device or proof of common ownership.",
            "device_neighbors",
            [t["id"] for t in packet["neighbors"][:20]],
            "support" if shared_fraud else "counter",
            group="network",
        )
    if shared_fraud:
        p = max(p, 0.86)
        if historical_network and not testing:
            pattern = "undocumented"
            affected = current_profile_episode
            ev(
                "Multiple prior confirmed undocumented cases on this profile combine with repeated new-device/proxy activity on the current and connected cards. This is corroborated network suspicion, not proof from profile sharing alone.",
                "corroborated_profile_pattern",
                [h["id"] for h in history_fraud]
                + [t["id"] for t in current_profile_episode],
                group="history",
            )
        affected += suspicious_neighbors
    else:
        connected = []
    mixed = len({t["channel"] for t in recent}) > 1
    flags = __import__("json").loads(f["match_flags"])
    if mixed and new_device and sum(v == "F" for v in flags.values()) >= 3 and p >= 0.6:
        pattern = "account_takeover"
        p += 0.06
        ev(
            "Mixed-channel activity, new-device status, and multiple encoded match anomalies support an account-takeover hypothesis; compromised credentials are not confirmed.",
            "mixed_channel_identity",
            [t["id"] for t in recent],
            group="identity",
        )
    disputed = trigger["trigger_type"] == "customer_report"
    if disputed:
        evidence.append(
            {
                "claim": "Organizer trigger contains a customer denial of the flagged transaction.",
                "source": "customer",
                "ref": "case_pack:" + trigger["case_id"],
                "entity_ids": [f["id"]],
            }
        )
        support.append("Customer disputes the flagged transaction.")
        groups.add("customer")
        if recurring:
            conflict = True
        else:
            p = max(p, 0.87)
    p = round(max(0.05, min(0.96, p)), 2)
    legitimate = bool(
        not disputed
        and p <= 0.15
        and typical
        and f["region"] in regions
        and len(baseline) >= 5
        and not testing
    )
    verdict = (
        "legitimate"
        if legitimate
        else ("fraud" if p >= 0.85 and (len(groups) >= 2 or disputed) else "uncertain")
    )
    if conflict:
        verdict = "uncertain"
        p = 0.45
    if verdict == "fraud" and pattern == "none":
        pattern = (
            "card_not_present_fraud"
            if f["channel"] == "online"
            else "out_of_region_use"
        )
    if verdict != "legitimate" and not affected:
        affected = [f]
    if verdict != "legitimate" and not any(t["id"] == f["id"] for t in affected):
        affected.append(f)
    if verdict == "legitimate":
        affected = []
        pattern = "none"
    affected = sorted(
        {t["id"]: t for t in affected}.values(), key=lambda t: (t["ts"], t["id"])
    )
    exposure = round(sum(abs(t["amount"]) for t in affected), 2)
    return {
        "probability": p,
        "verdict": verdict,
        "pattern": pattern,
        "affected": affected,
        "exposure": exposure,
        "evidence": evidence,
        "support": support,
        "counter": counter,
        "independent_evidence": 2 if legitimate else len(groups),
        "testing": testing,
        "recurring": recurring,
        "disputed": disputed,
        "conflict": conflict,
        "shared_fraud": shared_fraud,
        "connected_cards": connected,
        "history": relevant_history,
        "baseline_median": amount_median,
        "probability_method": "Transparent heuristic; not calibrated. Historical evaluation is required before calibration claims.",
        "next_evidence": "Verify whether the customer authorized the transaction; confirmation or denial changes policy actions. Escalate conflicting evidence.",
        "alternative": "A legitimate new device, travel, or recurring charge may explain the alert; compare the specific baseline evidence.",
    }
