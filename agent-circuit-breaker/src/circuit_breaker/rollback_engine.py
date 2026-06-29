"""Rollback Engine — compensates for or reverses tool calls after an incident.

Rollback strategies:
  - tool_call_compensation: Execute an inverse/compensating tool call
  - state_restore: Restore previous agent/application state
  - cost_refund: Log cost refund for billing adjustment
  - approval_revoke: Revoke an approval that was granted
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import Incident, RollbackLog, ToolCall


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


INVERSE_TOOL_MAP: dict[str, str] = {
    "create_file": "delete_file",
    "write_file": "delete_file",
    "copy_file": "delete_file",
    "move_file": "move_file",  # inverse needs original path
    "rename_file": "rename_file",  # inverse needs original name
    "insert_record": "delete_record",
    "create_user": "delete_user",
    "send_email": "send_email",  # send recall/cancel email
    "process_payment": "refund",
    "apply_discount": "apply_discount",  # inverse discount
    "create_api_key": "revoke_api_key",
    "modify_permissions": "modify_permissions",  # inverse permissions
    "update_system_prompt": "update_system_prompt",  # restore previous prompt
}


async def execute_rollback(
    session: AsyncSession,
    incident_id: uuid.UUID,
) -> list[RollbackLog]:
    stmt = select(Incident).where(Incident.id == incident_id)
    result = await session.execute(stmt)
    incident = result.scalar_one_or_none()
    if not incident:
        return []

    rollbacks: list[RollbackLog] = []

    if incident.tool_call_id:
        tool_stmt = select(ToolCall).where(ToolCall.id == incident.tool_call_id)
        tool_result = await session.execute(tool_stmt)
        tool_call = tool_result.scalar_one_or_none()
        if tool_call:
            compensation = await _compensate_tool_call(
                session, incident, tool_call
            )
            if compensation:
                rollbacks.append(compensation)

    state_restore = await _log_state_restore(session, incident)
    if state_restore:
        rollbacks.append(state_restore)

    cost_refund = await _log_cost_refund(session, incident)
    if cost_refund:
        rollbacks.append(cost_refund)

    if rollbacks:
        incident.rolled_back = True
        incident.rollback_id = rollbacks[0].id
        await session.flush()

    return rollbacks


async def _compensate_tool_call(
    session: AsyncSession,
    incident: Incident,
    tool_call: ToolCall,
) -> RollbackLog | None:
    inverse_tool = INVERSE_TOOL_MAP.get(tool_call.tool_name)
    if not inverse_tool:
        return None

    rollback = RollbackLog(
        incident_id=incident.id,
        tenant_id=incident.tenant_id,
        agent_id=incident.agent_id,
        rollback_type="tool_call_compensation",
        target_id=str(tool_call.id),
        status="pending",
        details={
            "original_tool": tool_call.tool_name,
            "compensation_tool": inverse_tool,
            "original_input": tool_call.tool_input,
        },
        created_at=now_utc(),
    )
    session.add(rollback)
    await session.flush()
    return rollback


async def _log_state_restore(
    session: AsyncSession,
    incident: Incident,
) -> RollbackLog | None:
    rollback = RollbackLog(
        incident_id=incident.id,
        tenant_id=incident.tenant_id,
        agent_id=incident.agent_id,
        rollback_type="state_restore",
        status="pending",
        details={
            "incident_category": incident.category,
            "action_taken": incident.action_taken,
        },
        created_at=now_utc(),
    )
    session.add(rollback)
    await session.flush()
    return rollback


async def _log_cost_refund(
    session: AsyncSession,
    incident: Incident,
) -> RollbackLog | None:
    if incident.tool_call_id:
        tool_stmt = select(ToolCall).where(ToolCall.id == incident.tool_call_id)
        tool_result = await session.execute(tool_stmt)
        tool_call = tool_result.scalar_one_or_none()
        if tool_call and (tool_call.cost and float(tool_call.cost) > 0):
            rollback = RollbackLog(
                incident_id=incident.id,
                tenant_id=incident.tenant_id,
                agent_id=incident.agent_id,
                rollback_type="cost_refund",
                target_id=str(tool_call.id),
                status="pending",
                details={
                    "refund_amount": str(tool_call.cost),
                    "tool_name": tool_call.tool_name,
                },
                created_at=now_utc(),
            )
            session.add(rollback)
            await session.flush()
            return rollback
    return None


async def complete_rollback(
    session: AsyncSession,
    rollback_id: uuid.UUID,
    success: bool = True,
) -> RollbackLog | None:
    stmt = select(RollbackLog).where(RollbackLog.id == rollback_id)
    result = await session.execute(stmt)
    rollback = result.scalar_one_or_none()
    if rollback:
        rollback.status = "completed" if success else "failed"
        rollback.completed_at = now_utc()
        await session.flush()
    return rollback
