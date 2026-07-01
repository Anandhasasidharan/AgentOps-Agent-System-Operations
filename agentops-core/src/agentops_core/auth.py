"""Shared authentication dependency.

Usage in each service:
    from agentops_core.auth import make_get_tenant
    from your_service.db import get_db

    get_tenant = make_get_tenant(get_db)
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_core.base import Tenant


def make_get_tenant(
    db_dependency: Callable,
) -> Callable:
    async def _get_tenant(
        x_api_key: str = Header(..., alias="X-API-Key"),
        session: AsyncSession = Depends(db_dependency),
    ) -> Tenant:
        stmt = select(Tenant).where(Tenant.slug == x_api_key)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return tenant

    return _get_tenant
