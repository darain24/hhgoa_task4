from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Pattern = Literal[
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none",
]
ActionName = Literal[
    "ALLOW_TRANSACTION",
    "DECLINE_TRANSACTION",
    "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "BLOCK_CARD",
    "BLOCK_ALL_CARDS",
    "GENERATE_REPORT",
    "CREATE_CASE",
    "FILE_REPORT",
    "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Action(StrictModel):
    action: ActionName
    route: Literal["auto", "L1", "L2"]
    reason: str


class Evidence(StrictModel):
    claim: str
    source: Literal["graph", "document", "customer", "external"]
    ref: str
    entity_ids: list[str] = Field(default_factory=list)


class CaseRecord(StrictModel):
    status: Literal["open", "closed_fraud", "closed_legitimate", "escalated"]
    verdict: Literal["fraud", "legitimate", "uncertain"]
    fraud_probability: float = Field(ge=0, le=1)
    pattern: Pattern
    pattern_description: str = ""
    affected_txn_ids: list[str] = Field(default_factory=list)
    first_suspicious_txn_id: str = ""
    connected_card_ids: list[str] = Field(default_factory=list)
    connected_device_profiles: list[str] = Field(default_factory=list)
    exposure_usd: float = Field(ge=0)
    evidence: list[Evidence]
    similar_prior_cases: list[str]
    summary: str
    written_to_graph: bool = False
    graph_case_id: str = ""


class SAR(StrictModel):
    file: bool = False
    reason: str
    narrative: str = ""
    subjects: list[str] = Field(default_factory=list)
    total_amount_usd: float = 0
    activity_dates: list[str] = Field(default_factory=list)


class Recommendations(StrictModel):
    initial: list[Action]
    final: list[Action]
    what_changed: str = "nothing"


class EvidenceRequest(StrictModel):
    type: Literal["customer_validation", "step_up_auth", "analyst_info"]
    asked_after_step: int = Field(ge=0)
    assumed_response: str


class Answer(StrictModel):
    case_id: str
    case: CaseRecord
    evidence_requests: list[EvidenceRequest] = Field(default_factory=list)
    next_best_actions: Recommendations
    sar: SAR
    stop_reason: str
    tool_calls: int = Field(ge=0)
    tokens: int = Field(ge=0)
    latency_s: float = Field(ge=0)

    @model_validator(mode="after")
    def consistency(self):
        c = self.case
        if len(set(c.affected_txn_ids)) != len(c.affected_txn_ids):
            raise ValueError("Duplicate affected transactions")
        if c.verdict == "legitimate" and (
            c.affected_txn_ids or c.exposure_usd or self.sar.file
        ):
            raise ValueError("Legitimate cases cannot have fraud exposure or SAR")
        if self.sar.file != any(
            a.action == "FILE_REPORT" for a in self.next_best_actions.final
        ):
            raise ValueError("SAR and final actions disagree")
        if not self.sar.file and (
            self.sar.narrative
            or self.sar.subjects
            or self.sar.total_amount_usd
            or self.sar.activity_dates
        ):
            raise ValueError("Non-filing SAR fields must be empty")
        if (
            not self.evidence_requests
            and self.next_best_actions.initial != self.next_best_actions.final
        ):
            raise ValueError("Actions cannot change without recorded evidence")
        if c.written_to_graph != bool(c.graph_case_id):
            raise ValueError("Graph persistence fields disagree")
        if c.pattern == "undocumented" and not c.pattern_description:
            raise ValueError("Undocumented pattern requires description")
        return self


class ResponseInput(StrictModel):
    response: Literal["confirmed", "denied", "no_reply", "conflicting"]
    note: str = Field(default="", max_length=1000)
    simulated: Literal[True] = True


class ApprovalInput(StrictModel):
    action: ActionName
    route: Literal["L1", "L2"]
    decision_revision: int = Field(ge=1)


class InvestigationInput(StrictModel):
    use_llm: bool = True
