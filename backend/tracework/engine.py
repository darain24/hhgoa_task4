import asyncio
import copy
import json
import time

from . import analysis, llm, retrieval, scoring, store, tigergraph
from .config import TG_URL
from .models import SAR, Answer, CaseRecord, EvidenceRequest, Recommendations
from .policy import Situation, decide

RUN_LOCK = asyncio.Lock()


def situation(a, response=None):
    return Situation(
        probability=a["probability"],
        exposure=a["exposure"],
        verdict=a["verdict"],
        response=response,
        disputed=a["disputed"],
        recurring=a["recurring"],
        card_testing=a["testing"],
        shared_fraud=a["shared_fraud"],
        undocumented=a["pattern"] == "undocumented",
        conflict=a["conflict"],
        independent_evidence=a["independent_evidence"],
    )


def build_answer(trigger, a, packet, response=None, previous=None, tokens=0, latency=0):
    s = situation(a, response)
    if not response and a["disputed"] and not a["conflict"] and not a["recurring"]:
        s.response = "denied"
    actions = decide(s)
    final_names = {x.action for x in actions}
    status = (
        "escalated"
        if "ESCALATE_TO_ANALYST" in final_names
        else (
            "closed_legitimate"
            if a["verdict"] == "legitimate"
            else ("closed_fraud" if a["verdict"] == "fraud" else "open")
        )
    )
    f = packet["flagged"]
    affected = a["affected"]
    ids = [t["id"] for t in affected]
    summary = (
        f"{trigger['case_id']}: {a['verdict']} assessment for {trigger['card_id']}. "
    )
    summary += f"{len(ids)} transaction(s) are included in the suspected episode, with ${a['exposure']:,.2f} potential exposure. "
    summary += (
        "Customer report conflicts with recurring-amount evidence; analyst review is required."
        if a["conflict"]
        else (
            "Verification remains necessary before a definitive conclusion."
            if a["verdict"] == "uncertain"
            else "The evidence and policy determine the recommended actions below."
        )
    )
    summary += " Probability is an uncalibrated heuristic."
    record = CaseRecord(
        status=status,
        verdict=a["verdict"],
        fraud_probability=a["probability"],
        pattern=a["pattern"],
        pattern_description="Repeated unusual online activity is connected across customers by a shared profile, with corroborating transaction behavior. The combination does not fit a documented pattern."
        if a["pattern"] == "undocumented"
        else "",
        affected_txn_ids=ids,
        first_suspicious_txn_id=ids[0] if ids else "",
        connected_card_ids=a["connected_cards"],
        connected_device_profiles=[f["device"]]
        if a["connected_cards"] and f["device"]
        else [],
        exposure_usd=a["exposure"],
        evidence=a["evidence"],
        similar_prior_cases=[h["id"] for h in a["history"]],
        summary=summary,
    )
    should_file = "FILE_REPORT" in final_names
    sar = SAR(
        reason="§3a: evidence does not meet report conditions; maintain the internal case as needed."
    )
    if should_file:
        dates = [
            min(t["ts"] for t in affected)[:10],
            max(t["ts"] for t in affected)[:10],
        ]
        narrative = (
            f"Customer {f['customer_id']} is associated with card {f['card_id']}. "
            f"The investigation covers {len(ids)} suspected transactions between {dates[0]} and {dates[1]}. "
            f"The flagged activity occurred through the {f['channel']} channel, with billing-region code {f['region'] or 'unavailable'}. "
            f"The suspected pattern is {a['pattern'].replace('_', ' ')}. "
            f"The cited transaction and investigation evidence supports a {a['verdict']} assessment; model scores alone do not establish fraud. "
            f"The total identified amount is ${a['exposure']:.2f}. "
            + (
                "A simulated customer response is recorded separately and must not be represented as an actual customer contact. "
                if response
                else "The original trigger and supporting evidence are retained in the case record. "
            )
            + "Reporting is recommended under the supplied policy §3a, subject to L2 approval. No regulatory filing or card action has been executed by this workbench."
        )
        sar = SAR(
            file=True,
            reason="§3a: strong suspicion and exposure or corroborated network conditions require L2 review.",
            narrative=narrative,
            subjects=[f["customer_id"], f["card_id"]] + a["connected_cards"],
            total_amount_usd=a["exposure"],
            activity_dates=dates,
        )
    requests = previous.evidence_requests if previous else []
    if response:
        requests = requests + [
            EvidenceRequest(
                type="customer_validation",
                asked_after_step=len(store.events(trigger["case_id"])),
                assumed_response="SIMULATED: "
                + {
                    "confirmed": "Customer confirms authorization.",
                    "denied": "Customer denies authorization.",
                    "no_reply": "No reply after a simulated 24-hour interval.",
                    "conflicting": "Customer response conflicts with other evidence.",
                }[response],
            )
        ]
    initial = previous.next_best_actions.initial if previous else actions
    stop = (
        "R8: pause and escalate conflicting evidence."
        if a["conflict"]
        else "Verification response settles the question under §6."
        if response in ("confirmed", "denied")
        else "§6: at least two independent findings support a threshold decision."
        if a["verdict"] != "uncertain" and a["independent_evidence"] >= 2
        else "Investigation paused: evidence or analyst review is pending; no definitive closure is claimed."
    )
    return Answer(
        case_id=trigger["case_id"],
        case=record,
        evidence_requests=requests,
        next_best_actions=Recommendations(
            initial=initial,
            final=actions,
            what_changed=f"Simulated {response} response changed the evidence and policy assessment."
            if response
            else "nothing",
        ),
        sar=sar,
        stop_reason=stop,
        tool_calls=packet["tool_calls"],
        tokens=tokens,
        latency_s=round(latency, 3),
    )


