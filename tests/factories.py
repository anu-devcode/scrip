from scrip_core.models import Rule


def rule_for(event, **changes):
    data = {
        "id": "test-task",
        "adapter": event.adapter,
        "workspace": event.workspace,
        "tool": event.payload.name,
        "arguments": event.payload.arguments,
        "action": "allow",
    }
    data.update(changes)
    return Rule(**data)
