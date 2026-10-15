import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ticket_router.models import Action, Queue, RoutingDecision, Ticket
from ticket_router.router import route_ticket


ROOT = Path(__file__).resolve().parents[1]


def test_all_sample_tickets_follow_input_contract() -> None:
    files = sorted((ROOT / "data" / "tickets").glob("*.json"))
    assert len(files) == 5
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


def test_router_returns_framework_usage_and_preserves_ticket_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic_ai.usage import RunUsage

    class FakeResult:
        output = RoutingDecision(action=Action.ROUTE, queue=Queue.BILLING, reason="Receipt request")
        usage = RunUsage(requests=1, input_tokens=25, output_tokens=12)

    class FakeAgent:
        def __init__(self, model: str, **kwargs: object) -> None:
            assert model == "openai:gpt-6.1-sol"
            assert kwargs["output_type"] is RoutingDecision

        def run_sync(self, prompt: str) -> FakeResult:
            assert "NNS-1001" in prompt
            return FakeResult()

    monkeypatch.setattr("ticket_router.router.Agent", FakeAgent)
    ticket = Ticket.model_validate_json((ROOT / "data/tickets/ordinary-billing.json").read_text())
    outcome = route_ticket(ticket, model="openai:gpt-6.1-sol")
    assert outcome.ticket_id == ticket.ticket_id
    assert outcome.usage == {"requests": 1, "input_tokens": 25, "output_tokens": 12, "total_tokens": 37}