def graph_view(packet, a):
    f = packet["flagged"]
    nodes = []
    edges = []
    seen = set()

    def node(id, label, kind, **extra):
        if id not in seen:
            nodes.append({"id": id, "label": label, "kind": kind, **extra})
            seen.add(id)

    def edge(source, target, label):
        edges.append(
            {
                "id": f"{source}-{target}-{label}",
                "source": source,
                "target": target,
                "label": label,
            }
        )

    node(f["customer_id"], f["customer_id"], "customer")
    node(f["card_id"], f["card_id"], "card")
    edge(f["customer_id"], f["card_id"], "owns")
    display = packet["timeline"][-3:]
    if not any(t["id"] == f["id"] for t in display):
        display.append(f)
    for t in display:
        node(t["card_id"], t["card_id"], "card")
        node(
            t["id"],
            f"${abs(t['amount']):,.2f}",
            "transaction",
            flagged=t["id"] == f["id"],
            timestamp=t["ts"],
            risk=t["risk"],
        )
        edge(t["card_id"], t["id"], "transaction")
    if f["device"]:
        node("device:" + f["device"], f["device"].split(" | ")[0][:26], "device")
        edge(f["id"], "device:" + f["device"], "profile")
        other = {}
        for t in packet["neighbors"]:
            if t["card_verified"]:
                other[t["card_id"]] = t
        for t in list(other.values())[:3]:
            node(t["card_id"], t["card_id"], "connected")
            edge("device:" + f["device"], t["card_id"], "shared profile ≠ fraud")
    else:
        node("region:" + f["region"], "Region " + (f["region"] or "unknown"), "region")
        edge(f["id"], "region:" + f["region"], "billed in")
    return {"nodes": nodes, "edges": edges}


