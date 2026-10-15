import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ticket_router.models import Action, Queue, RoutingDecision, Ticket


ROOT = Path(__file__).resolve().parents[1]


def test_all_sample_tickets_follow_input_contract() -> None:
    files = sorted((ROOT / "data" / "tickets").glob("*.json"))
    assert len(files) == 16
    ids = [Ticket.model_validate_json(path.read_text(encoding="utf-8")).ticket_id for path in files]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "route", "queue": None, "reason": "clear"},
        {"action": "clarify", "queue": "billing", "reason": "unclear", "clarifying_question": "Which charge?"},
        {"action": "clarify", "queue": None, "reason": "unclear"},
        {"action": "out_of_scope", "queue": None, "reason": "unrelated", "clarifying_question": "Why?"},
    ],
)
def test_impossible_decisions_are_rejected(payload: dict) -> None:
    with pytest.raises(ValidationError):
        RoutingDecision.model_validate(payload)


def test_valid_route_and_clarification() -> None:
    route = RoutingDecision(action=Action.ROUTE, queue=Queue.SECURITY, reason="Unknown sign-in")
    clarify = RoutingDecision(
        action=Action.CLARIFY,
        queue=None,
        reason="Problem is unspecified",
        clarifying_question="What changed?",
    )
    assert route.queue is Queue.SECURITY
    assert clarify.clarifying_question == "What changed?"


def test_sample_data_is_json_without_credentials() -> None:
    for path in (ROOT / "data" / "tickets").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert set(payload) == {"ticket_id", "subject", "body", "account_tier"}



@pytest.mark.parametrize("field", ["ticket_id", "subject", "body", "account_tier"])
def test_blank_ticket_fields_do_not_become_model_input(field: str) -> None:
    payload = {"ticket_id": "NNS-1", "subject": "Receipt", "body": "Need a receipt", "account_tier": "team"}
    payload[field] = " \t\n"
    with pytest.raises(ValidationError):
        Ticket.model_validate(payload)


def test_whitespace_question_and_unexpected_action_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RoutingDecision(action=Action.CLARIFY, queue=None, reason="Missing details", clarifying_question="   ")
    with pytest.raises(ValidationError):
        RoutingDecision.model_validate({"action": "route", "queue": "billing", "reason": "Receipt", "refund_executed": True})
