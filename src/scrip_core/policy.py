"""Exact, user-configured decisions. This module never executes a command."""

from datetime import datetime

from .models import QUESTION_TOOLS, Decision, Rule, ToolRequested, canonical_json, utc_now


def decide(
    event: ToolRequested,
    rules: list[Rule],
    *,
    paused: bool = False,
    now: datetime | None = None,
) -> Decision:
    if event.payload.name in QUESTION_TOOLS:
        return Decision(action="ask", reason="A question needs a human answer")
    now = now or utc_now()
    arguments = canonical_json(event.payload.arguments)
    matches = [
        rule
        for rule in rules
        if rule.enabled
        and rule.adapter == event.adapter
        and rule.workspace == event.workspace
        and rule.tool == event.payload.name
        and (rule.session_id is None or rule.session_id == event.session_id)
        and (rule.expires_at is None or rule.expires_at > now)
        and canonical_json(rule.arguments) == arguments
    ]
    denied = next((rule for rule in matches if rule.action == "deny"), None)
    if denied:
        return Decision(action="deny", reason=f"Denied by rule {denied.id}", rule_id=denied.id)
    if paused:
        return Decision(action="ask", reason="Scrip automatic decisions are paused")
    allowed = next((rule for rule in matches if rule.action == "allow"), None)
    if allowed:
        return Decision(
            action="allow", reason=f"Authorized by rule {allowed.id}", rule_id=allowed.id
        )
    return Decision(action="ask", reason="No exact user-authorized rule matches this action")
