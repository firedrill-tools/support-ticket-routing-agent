"""Exercise real Pydantic AI and OpenAI SDK code with an offline HTTP transport."""

import asyncio
import json
from pathlib import Path

import httpx2
from openai import AsyncOpenAI
from pydantic_ai.providers.openai import OpenAIProvider
import pytest

from ticket_router.models import Queue, Ticket
from ticket_router.router import RoutingRunError, route_ticket

ROOT = Path(__file__).resolve().parents[1]
VALID = {"action": "route", "queue": "billing", "reason": "The customer needs the renewal receipt", "clarifying_question": None}


def response(payload=VALID, *, status="completed", usage=True, refusal=False):
    return {"id": "resp_synthetic", "object": "response", "created_at": 1792070000,
            "model": "gpt-6.1-sol-synthetic-snapshot", "status": status, "error": None,
            "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
            "background": False, "output": [{"id": "msg_synthetic", "type": "message", "role": "assistant",
                "status": "completed", "content": [{"type": "refusal", "refusal": "Synthetic refusal"}] if refusal else
                [{"type": "output_text", "text": json.dumps(payload), "annotations": []}]}],
            "usage": {"input_tokens": 25, "output_tokens": 12, "total_tokens": 37,
                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}} if usage else None}


@pytest.fixture
def http_provider():
    clients = []

    def make(responses):
        requests = []

        def handler(request):
            assert request.url.host == "provider.synthetic.example"
            assert request.url.path == "/v1/responses"
            assert request.method == "POST"
            requests.append(json.loads(request.content))
            assert len(requests) <= len(responses), "Unexpected extra SDK request"
            item = responses[len(requests) - 1]
            if isinstance(item, int):
                return httpx2.Response(item, json={"error": {"message": "Synthetic provider unavailable", "type": "server_error", "code": "synthetic_failure"}})
            return httpx2.Response(200, json=item)

        transport = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        client = AsyncOpenAI(api_key="synthetic-not-a-secret", base_url="https://provider.synthetic.example/v1",
                             max_retries=0, http_client=transport)
        clients.append(client)
        return OpenAIProvider(openai_client=client), requests

    yield make
    for client in clients:
        asyncio.run(client.close())


def ticket():
    return Ticket.model_validate_json((ROOT / "data/tickets/ordinary-billing.json").read_text())


def test_native_responses_request_preserves_policy_identity_usage_and_actual_model(http_provider):
    provider, requests = http_provider([response()])
    result = route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert result.decision.queue is Queue.BILLING
    assert result.ticket_id == "NNS-1001"
    assert result.usage == {"requests": 1, "input_tokens": 25, "output_tokens": 12, "total_tokens": 37}
    assert result.observation.responses[0].model == "gpt-6.1-sol-synthetic-snapshot"
    assert result.observation.cost_usd is None
    assert len(result.input_sha256) == len(result.policy_sha256) == 64
    request = requests[0]
    assert request["model"] == "gpt-6.1-sol"
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["schema"]["additionalProperties"] is False
    assert request.get("tools", []) == []
    assert request["store"] is False
    prompt = json.dumps(request["input"])
    assert "NNS-1001" in prompt and "Security takes priority" in request["instructions"]
    assert "NNS-1002" not in prompt and "Scenario briefs" not in prompt


def test_actual_sdk_validation_retries_once_and_preserves_both_usage_observations(http_provider):
    provider, requests = http_provider([response({**VALID, "queue": None}), response()])
    result = route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert len(requests) == len(result.observation.responses) == 2
    assert result.usage == {"requests": 2, "input_tokens": 50, "output_tokens": 24, "total_tokens": 74}
    assert result.observation.sdk_usage["requests"] == 2


def test_persistent_invalid_output_exhausts_the_bound_without_a_decision(http_provider):
    provider, requests = http_provider([response({**VALID, "reason": "   "})] * 2)
    with pytest.raises(RoutingRunError) as error:
        route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert len(requests) == len(error.value.observation.responses) == 2
    assert error.value.observation.usage_complete is True
    assert not hasattr(error.value, "decision")


