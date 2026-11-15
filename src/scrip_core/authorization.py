"""Expiring tool authorizations, independent of host and storage schemas."""

from datetime import UTC, datetime

from pydantic import field_validator

from .models import QUESTION_TOOLS, Contract, Identifier, Rule, ToolRequested, workspace_path


class SessionCommandScope(Contract):
    adapter: str
    workspace: str
    tool: Identifier
    session_id: Identifier | None = None

    _workspace = field_validator("workspace")(workspace_path)

    def matches(self, event: ToolRequested) -> bool:
        return (
            event.policy_mode == "enforce"
            and event.payload.name not in QUESTION_TOOLS
            and event.adapter == self.adapter
            and event.workspace == self.workspace
            and event.payload.name == self.tool
            and (self.session_id is None or self.session_id == event.session_id)
        )


class ProjectAuthorization(Contract):
    id: Identifier
    expires_at: datetime
    rules: tuple[Rule, ...]
    session: SessionCommandScope | None = None

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Authorization expiry must include a timezone")
        return value.astimezone(UTC)

    def matching_rules(self, event: ToolRequested, now: datetime) -> list[Rule]:
        if self.expires_at <= now or event.policy_mode != "enforce":
            return []
        return [
            rule
            for rule in self.rules
            if rule.adapter == event.adapter
            and rule.workspace == event.workspace
            and rule.tool == event.payload.name
        ]
