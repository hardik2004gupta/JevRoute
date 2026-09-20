"""ApplicationState: the state legitimately available to the control plane."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApplicationState(BaseModel):
    """Compact, control-plane-visible representation of a support ticket request.

    Only information legitimately available to the routing layer is included.
    The Jev implementation should not receive unnecessarily large application context.
    """

    example_id: str = Field(..., description="Unique identifier for this example.")
    customer_tier: str = Field(..., description="Customer tier (e.g. enterprise, standard, free).")
    product: str = Field(..., description="Product category (e.g. billing, api, dashboard).")
    region: str = Field(..., description="Geographic region (e.g. EU, US, APAC).")
    ticket_subject: str = Field(..., description="Support ticket subject line.")
    ticket_body: str = Field(..., description="Support ticket body text.")
    draft_reply: str = Field(..., description="AI-generated draft reply awaiting control decision.")

    model_config = {"str_strip_whitespace": True}


def redact_state(state: ApplicationState) -> dict:
    """Return a redacted view of ApplicationState safe for structured logs.

    Removes free-text customer content; retains metadata-level fields only.
    Required by the security contract (JevRoute_MVP_Technical_Architecture.md §46).
    """
    return {
        "example_id": state.example_id,
        "customer_tier": state.customer_tier,
        "product": state.product,
        "region": state.region,
        "ticket_subject": "[REDACTED]",
        "ticket_body": "[REDACTED]",
        "draft_reply": "[REDACTED]",
    }
