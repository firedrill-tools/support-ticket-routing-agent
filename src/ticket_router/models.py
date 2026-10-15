"""Application input and output contracts."""

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Queue(str, Enum):
    BILLING = "billing"
    ACCOUNT = "account"
    PRODUCT = "product"
    SECURITY = "security"


class Action(str, Enum):
    ROUTE = "route"
    CLARIFY = "clarify"
    OUT_OF_SCOPE = "out_of_scope"


class Ticket(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    account_tier: str | None = Field(default=None, max_length=100)


class RoutingDecision(BaseModel):
    action: Action
    queue: Queue | None
    reason: str = Field(min_length=1, max_length=1000)
    clarifying_question: str | None = Field(default=None, max_length=500)

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


class RouteResult(BaseModel):
    ticket_id: str
    model: str
    decision: RoutingDecision
    usage: dict[str, int | float | None] | None = None
