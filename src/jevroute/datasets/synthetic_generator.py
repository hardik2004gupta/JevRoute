"""Synthetic benchmark dataset generator.

Generates diverse labeled support ticket examples for the JevRoute benchmark.
Source type: SYNTHETIC — not real operational data.

Ground truth is assigned deterministically by a rule-based labeling function.
No benchmark router (Rules, LLM Single, LLM Parallel, Jev) is used to generate labels.
This ensures the benchmark evaluation remains independent of the training/labeling process.

Usage:
    python -m jevroute.datasets.synthetic_generator --output datasets/raw/synthetic_support_v1.jsonl --count 500
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Template pools — each entry defines (subject, body, draft_reply, meta)
# meta carries labeling hints: category, severity_hint, violation, hal, tone, action
# ---------------------------------------------------------------------------

_TIERS = ["enterprise", "enterprise", "standard", "standard", "free"]
_PRODUCTS = ["api", "billing", "dashboard", "account", "core"]
_REGIONS = ["US", "EU", "APAC", "CA"]

# (subject_tmpl, body_tmpl, draft_tmpl, category, sev_base, policy_violation, hal_risk, tone_risk, action)
_BILLING_TEMPLATES = [
    (
        "Duplicate charge on account {idx}",
        "I was charged twice for my subscription this month. Transaction IDs appear identical.",
        "We have identified the duplicate charge and will issue a refund within 5-7 business days.",
        "Billing", "P2", False, 0.05, 0.02, "SEND",
    ),
    (
        "Unauthorized transaction on invoice {idx}",
        "There is a charge I did not authorize on my latest invoice. Amount: ${amount}.",
        "We will initiate an immediate refund and investigate the unauthorized charge.",
        "Billing", "P1", True, 0.10, 0.03, "HOLD",
    ),
    (
        "Invoice {idx} not received",
        "I have not received my invoice for this billing period. I need it for accounting.",
        "We will resend your invoice to the email address registered on your account.",
        "Billing", "P3", False, 0.03, 0.01, "SEND",
    ),
    (
        "Incorrect pricing on plan {idx}",
        "The price I am being charged does not match the price on the plan page when I signed up.",
        "Our billing team will review your account and contact you with a resolution.",
        "Billing", "P2", False, 0.08, 0.04, "SEND",
    ),
    (
        "Subscription renewal confusion {idx}",
        "I was not notified before my subscription renewed automatically. I want a refund.",
        "Renewal notifications are sent 30 days in advance to your registered email.",
        "Billing", "P3", False, 0.12, 0.06, "SEND",
    ),
    (
        "Overcharge on enterprise contract {idx}",
        "The amount billed on our enterprise contract is $500 more than the agreed price.",
        "We guarantee a full refund and will immediately correct the contract billing.",
        "Billing", "P2", True, 0.15, 0.05, "HOLD",
    ),
    (
        "Tax calculation error on invoice {idx}",
        "The tax on my invoice appears to be calculated at the wrong rate for my region.",
        "Our finance team will review the tax settings on your account.",
        "Billing", "P3", False, 0.06, 0.02, "SEND",
    ),
    (
        "Payment method declined {idx}",
        "My payment method was declined but my card is valid and has available funds.",
        "Please try updating your payment method in the billing portal.",
        "Billing", "P3", False, 0.04, 0.01, "SEND",
    ),
    (
        "Contract renewal terms dispute {idx}",
        "The renewal terms on my new contract differ from what was agreed verbally with sales.",
        "Our contracts team will review the agreement and reach out within 2 business days.",
        "Billing", "P2", False, 0.09, 0.05, "SEND",
    ),
    (
        "Refund not processed after {idx} days",
        "I requested a refund 14 days ago and it has not appeared on my statement.",
        "We confirm your refund was approved and will arrive within 10 business days.",
        "Billing", "P2", False, 0.08, 0.03, "SEND",
    ),
]

_BUG_TEMPLATES = [
    (
        "API returning 500 errors for endpoint {idx}",
        "Our integration is receiving 500 responses consistently for the past 2 hours.",
        "Our engineering team is investigating the service degradation.",
        "Bug", "P2", False, 0.15, 0.08, "SEND",
    ),
    (
        "Dashboard blank screen after login {idx}",
        "After logging in the dashboard shows a completely blank page. No errors in console.",
        "Please clear your browser cache and cookies then try logging in again.",
        "Bug", "P3", False, 0.12, 0.05, "SEND",
    ),
    (
        "Data export failing silently {idx}",
        "When I trigger a data export it says completed but no file arrives.",
        "We have identified a bug in the export service and a fix is being deployed.",
        "Bug", "P2", False, 0.18, 0.07, "SEND",
    ),
    (
        "Webhook events not firing {idx}",
        "Our webhook endpoint stopped receiving events 6 hours ago. No changes on our side.",
        "We are investigating webhook delivery issues affecting some accounts.",
        "Bug", "P2", False, 0.16, 0.09, "SEND",
    ),
    (
        "Search results returning incorrect data {idx}",
        "Search results in the UI appear to be returning records from a different account.",
        "We have escalated this as a potential data isolation issue requiring immediate review.",
        "Bug", "P1", False, 0.25, 0.10, "ESCALATE",
    ),
    (
        "Mobile app crashing on startup {idx}",
        "The mobile app crashes immediately after the splash screen on iOS 17.4.",
        "Our mobile team is aware of this issue on iOS 17.4 and a patch is in review.",
        "Bug", "P2", False, 0.10, 0.04, "SEND",
    ),
    (
        "Report generation taking too long {idx}",
        "Generating a monthly report now takes over 10 minutes and sometimes times out.",
        "Performance improvements for large reports are scheduled for the next release.",
        "Bug", "P3", False, 0.08, 0.03, "SEND",
    ),
    (
        "SSO integration broken after update {idx}",
        "Our SAML SSO stopped working after last Tuesday's platform update.",
        "We have identified a regression in SSO configuration parsing and are reverting.",
        "Bug", "P1", False, 0.20, 0.08, "ESCALATE",
    ),
    (
        "CSV import rejecting valid file {idx}",
        "A CSV file that imported correctly last month is now being rejected with no error.",
        "Please check that your CSV headers match the current import template exactly.",
        "Bug", "P3", False, 0.09, 0.04, "SEND",
    ),
    (
        "Notification emails not arriving {idx}",
        "Team members are not receiving any notification emails for the past 3 days.",
        "We are investigating an issue with our email delivery provider.",
        "Bug", "P2", False, 0.11, 0.05, "SEND",
    ),
]

_FEATURE_TEMPLATES = [
    (
        "Request: dark mode for dashboard {idx}",
        "Would love a dark mode option in the dashboard to reduce eye strain.",
        "Thank you for the suggestion. We have passed this to our product team for consideration.",
        "Feature", "P4", False, 0.03, 0.01, "SEND",
    ),
    (
        "Feature request: bulk user import {idx}",
        "We need the ability to import multiple users at once via CSV instead of one by one.",
        "Bulk user import is on our roadmap for Q3. We will notify you when it is available.",
        "Feature", "P4", False, 0.07, 0.02, "SEND",
    ),
    (
        "Request: API rate limit increase option {idx}",
        "Our production workload regularly hits the rate limit. An option to purchase higher limits would help.",
        "Custom rate limit tiers are available for enterprise accounts. Please contact sales.",
        "Feature", "P3", False, 0.05, 0.02, "SEND",
    ),
    (
        "Add two-factor authentication support {idx}",
        "We need 2FA for compliance reasons. Is this on your roadmap?",
        "2FA via TOTP authenticator apps is available in account security settings.",
        "Feature", "P3", False, 0.04, 0.01, "SEND",
    ),
    (
        "Request: custom report builder {idx}",
        "The preset reports do not cover our analytics needs. A custom report builder would be valuable.",
        "Custom reporting is a planned feature. We have added your request to the tracking list.",
        "Feature", "P4", False, 0.06, 0.02, "SEND",
    ),
    (
        "Webhook retry configuration {idx}",
        "We need configurable retry intervals for webhook failures to match our infrastructure.",
        "Webhook retry settings including interval and max attempts are available in the developer portal.",
        "Feature", "P3", False, 0.05, 0.01, "SEND",
    ),
    (
        "Export data to multiple formats {idx}",
        "Currently only CSV is supported for export. Can you add JSON and Parquet?",
        "JSON export is already available via the API. Parquet format is under consideration.",
        "Feature", "P4", False, 0.08, 0.03, "SEND",
    ),
    (
        "Audit log download {idx}",
        "We need downloadable audit logs for our compliance team.",
        "Audit log export to CSV is available under Settings > Security > Audit Logs.",
        "Feature", "P3", False, 0.04, 0.01, "SEND",
    ),
]

_ACCOUNT_TEMPLATES = [
    (
        "Entire team locked out of account {idx}",
        "All 15 members of our team cannot log in as of this morning. Production is impacted.",
        "We have escalated this as a critical access incident and are investigating immediately.",
        "Account", "P1", False, 0.20, 0.05, "ESCALATE",
    ),
    (
        "Admin permissions not working {idx}",
        "I am listed as an admin but I cannot access admin settings.",
        "Please try logging out and back in. If the issue persists contact support with your user ID.",
        "Account", "P3", False, 0.08, 0.04, "SEND",
    ),
    (
        "Cannot delete account {idx}",
        "I want to close my account but I cannot find the option to delete it.",
        "Account deletion is available under Settings > Account > Delete Account.",
        "Account", "P3", False, 0.05, 0.02, "SEND",
    ),
    (
        "User not receiving invitation email {idx}",
        "I invited a colleague but they have not received the invitation email after 24 hours.",
        "Please check spam folders. You can resend the invitation from the Team Members page.",
        "Account", "P3", False, 0.06, 0.02, "SEND",
    ),
    (
        "Security breach suspected on account {idx}",
        "We believe an unauthorized party may have accessed our account. We need immediate help.",
        "We have immediately locked your account and our security team is reviewing access logs.",
        "Account", "P1", False, 0.15, 0.05, "ESCALATE",
    ),
    (
        "Cannot transfer account ownership {idx}",
        "I need to transfer ownership to a colleague but there is no option to do this.",
        "Account ownership transfer requires contacting support with identity verification.",
        "Account", "P2", False, 0.07, 0.03, "SEND",
    ),
    (
        "API keys stopped working after team change {idx}",
        "After our team admin changed, all our API keys returned authentication errors.",
        "API keys are tied to individual accounts. Please regenerate keys under your user settings.",
        "Account", "P2", False, 0.10, 0.04, "SEND",
    ),
    (
        "GDPR data deletion request {idx}",
        "Under GDPR we are requesting deletion of all personal data for a former employee.",
        "We will process your data deletion request within 30 days as required by GDPR.",
        "Account", "P2", False, 0.06, 0.02, "SEND",
    ),
    (
        "Two accounts accidentally merged {idx}",
        "It appears our personal and business accounts were merged by mistake.",
        "Our account team will investigate the merge and work to separate the accounts.",
        "Account", "P2", False, 0.12, 0.06, "SEND",
    ),
    (
        "Password reset not working {idx}",
        "The password reset link in the email does not work and expires immediately.",
        "Password reset links expire after 1 hour. Please request a new reset link.",
        "Account", "P3", False, 0.05, 0.02, "SEND",
    ),
]

_OTHER_TEMPLATES = [
    (
        "General question about plan features {idx}",
        "I am trying to understand which features are included in the standard plan.",
        "You can find a full feature comparison at our pricing page. Happy to clarify specifics.",
        "Other", "P4", False, 0.04, 0.01, "SEND",
    ),
    (
        "Onboarding help needed {idx}",
        "We just signed up and are not sure where to start with the setup.",
        "Welcome! We recommend starting with our getting started guide in the documentation.",
        "Other", "P4", False, 0.03, 0.01, "SEND",
    ),
    (
        "Compliance certification documentation {idx}",
        "We need SOC 2 Type II documentation for our procurement process.",
        "Our SOC 2 Type II report is available under NDA. Please contact your account manager.",
        "Other", "P3", False, 0.06, 0.02, "SEND",
    ),
    (
        "Service status during maintenance {idx}",
        "I noticed service degradation yesterday. Is there a status page I can monitor?",
        "Our status page at status.example.com shows real-time service health.",
        "Other", "P4", False, 0.04, 0.01, "SEND",
    ),
    (
        "Integration documentation unclear {idx}",
        "The integration guide for our CRM system is unclear about OAuth scopes needed.",
        "Our developer documentation covers all required OAuth scopes for CRM integrations.",
        "Other", "P4", False, 0.05, 0.02, "SEND",
    ),
    (
        "SLA clarification for enterprise plan {idx}",
        "I need to understand our SLA commitments for the enterprise plan for an internal review.",
        "SLA details are available in your enterprise contract. Contact your account manager.",
        "Other", "P3", False, 0.07, 0.03, "SEND",
    ),
    (
        "Partner program information {idx}",
        "We are interested in becoming a reseller partner. How does the partner program work?",
        "Our partner program details are available at our partnerships page. We will connect you.",
        "Other", "P4", False, 0.05, 0.01, "SEND",
    ),
    (
        "Training and certification options {idx}",
        "Do you offer certification or training for our team to become platform experts?",
        "We offer self-paced certification courses through our learning portal.",
        "Other", "P4", False, 0.03, 0.01, "SEND",
    ),
]

_ALL_TEMPLATES = (
    _BILLING_TEMPLATES * 5 +
    _BUG_TEMPLATES * 5 +
    _FEATURE_TEMPLATES * 7 +
    _ACCOUNT_TEMPLATES * 5 +
    _OTHER_TEMPLATES * 7
)


def _severity_for_tier(base_sev: str, tier: str) -> str:
    """Adjust severity based on customer tier."""
    tier_bump = {"enterprise": 1, "standard": 0, "free": -1}
    sev_order = ["P1", "P2", "P3", "P4"]
    idx = sev_order.index(base_sev)
    bump = tier_bump.get(tier, 0)
    new_idx = max(0, min(3, idx - bump))  # bump up = lower index = higher severity
    return sev_order[new_idx]


def _make_example(
    example_id: str,
    template: tuple,
    tier: str,
    product: str,
    region: str,
    variant: int,
) -> dict:
    (subject_tmpl, body_tmpl, draft_tmpl, category, sev_base, policy_viol,
     hal_risk, tone_risk, action) = template

    # Apply small per-variant adjustments to make records non-identical
    variant_hal = round(min(1.0, max(0.0, hal_risk + (variant * 0.01 % 0.05))), 3)
    variant_tone = round(min(1.0, max(0.0, tone_risk + (variant * 0.007 % 0.03))), 3)

    severity = _severity_for_tier(sev_base, tier)

    # Determine action from severity + policy_violation
    if policy_viol:
        actual_action = "HOLD"
    elif severity == "P1" and category in ("Account", "Bug"):
        actual_action = "ESCALATE"
    else:
        actual_action = action

    subject = subject_tmpl.format(idx=variant, amount=f"{(variant * 13 % 900) + 100:.0f}")
    body = body_tmpl
    draft = draft_tmpl

    return {
        "example_id": example_id,
        "customer_tier": tier,
        "product": product,
        "region": region,
        "ticket_subject": subject,
        "ticket_body": body,
        "draft_reply": draft,
        "ground_truth": {
            "severity": severity,
            "category": category,
            "policy_violation": policy_viol,
            "hallucination_risk": variant_hal,
            "tone_risk": variant_tone,
            "action": actual_action,
        },
    }


def generate(count: int = 500, seed_string: str = "jevroute-synthetic-v1") -> list[dict]:
    """Generate `count` deterministic synthetic support ticket examples.

    Ground truth is assigned by a rule-based function that does not use
    any benchmark router. Records are shuffled deterministically using the seed.
    """
    import random
    rng = random.Random(hashlib.sha256(seed_string.encode()).hexdigest())

    examples: list[dict] = []
    template_count = len(_ALL_TEMPLATES)

    for i in range(count):
        template_idx = i % template_count
        tmpl = _ALL_TEMPLATES[template_idx]
        tier = _TIERS[i % len(_TIERS)]
        product = _PRODUCTS[i % len(_PRODUCTS)]
        region = _REGIONS[i % len(_REGIONS)]
        variant = i // template_count + 1
        example_id = f"syn-{i + 1:04d}"
        examples.append(_make_example(example_id, tmpl, tier, product, region, variant))

    rng.shuffle(examples)
    # Re-assign sequential IDs after shuffle
    for i, ex in enumerate(examples):
        ex["example_id"] = f"syn-{i + 1:04d}"

    return examples


def write_jsonl(examples: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in examples), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic JevRoute benchmark dataset")
    parser.add_argument("--output", default="datasets/raw/synthetic_support_v1.jsonl")
    parser.add_argument("--count", type=int, default=500)
    args = parser.parse_args(argv)

    path = Path(args.output)
    if path.exists():
        print(f"ERROR: output file already exists: {path}", file=sys.stderr)
        return 1

    examples = generate(count=args.count)
    write_jsonl(examples, path)

    # Print category/severity distribution
    from collections import Counter
    cats = Counter(e["ground_truth"]["category"] for e in examples)
    sevs = Counter(e["ground_truth"]["severity"] for e in examples)
    acts = Counter(e["ground_truth"]["action"] for e in examples)
    viols = sum(1 for e in examples if e["ground_truth"]["policy_violation"])
    print(f"Generated {len(examples)} examples → {path}")
    print(f"Categories: {dict(cats)}")
    print(f"Severities: {dict(sevs)}")
    print(f"Actions: {dict(acts)}")
    print(f"Policy violations: {viols} ({viols/len(examples)*100:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
