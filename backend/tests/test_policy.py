import pytest
from tracework.policy import Situation, decide, route, validate_actions


def names(s):
    return {a.action for a in decide(s)}


@pytest.mark.parametrize(
    "amount,expected", [(2499.99, "L1"), (2500, "L1"), (2500.01, "L2")]
)
def test_block_approval_boundary(amount, expected):
    assert route("BLOCK_CARD", amount) == expected


@pytest.mark.parametrize(
    "amount,sar", [(999.99, False), (1000, False), (1000.01, True)]
)
def test_reporting_threshold(amount, sar):
    assert (
        "FILE_REPORT" in names(Situation(0.92, amount, "fraud", response="denied"))
    ) == sar


@pytest.mark.parametrize(
    "amount,escalate", [(499.99, False), (500, False), (500.01, True)]
)
def test_uncertain_escalation(amount, escalate):
    assert ("ESCALATE_TO_ANALYST" in names(Situation(0.5, amount))) == escalate


def test_weak_signal_never_blocks():
    n = names(Situation(0.45, 700))
    assert "VERIFY_WITH_CUSTOMER" in n
    assert "BLOCK_CARD" not in n
    assert "ESCALATE_TO_ANALYST" in n


def test_confirmation_closes_without_sar():
    n = names(Situation(0.1, 0, "legitimate", response="confirmed"))
    assert "CLOSE_NO_FRAUD" in n
    assert "FILE_REPORT" not in n


def test_no_reply_does_not_decline_unknown_authorization():
    assert "DECLINE_TRANSACTION" not in names(Situation(0.5, 600, response="no_reply"))
    assert "DECLINE_TRANSACTION" in names(
        Situation(0.5, 600, response="no_reply", pending_authorization=True)
    )


def test_conflict_escalates_even_with_customer_confirmation():
    n = names(Situation(0.1, 0, response="confirmed", conflict=True))
    assert "ESCALATE_TO_ANALYST" in n
    assert "CLOSE_NO_FRAUD" not in n


def test_card_testing_has_two_actions():
    n = names(Situation(0.89, 100, card_testing=True))
    assert {"DECLINE_TRANSACTION", "STEP_UP_AUTH"} <= n
    assert "BLOCK_CARD" not in n


def test_card_testing_cleared_condition():
    assert "BLOCK_CARD" in names(
        Situation(0.89, 101, card_testing=True, cleared_over_100=True)
    )


def test_shared_profile_alone_not_report():
    assert "FILE_REPORT" not in names(Situation(0.4, 100))


def test_shared_fraud_report_routes():
    actions = decide(Situation(0.9, 100, "fraud", shared_fraud=True))
    assert {"CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS"} <= {
        a.action for a in actions
    }
    assert not validate_actions(actions, 100)


def test_recurring_dispute_no_block():
    n = names(Situation(0.4, 49, disputed=True, recurring=True))
    assert {"CREATE_CASE", "VERIFY_WITH_CUSTOMER", "WARN_CUSTOMER"} <= n
    assert "BLOCK_CARD" not in n


def test_undocumented_escalates():
    n = names(Situation(0.9, 100, "fraud", undocumented=True))
    assert {"CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST"} <= n
