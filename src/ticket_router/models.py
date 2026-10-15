"""Application input and output contracts."""

from enum import Enum

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Queue(str, Enum):
    BILLING = "billing"
    ACCOUNT = "account"
    PRODUCT = "product"
    SECURITY = "security"


class Action(str, Enum):
    ROUTE = "route"
    CLARIFY = "clarify"
    OUT_OF_SCOPE = "out_of_scope"


class Ticket(Contract):
    ticket_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    account_tier: str | None = Field(default=None, max_length=100)

    @field_validator("ticket_id", "subject", "body", "account_tier")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Ticket fields must contain non-whitespace text or an explicit null tier")
        return value


class RoutingDecision(Contract):
    action: Action
    queue: Queue | None
    reason: str = Field(min_length=1, max_length=1000)
    clarifying_question: str | None = Field(default=None, max_length=500)

    @field_validator("reason", "clarifying_question")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Reasons and questions must contain non-whitespace text")
        return value

    @model_validator(mode="after")
    def check_consistency(self) -> "RoutingDecision":
        if self.action is Action.ROUTE and self.queue is None:
            raise ValueError("A routed ticket needs a queue")
        if self.action is not Action.ROUTE and self.queue is not None:
            raise ValueError("Only routed tickets may have a queue")
        if self.action is Action.CLARIFY and not self.clarifying_question:
            raise ValueError("Clarification needs a question")
        if self.action is not Action.CLARIFY and self.clarifying_question is not None:
            raise ValueError("Only clarification may include a question")
        return self


class DatasetSelection(Contract):
    dataset_id: str
    version: str
    profile: str
    case_id: str
    source_sha256: str


class ResponseObservation(Contract):
    model: str | None
    response_id: str | None
    status: str | None
    finish_reason: str | None
    state: str
    reported_usage: dict[str, Any] | None


class RunObservation(Contract):
    responses: list[ResponseObservation]
    usage_complete: bool
    sdk_usage: dict[str, int] | None = None
    cost_usd: None = None


class RouteResult(Contract):
    ticket_id: str
    model: str
    decision: RoutingDecision
    usage: dict[str, int | float | None] | None = None
    observation: RunObservation
    input_sha256: str
    policy_sha256: str
    dataset: DatasetSelection | None = None
