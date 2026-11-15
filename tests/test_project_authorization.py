from datetime import timedelta

from scrip_core.authorization import ProjectAuthorization, SessionCommandScope
from scrip_core.models import Tool
from tests.factories import rule_for


def authorize(companion, event, clock):
    grant = ProjectAuthorization(
        id="activation-1",
        expires_at=clock() + timedelta(hours=24),
        rules=(rule_for(event),),
    )
    companion.set_project_authorization(grant)
    return grant


def test_project_grant_requires_activation_and_exact_arguments(companion, tool_event, clock):
    authorize(companion, tool_event, clock)
    assert companion.ingest(tool_event).decision.action == "ask"
    matching = tool_event.model_copy(update={"event_id": "new", "operation_id": "new"})
    assert companion.ingest(matching, authorization_id="activation-1").decision.action == "allow"
    assert companion.ingest(matching, authorization_id="activation-1").decision.action == "ask"
    changed = matching.model_copy(
        update={
            "event_id": "changed",
            "operation_id": "changed",
            "payload": Tool(
                name=tool_event.payload.name,
                arguments={
                    **tool_event.payload.arguments,
                    "CommandLine": "different command",
                },
            ),
        }
    )
    assert companion.ingest(changed, authorization_id="activation-1").decision.action == "ask"


def test_revocation_and_expiry_prevent_later_approvals(companion, tool_event, clock):
    authorize(companion, tool_event, clock)
    companion.set_project_authorization(None)
    assert companion.ingest(tool_event, authorization_id="activation-1").decision.action == "ask"
    authorize(companion, tool_event, clock)
    clock.advance(hours=25)
    changed = tool_event.model_copy(update={"event_id": "expired", "operation_id": "expired"})
    assert companion.ingest(changed, authorization_id="activation-1").decision.action == "ask"


def test_wrong_activation_workspace_adapter_and_pause_cannot_use_grant(
    companion, tool_event, clock, tmp_path
):
    authorize(companion, tool_event, clock)
    variants = [
        {"adapter": "other"},
        {"session_id": "another", "workspace": str(tmp_path / "other")},
        {"payload": Tool(name="other", arguments=tool_event.payload.arguments)},
    ]
    for index, update in enumerate(variants):
        event = tool_event.model_copy(
            update={
                "event_id": f"scope-{index}",
                "operation_id": f"scope-{index}",
                **update,
            }
        )
        assert companion.ingest(event, authorization_id="activation-1").decision.action == "ask"
    assert companion.ingest(tool_event, authorization_id="stale").decision.action == "ask"
    companion.set_paused(True)
    event = tool_event.model_copy(update={"event_id": "paused", "operation_id": "paused"})
    assert companion.ingest(event, authorization_id="activation-1").decision.action == "ask"


def test_explicit_deny_wins_over_project_grant(companion, tool_event, clock):
    authorize(companion, tool_event, clock)
    companion.put_rule(rule_for(tool_event, id="deny", action="deny"))
    assert companion.ingest(tool_event, authorization_id="activation-1").decision.action == "deny"


def test_question_cannot_be_answered_by_project_authorization(companion, input_event, clock):
    companion.set_project_authorization(
        ProjectAuthorization(
            id="activation-1",
            expires_at=clock() + timedelta(hours=24),
            rules=(),
        )
    )
    result = companion.ingest(input_event, authorization_id="activation-1")
    assert result.decision.action == "ask"
    assert companion.inbox()[0].kind == "input"


def session_grant(event, clock):
    return ProjectAuthorization(
        id="session-grant",
        expires_at=clock() + timedelta(hours=24),
        rules=(),
        session=SessionCommandScope(
            adapter=event.adapter, workspace=event.workspace, tool=event.payload.name
        ),
    )


def test_parallel_conversations_atomically_bind_only_one(companion, tool_event, clock):
    from concurrent.futures import ThreadPoolExecutor

    companion.set_project_authorization(session_grant(tool_event, clock))
    events = [
        tool_event.model_copy(
            update={
                "session_id": f"session-{index}",
                "event_id": f"event-{index}",
                "operation_id": f"operation-{index}",
            }
        )
        for index in range(8)
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda event: companion.ingest(event, authorization_id="session-grant"), events
            )
        )
    assert sum(result.decision.action == "allow" for result in results) == 1
    allowed = next(
        event.session_id
        for event, result in zip(events, results, strict=True)
        if result.decision.action == "allow"
    )
    assert companion.project_authorization().session.session_id == allowed


def test_session_grant_obeys_pause_deny_expiry_revocation_and_workspace(
    companion, tool_event, clock, tmp_path
):
    companion.set_project_authorization(session_grant(tool_event, clock))
    companion.set_paused(True)
    assert companion.ingest(tool_event, authorization_id="session-grant").decision.action == "ask"
    assert companion.project_authorization().session.session_id is None
    companion.set_paused(False)
    companion.put_rule(rule_for(tool_event, id="deny-command", action="deny"))
    denied = tool_event.model_copy(update={"event_id": "denied", "operation_id": "denied"})
    assert companion.ingest(denied, authorization_id="session-grant").decision.action == "deny"
    assert companion.project_authorization().session.session_id is None
    wrong = tool_event.model_copy(
        update={
            "event_id": "wrong",
            "operation_id": "wrong",
            "session_id": "other",
            "workspace": str(tmp_path / "other"),
        }
    )
    assert companion.ingest(wrong, authorization_id="session-grant").decision.action == "ask"
    companion.remove_rule("deny-command")
    clock.advance(hours=25)
    expired = tool_event.model_copy(update={"event_id": "expired", "operation_id": "expired"})
    assert companion.ingest(expired, authorization_id="session-grant").decision.action == "ask"
    companion.set_project_authorization(session_grant(tool_event, clock))
    companion.set_project_authorization(None)
    stopped = tool_event.model_copy(update={"event_id": "stopped", "operation_id": "stopped"})
    assert companion.ingest(stopped, authorization_id="session-grant").decision.action == "ask"