@pytest.mark.parametrize("status", ["incomplete", "in_progress", "cancelled", "failed"])
def test_nonfinal_response_cannot_complete_even_with_valid_json(http_provider, status):
    provider, requests = http_provider([response(status=status)] * 2)
    with pytest.raises(RoutingRunError) as error:
        route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert len(requests) <= 2
    assert error.value.observation.responses[-1].status == status
    assert error.value.observation.responses[-1].reported_usage["total_tokens"] == 37


def test_refusal_is_not_an_out_of_scope_routing_decision(http_provider):
    provider, requests = http_provider([response(refusal=True)] * 2)
    with pytest.raises(RoutingRunError) as error:
        route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert error.value.observation.responses[-1].finish_reason == "content_filter"
    assert 1 <= len(requests) <= 2


def test_missing_provider_usage_stays_unknown_instead_of_zero_cost(http_provider):
    provider, _ = http_provider([response(usage=False)])
    result = route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert result.usage is None
    assert result.observation.usage_complete is False
    assert result.observation.responses[0].reported_usage is None
    assert result.observation.sdk_usage["total_tokens"] == 0
    assert result.observation.cost_usd is None


def test_reported_zero_usage_is_retained_as_reported(http_provider):
    payload = response()
    payload["usage"].update(input_tokens=0, output_tokens=0, total_tokens=0)
    provider, _ = http_provider([payload])
    result = route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert result.observation.usage_complete is True
    assert result.usage["total_tokens"] == 0
    assert result.observation.cost_usd is None


def test_http_failure_has_no_success_and_no_invented_usage_or_hidden_retry(http_provider):
    provider, requests = http_provider([503])
    with pytest.raises(RoutingRunError) as error:
        route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert len(requests) == 1
    assert error.value.observation.responses == []
    assert error.value.observation.usage_complete is False
    assert error.value.http_status == 503
    assert error.value.provider_error_type == "ModelHTTPError"


@pytest.fixture(autouse=True)
def no_provider_environment(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)


def cli_with_provider(monkeypatch, provider):
    from functools import partial
    from ticket_router import cli
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setattr(cli, "route_ticket", partial(route_ticket, provider=provider))
    return cli


