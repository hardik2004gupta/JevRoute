"""RulesRouter: deterministic keyword/regex baseline.

Provides a credible deterministic baseline against which LLM and Jev routers
are compared. Rules are tuned on training/validation data only and must never
inspect test labels.

Router version: rules-v1
"""

from __future__ import annotations

import re
from time import perf_counter

from jevroute.models.decision import (
    Action,
    Category,
    ConfidenceOutput,
    DecisionResult,
    Severity,
)
from jevroute.models.state import ApplicationState

ROUTER_NAME = "rules"
ROUTER_VERSION = "rules-v1"


# ---------------------------------------------------------------------------
# Keyword groups (tuned on training data; never on test labels)
# ---------------------------------------------------------------------------

_BILLING_KEYWORDS = re.compile(
    r"\b(charge[ds]?|billing|invoice|payment|refund|subscription|"
    r"transaction|contract|renewal|overcharge|credited|credit|debit|"
    r"fee|price|cost|quote|receipt)\b",
    re.IGNORECASE,
)
_BUG_KEYWORDS = re.compile(
    r"\b(error|500|bug|not working|broken|blank|loading|crash|fail|"
    r"exception|timeout|hang|slow|unresponsive|glitch|issue|problem"
    r"|doesn.t work|not load|cannot load)\b",
    re.IGNORECASE,
)
_FEATURE_KEYWORDS = re.compile(
    r"\b(feature request|would love|could you add|suggestion|"
    r"dark mode|wish list|please add|nice to have|would be great|"
    r"consider adding|improvement)\b",
    re.IGNORECASE,
)
_ACCOUNT_KEYWORDS = re.compile(
    r"\b(account|access|login|sign.?in|locked|password|reset|"
    r"permission|team|member|user|rate limit|quota|delete account|"
    r"close account|cancel|suspend|2fa|mfa)\b",
    re.IGNORECASE,
)

# Policy violation triggers: strong unauthorized-charge or security breach signals
_POLICY_VIOLATION_KEYWORDS = re.compile(
    r"\b(unauthorized|not authorize|did not authorize|fraudulent|fraud|"
    r"dispute|chargeback|breach|hacked|compromised|stolen|theft)\b",
    re.IGNORECASE,
)

# Severity escalation triggers
_P1_KEYWORDS = re.compile(
    r"\b(entire team|whole company|all users|security breach|account "
    r"compromise[d]?|cannot access|locked out|data loss|urgent|critical|"
    r"outage|down|production down)\b",
    re.IGNORECASE,
)
_P2_KEYWORDS = re.compile(
    r"\b(charged twice|duplicate charge|unauthorized|contract|renewal"
    r"|rate limit|quota exceeded|billing dispute)\b",
    re.IGNORECASE,
)
_P4_KEYWORDS = re.compile(
    r"\b(feature request|suggestion|dark mode|would love|nice to have|"
    r"when will|roadmap)\b",
    re.IGNORECASE,
)

# Hallucination-risk signals in draft replies:
# specific claims about amounts, dates, or guarantees that may not be grounded.
_HALLUCINATION_HIGH = re.compile(
    r"\b(immediately|right away|guarantee[sd]?|definitely|certainly"
    r"|will refund|refund you now|full refund|100%)\b",
    re.IGNORECASE,
)
_HALLUCINATION_MED = re.compile(
    r"\b(will contact|we will|our team will|should be|expect to)\b",
    re.IGNORECASE,
)