async def investigate(case_id, use_llm=True):
    async with RUN_LOCK:
        record = store.get_case(case_id)
        if record["result"]:
            return record  # Resume is idempotent; evidence updates are separate.
        start = time.monotonic()
        with store.connect() as c:
            c.execute(
                "UPDATE cases SET state='running',error=NULL WHERE id=?", (case_id,)
            )
        try:
            trigger = record["trigger"]
            store.event(
                case_id,
                "trigger",
                "Investigation opened",
                {"trigger": trigger["trigger_type"]},
            )
            packet = await asyncio.to_thread(analysis.collect, trigger)
            store.event(
                case_id,
                "evidence",
                "Transaction history and relationships retrieved",
                {
                    "source": "local_sqlite",
                    "cutoff": packet["cutoff"],
                    "transactions": len(packet["timeline"]),
                },
            )
            grounding_error = None
            if TG_URL:
                try:
                    packet = await retrieval.ground(packet, trigger)
                    store.event(
                        case_id,
                        "graph",
                        "TigerGraph evidence and vector context verified",
                        {"source": "tigergraph"},
                    )
                except Exception as exc:
                    grounding_error = str(exc)[:250]
                    store.event(
                        case_id,
                        "warning",
                        "TigerGraph grounding failed; local analysis explicitly retained",
                        {"error": grounding_error},
                    )
            a = analysis.assess(packet, trigger)
            advisory = scoring.predict(trigger["flagged_txn_id"])
            if packet["source"] == "tigergraph":
                for ev in a["evidence"]:
                    if ev["source"] == "external":
                        ev.update(
                            source="graph",
                            ref=ev["ref"].replace(
                                "local_sqlite:", "tigergraph:verified_derivation:"
                            ),
                        )
                for doc in packet.get("graph_documents", [])[:3]:
                    a["evidence"].append(
                        {
                            "claim": doc["text"][:1200],
                            "source": "document",
                            "ref": "tigergraph:vector:" + doc["id"],
                            "entity_ids": [],
                        }
                    )
            store.event(
                case_id,
                "assessment",
                "Competing explanations assessed",
                {
                    "verdict": a["verdict"],
                    "probability": a["probability"],
                    "calibrated": False,
                },
            )
            synthesis = None
            model_error = None
            tokens = 0
            if use_llm:
                store.event(
                    case_id,
                    "model",
                    "Local evidence reviewer started",
                    {"model": llm.MODEL},
                )
                try:
                    synthesis = await llm.synthesize(a)
                    tokens = synthesis["tokens"]
                    store.event(
                        case_id,
                        "model",
                        "Local reviewer completed",
                        {
                            "tokens": tokens,
                            "cached": synthesis["cached"],
                            "next_tool": synthesis["synthesis"]["next_tool"],
                        },
                    )
                    # Tool selection is bounded: execute only reviewed read-only follow-ups.
                    selected = synthesis["synthesis"]["next_tool"]
                    if selected != "none":
                        await asyncio.to_thread(followup, selected, packet, trigger)
                        packet["tool_calls"] += 1
                        store.event(
                            case_id,
                            "tool",
                            "Agent selected " + selected,
                            {
                                "tool": selected,
                                "source": "local_sqlite",
                                "read_only": True,
                            },
                        )
                except Exception as exc:
                    model_error = f"{type(exc).__name__}: {str(exc)[:180]}"
                    store.event(
                        case_id,
                        "warning",
                        "Local model unavailable; deterministic analysis retained",
                        {"error": model_error},
                    )
            answer = build_answer(
                trigger, a, packet, tokens=tokens, latency=time.monotonic() - start
            )
            store.event(
                case_id,
                "policy",
                "Policy and approval routes evaluated",
                {"actions": [x.model_dump() for x in answer.next_best_actions.final]},
            )
            tg_error = grounding_error
            if TG_URL:
                try:
                    graph_id = await tigergraph.persist(answer.model_dump())
                    answer.case.written_to_graph = True
                    answer.case.graph_case_id = graph_id
                    store.event(
                        case_id,
                        "persistence",
                        "TigerGraph case read-back verified",
                        {"graph_case_id": graph_id},
                    )
                except Exception as exc:
                    tg_error = str(exc)[:250]
            detail = {
                "assessment": a,
                "statistical_advisory": advisory,
                "packet": packet,
                "graph": graph_view(packet, a),
                "synthesis": synthesis,
                "model_error": model_error,
                "tigergraph_error": tg_error,
                "mode": "TigerGraph grounded"
                if packet["source"] == "tigergraph"
                else "local analysis · TigerGraph evidence pending",
                "simulated": False,
                "validation": validate(answer),
            }
            store.save(case_id, answer.model_dump(), detail)
            store.event(
                case_id,
                "complete",
                "Investigation saved",
                {
                    "state": answer.case.status,
                    "written_to_graph": answer.case.written_to_graph,
                },
            )
            return store.get_case(case_id)
        except Exception as exc:
            with store.connect() as c:
                c.execute(
                    "UPDATE cases SET state='failed',error=? WHERE id=?",
                    (str(exc)[:400], case_id),
                )
            store.event(
                case_id, "error", "Investigation failed", {"error": str(exc)[:400]}
            )
            raise