def test_cli_selected_case_emits_one_complete_result_and_keeps_manifest_out_of_prompt(http_provider, monkeypatch, capsys):
    provider, requests = http_provider([response()])
    cli = cli_with_provider(monkeypatch, provider)
    assert cli.main(["--case", "starter-receipt"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["dataset"]["dataset_id"] == "northstar-support-tickets"
    assert result["dataset"]["version"] == "1.0.0"
    assert result["dataset"]["profile"] == "starter"
    assert result["ticket_id"] == "NNS-1001"
    assert result["decision"]["queue"] == "billing"
    assert len(requests) == 1
    assert "dataset_id" not in json.dumps(requests[0])
    assert "case_id" not in json.dumps(requests[0])
    assert provider.client.is_closed() is False  # injected clients remain caller-owned


def test_cli_incomplete_response_emits_only_failure_evidence(http_provider, monkeypatch, capsys):
    provider, _ = http_provider([response(status="incomplete")] * 2)
    cli = cli_with_provider(monkeypatch, provider)
    assert cli.main(["--case", "starter-receipt"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"]["code"] == "model_failed"
    assert error["observation"]["responses"][-1]["status"] == "incomplete"
    assert error["observation"]["responses"][-1]["reported_usage"]["total_tokens"] == 37
    assert error["dataset"]["case_id"] == "starter-receipt"
    assert "decision" not in error


def test_case_listing_is_model_free_and_does_not_need_credentials(monkeypatch, capsys):
    from ticket_router import cli
    def forbidden(*args, **kwargs):
        pytest.fail("Listing a dataset must not start a model run")
    monkeypatch.setattr(cli, "route_ticket", forbidden)
    assert cli.main(["--list-cases"]) == 0
    assert json.loads(capsys.readouterr().out)["case_count"] == 16


def test_changed_case_is_rejected_before_a_provider_request(http_provider, monkeypatch, capsys, tmp_path):
    import shutil
    shutil.copytree(ROOT / "data", tmp_path / "data")
    source = tmp_path / "data/tickets/ordinary-billing.json"
    source.write_text(source.read_text().replace("$48", "$480"))
    provider, requests = http_provider([])
    cli = cli_with_provider(monkeypatch, provider)
    assert cli.main(["--case", "starter-receipt", "--manifest", str(tmp_path / "data/manifest.json")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "digest mismatch" in json.loads(captured.err)["error"]["message"]
    assert requests == []


def test_missing_credentials_do_not_produce_a_decision(http_provider, monkeypatch, capsys):
    provider, requests = http_provider([])
    cli = cli_with_provider(monkeypatch, provider)
    monkeypatch.delenv("OPENAI_API_KEY")
    assert cli.main(["--case", "starter-receipt"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "OPENAI_API_KEY" in json.loads(captured.err)["error"]["message"]
    assert requests == []


def test_stdin_retains_ticket_identity_without_invented_dataset_metadata(http_provider, monkeypatch, capsys):
    import io
    import sys
    provider, requests = http_provider([response()])
    cli = cli_with_provider(monkeypatch, provider)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(ticket().model_dump_json().encode()), encoding="utf-8"))
    assert cli.main(["--stdin"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["ticket_id"] == "NNS-1001"
    assert json.loads(captured.out)["dataset"] is None
    assert len(requests) == 1


def test_oversized_input_is_bounded_before_model_execution(http_provider, monkeypatch, capsys, tmp_path):
    from ticket_router.datasets import MAX_INPUT_BYTES
    path = tmp_path / "too-large.json"
    path.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
    provider, requests = http_provider([])
    cli = cli_with_provider(monkeypatch, provider)
    assert cli.main(["--ticket", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "128 KiB" in json.loads(captured.err)["error"]["message"]
    assert requests == []


@pytest.mark.parametrize("failed", [False, True])
def test_default_client_closes_on_success_and_failure_without_hidden_http_retries(http_provider, monkeypatch, failed):
    from ticket_router import router
    provider, requests = http_provider([503] if failed else [response()])
    def client_factory(**options):
        assert options == {"max_retries": 0, "timeout": 30.0}
        return provider.client
    monkeypatch.setattr(router, "AsyncOpenAI", client_factory)
    if failed:
        with pytest.raises(RoutingRunError):
            route_ticket(ticket(), model="openai:gpt-6.1-sol")
    else:
        route_ticket(ticket(), model="openai:gpt-6.1-sol")
    assert len(requests) == 1
    assert provider.client.is_closed() is True


@pytest.mark.parametrize("model", ["anthropic:synthetic", "openai:", "openai:   ", "openai: gpt-6.1-sol"])
def test_invalid_model_configuration_fails_before_http(http_provider, model):
    provider, requests = http_provider([])
    with pytest.raises(ValueError, match="OpenAI model identifier"):
        route_ticket(ticket(), model=model, provider=provider)
    assert requests == []


@pytest.mark.parametrize("decision", [
    {"action": "clarify", "queue": None, "reason": "The request does not say what changed", "clarifying_question": "What are you trying to do?"},
    {"action": "out_of_scope", "queue": None, "reason": "Travel arrangements are outside product support", "clarifying_question": None},
])
def test_structured_clarification_and_scope_decisions_are_valid_successes(http_provider, decision):
    provider, _ = http_provider([response(decision)])
    result = route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider)
    assert result.decision.action.value == decision["action"]
    assert result.decision.queue is None
    assert result.observation.responses[-1].status == "completed"


def test_custom_policy_is_the_actual_transmitted_and_hashed_configuration(http_provider, tmp_path):
    from hashlib import sha256
    path = tmp_path / "policy.txt"
    path.write_text("Synthetic policy variant: explain the routing choice; never perform an account action.\n")
    provider, requests = http_provider([response()])
    result = route_ticket(ticket(), model="openai:gpt-6.1-sol", provider=provider, policy_path=path)
    assert "Synthetic policy variant" in requests[0]["instructions"]
    assert "Security takes priority" not in requests[0]["instructions"]
    assert result.policy_sha256 == sha256(path.read_bytes()).hexdigest()
