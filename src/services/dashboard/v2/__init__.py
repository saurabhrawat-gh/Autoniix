"""v2 dashboard router — additive API surface for the UI revamp.

Mounted from ``src/services/dashboard/main.py`` with::

    from src.services.dashboard.v2 import router as v2_router
    app.include_router(v2_router, prefix="/api/v2")

All v2 endpoints accept either a legacy ``/api/auth/login`` bearer token
(via :func:`legacy_session_dep`) or a v2 JWT (via :func:`v2_user_dep`),
so a partially-migrated dashboard keeps working.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    auth as _auth,
    channels as _channels,
    content as _content,
    experiments as _experiments,
    flags as _flags,
    library as _library,
    notifications as _notifications,
    providers as _providers,
    review as _review,
    users as _users,
    workspace as _workspace,
)

router = APIRouter(tags=["v2"])
router.include_router(_flags.router,         prefix="/flags",         tags=["v2.flags"])
router.include_router(_auth.router,          prefix="/auth",          tags=["v2.auth"])
router.include_router(_users.router,         prefix="/users",         tags=["v2.users"])
router.include_router(_channels.router,      prefix="/channels",      tags=["v2.channels"])
router.include_router(_providers.router,     prefix="/providers",     tags=["v2.providers"])
router.include_router(_content.router,       prefix="/content",       tags=["v2.content"])
router.include_router(_review.router,        prefix="/review",        tags=["v2.review"])
router.include_router(_notifications.router, prefix="/notifications", tags=["v2.notifications"])
router.include_router(_library.router,       prefix="/library",       tags=["v2.library"])
router.include_router(_experiments.router,   prefix="/experiments",   tags=["v2.experiments"])
router.include_router(_workspace.router,     prefix="/workspace",     tags=["v2.workspace"])
