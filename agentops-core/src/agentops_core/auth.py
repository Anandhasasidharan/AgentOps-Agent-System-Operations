"""Shared authentication dependency.

Usage in each service:
    from agentops_core.auth import make_get_tenant
    from your_service.db import get_db

    get_tenant = make_get_tenant(get_db)

API key format: slug:random-hex-token
- slug identifies the tenant
- token is verified against stored hash
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_core.base import Tenant


def generate_api_key(slug: str) -> tuple[str, str]:
    token = secrets.token_hex(32)
    raw = f"{slug}:{token}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    return raw, h


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    return hashlib.sha256(raw_key.encode()).hexdigest() == stored_hash


def make_get_tenant(
    db_dependency: Callable,
) -> Callable:
    async def _get_tenant(
        x_api_key: str = Header(..., alias="X-API-Key"),
        session: AsyncSession = Depends(db_dependency),
    ) -> Tenant:
        slug = x_api_key.split(":", 1)[0]
        stmt = select(Tenant).where(Tenant.slug == slug)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if tenant.api_key_hash and not verify_api_key(x_api_key, tenant.api_key_hash):
            raise HTTPException(status_code=401, detail="Invalid API key")
        return tenant

    return _get_tenant