# Tone-risk signals in ticket body (customer frustration/aggression):
_TONE_HIGH = re.compile(
    r"\b(unacceptable|ridiculous|outrageous|disgusting|scam|horrible"
    r"|worst|terrible|furious|extremely angry|demand|lawyer|sue)\b",
    re.IGNORECASE,
)
_TONE_MED = re.compile(
    r"\b(frustrated|disappointed|upset|annoyed|unhappy|not happy"
    r"|not impressed|wasted|waste of)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _classify_category(subject: str, body: str) -> Category:
    text = f"{subject} {body}"
    billing_score = len(_BILLING_KEYWORDS.findall(text))
    bug_score = len(_BUG_KEYWORDS.findall(text))
    feature_score = len(_FEATURE_KEYWORDS.findall(text))
    account_score = len(_ACCOUNT_KEYWORDS.findall(text))

    scores = {
        Category.Billing: billing_score,
        Category.Bug: bug_score,
        Category.Feature: feature_score,
        Category.Account: account_score,
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else Category.Other


def _classify_severity(
    subject: str,
    body: str,
    category: Category,
    customer_tier: str,
) -> Severity:
    text = f"{subject} {body}"
    if _P1_KEYWORDS.search(text):
        return Severity.P1
    if _P2_KEYWORDS.search(text):
        return Severity.P2
    if _P4_KEYWORDS.search(text):
        return Severity.P4

    # Tier-modulated defaults per category
    tier = customer_tier.lower()
    if category == Category.Billing:
        return Severity.P2 if tier in ("enterprise", "premium") else Severity.P3
    if category == Category.Bug:
        return Severity.P2 if tier == "enterprise" else Severity.P3
    if category == Category.Account:
        return Severity.P2 if tier == "enterprise" else Severity.P3
    if category == Category.Feature:
        return Severity.P4
    return Severity.P3  # Other


def _detect_policy_violation(subject: str, body: str) -> bool:
    text = f"{subject} {body}"
    return bool(_POLICY_VIOLATION_KEYWORDS.search(text))


def _estimate_hallucination_risk(draft_reply: str) -> float:
    if _HALLUCINATION_HIGH.search(draft_reply):
        return 0.35
    if _HALLUCINATION_MED.search(draft_reply):
        return 0.15
    return 0.05


def _estimate_tone_risk(ticket_body: str) -> float:
    if _TONE_HIGH.search(ticket_body):
        return 0.55
    if _TONE_MED.search(ticket_body):
        return 0.20
    return 0.04


def _determine_action(
    severity: Severity,
    policy_violation: bool,
    hallucination_risk: float,
    category: Category,
) -> Action:
    """Router's raw action recommendation (policy engine applies final override)."""
    if policy_violation:
        return Action.HOLD
    if severity == Severity.P1:
        return Action.ESCALATE
    if hallucination_risk >= 0.30:
        return Action.HOLD
    if severity == Severity.P2 and category == Category.Billing:
        return Action.SEND
    return Action.SEND


# ---------------------------------------------------------------------------
# RulesRouter
# ---------------------------------------------------------------------------

class RulesRouter:
    """Deterministic keyword/regex router.

    This router must be tuned on training and validation data only.
    Test labels must never influence rule thresholds or keyword groups.
    """

    async def decide(self, state: ApplicationState) -> DecisionResult:
        t0 = perf_counter()

        category = _classify_category(state.ticket_subject, state.ticket_body)
        severity = _classify_severity(
            state.ticket_subject,
            state.ticket_body,
            category,
            state.customer_tier,
        )
        policy_violation = _detect_policy_violation(state.ticket_subject, state.ticket_body)
        hallucination_risk = _estimate_hallucination_risk(state.draft_reply)
        tone_risk = _estimate_tone_risk(state.ticket_body)
        action = _determine_action(severity, policy_violation, hallucination_risk, category)

        latency_ms = (perf_counter() - t0) * 1000

        return DecisionResult(
            severity=severity,
            category=category,
            policy_violation=policy_violation,
            hallucination_risk=round(hallucination_risk, 3),
            tone_risk=round(tone_risk, 3),
            action=action,
            confidence=ConfidenceOutput(),  # Rules produce no native probabilities
            router=ROUTER_NAME,
            router_version=ROUTER_VERSION,
            schema_valid=True,
            latency_ms=round(latency_ms, 3),
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=0.0,  # Deterministic rules have zero API cost
        )