def followup(tool, packet, trigger):
    with store.connect() as c:
        if tool == "prior_cases":
            r = c.execute(
                "SELECT id,outcome,pattern FROM history WHERE customer_id=? AND closed_at<? LIMIT 20",
                (trigger["customer_id"], trigger["opened_at"]),
            ).fetchall()
        elif tool == "device_neighbors":
            r = c.execute(
                "SELECT id,card_id FROM transactions WHERE device=? AND device!=? AND ts<=? LIMIT 20",
                (packet["flagged"]["device"], "", trigger["opened_at"]),
            ).fetchall()
        else:
            r = c.execute(
                "SELECT region,count(*) AS count FROM transactions WHERE customer_id=? AND ts<=? GROUP BY region",
                (trigger["customer_id"], trigger["opened_at"]),
            ).fetchall()
    packet["agent_followup"] = {"tool": tool, "result": [dict(x) for x in r]}
    return packet["agent_followup"]


def validate(answer):
    from .policy import validate_actions

    errors = validate_actions(answer.next_best_actions.final, answer.case.exposure_usd)
    with store.connect() as c:
        amounts = []
        for id in answer.case.affected_txn_ids:
            r = c.execute(
                "SELECT amount FROM transactions WHERE id=?", (id,)
            ).fetchone()
            if not r:
                errors.append("Missing transaction " + id)
            else:
                amounts.append(abs(r[0]))
        if round(sum(amounts), 2) != round(answer.case.exposure_usd, 2):
            errors.append("Exposure does not match affected transactions")
        for id in answer.case.connected_card_ids:
            if not c.execute(
                "SELECT 1 FROM transactions WHERE card_id=? AND card_verified=1 LIMIT 1",
                (id,),
            ).fetchone():
                errors.append("Unverified card " + id)
        for id in answer.case.similar_prior_cases:
            if not c.execute("SELECT 1 FROM history WHERE id=?", (id,)).fetchone():
                errors.append("Unknown historical case " + id)
    return {
        "schema_valid": True,
        "errors": errors,
        "submission_ready": not errors
        and answer.case.written_to_graph
        and any(
            e.source == "graph" and e.ref.startswith("tigergraph:")
            for e in answer.case.evidence
        )
        and any(
            e.source == "document" and e.ref.startswith("tigergraph:vector:")
            for e in answer.case.evidence
        ),
        "limitations": [
            "TigerGraph evidence retrieval and vector grounding are not verified."
        ]
        if not answer.case.written_to_graph
        else [],
    }


async def respond(case_id, response, note=""):
    async with RUN_LOCK:
        r = store.get_case(case_id)
        if not r["result"]:
            raise ValueError("Run the investigation before adding evidence")
        old = Answer.model_validate(r["result"])
        detail = copy.deepcopy(r["detail"])
        a = detail["assessment"]
        packet = detail["packet"]
        if detail.get("last_response") == {"response": response, "note": note}:
            return r
        if response == "confirmed":
            a.update(
                verdict="legitimate",
                probability=0.08,
                pattern="none",
                affected=[],
                exposure=0,
                connected_cards=[],
                shared_fraud=False,
                conflict=False,
            )
        elif response == "denied":
            a.update(verdict="fraud", probability=0.92, conflict=False)
            if not a["affected"]:
                a["affected"] = [packet["flagged"]]
                a["exposure"] = abs(packet["flagged"]["amount"])
            if a["pattern"] == "none":
                a["pattern"] = (
                    "card_not_present_fraud"
                    if packet["flagged"]["channel"] == "online"
                    else "out_of_region_use"
                )
        else:
            a.update(
                verdict="uncertain", probability=0.5, conflict=response == "conflicting"
            )
        a["evidence"].append(
            {
                "claim": f"SIMULATED customer response: {response}. " + note,
                "source": "customer",
                "ref": f"evidence_request:{len(old.evidence_requests) + 1}",
                "entity_ids": [packet["flagged"]["id"]],
            }
        )
        answer = build_answer(
            r["trigger"], a, packet, response, old, old.tokens, old.latency_s
        )
        detail.update(
            simulated=True,
            last_response={"response": response, "note": note},
            validation=validate(answer),
            synthesis=None,
        )
        if TG_URL:
            try:
                gid = await tigergraph.persist(answer.model_dump())
                answer.case.written_to_graph = True
                answer.case.graph_case_id = gid
            except Exception as exc:
                detail["tigergraph_error"] = str(exc)[:250]
        store.save(case_id, answer.model_dump(), detail)
        store.event(
            case_id,
            "response",
            "Simulated evidence received",
            {
                "response": response,
                "note": note,
                "simulated": True,
                "actions": [x.model_dump() for x in answer.next_best_actions.final],
            },
        )
        return store.get_case(case_id)


def scenarios(case_id):
    r = store.get_case(case_id)
    if not r["detail"]:
        raise ValueError("Run an investigation first")
    results = {}
    for response in ["confirmed", "denied", "no_reply", "conflicting"]:
        a = copy.deepcopy(r["detail"]["assessment"])
        s = situation(a, response)
        s.conflict = response == "conflicting"
        if response == "confirmed":
            s.verdict = "legitimate"
            s.exposure = 0
            s.probability = 0.08
            s.shared_fraud = False
        elif response == "denied":
            s.verdict = "fraud"
            s.probability = 0.92
        else:
            s.verdict = "uncertain"
        results[response] = [x.model_dump() for x in decide(s)]
    return {"hypothetical": True, "persisted": False, "branches": results}


async def review(case_id):
    async with RUN_LOCK:
        record = store.get_case(case_id)
        if not record["result"]:
            raise ValueError("Run the investigation first")
        start = time.monotonic()
        detail = record["detail"]
        store.event(
            case_id, "model", "Local evidence reviewer started", {"model": llm.MODEL}
        )
        try:
            synthesis = await llm.synthesize(detail["assessment"])
        except Exception as exc:
            store.event(
                case_id, "warning", "Local reviewer failed", {"error": str(exc)[:200]}
            )
            raise ValueError("Local model review failed: " + str(exc)[:200]) from exc
        detail["synthesis"] = synthesis
        detail["model_error"] = None
        selected = synthesis["synthesis"]["next_tool"]
        if selected != "none":
            result = await asyncio.to_thread(
                followup, selected, detail["packet"], record["trigger"]
            )
            store.event(
                case_id,
                "tool",
                "Agent selected " + selected,
                {"tool": selected, "result": result, "source": "local_sqlite"},
            )
            record["result"]["tool_calls"] += 1
        record["result"]["tokens"] += synthesis["tokens"]
        record["result"]["latency_s"] = round(
            record["result"]["latency_s"] + time.monotonic() - start, 3
        )
        # Review changes interpretation only, not policy decisions or their approval revision.
        with store.connect() as c:
            c.execute(
                "UPDATE cases SET result_json=?,detail_json=?,updated_at=? WHERE id=?",
                (
                    json.dumps(record["result"]),
                    json.dumps(detail),
                    store.now(),
                    case_id,
                ),
            )
        store.event(
            case_id,
            "model",
            "Local evidence reviewer completed",
            {"tokens": synthesis["tokens"], "cached": synthesis["cached"]},
        )
        return store.get_case(case_id)
