"""Admin-only API endpoints for the curriculum dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import AuthUser
from .database import PostgresRepository


class HotspotStatusPayload(BaseModel):
    status: str
    reviewed_guidance: str = ""
    suggested_activity_adjustment: str | None = None
    suggested_checkpoint_focus: str | None = None


def require_admin(user: AuthUser) -> AuthUser:
    """Raise 403 if the authenticated user does not have admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# The endpoints below are wired up via ``mount_admin_routes`` which receives
# the ``current_user`` and ``service_dep`` dependencies from the main app.
# ---------------------------------------------------------------------------


def mount_admin_routes(
    app: Any,
    *,
    current_user_dep: Any,
    service_dep: Any,
) -> None:
    """Register all admin routes on the FastAPI app."""

    router = APIRouter(prefix="/api/admin", tags=["admin"])

    def admin_user(user: AuthUser = Depends(current_user_dep)) -> AuthUser:
        return require_admin(user)

    def repo_dep(svc: Any = Depends(service_dep)) -> PostgresRepository:
        if not svc.repository:
            raise HTTPException(status_code=503, detail="Database is not available")
        return svc.repository

    # -- Admin check --------------------------------------------------------

    @router.get("/check")
    def admin_check(user: AuthUser = Depends(admin_user)) -> dict[str, Any]:
        return {"ok": True, "user_id": user.user_id, "role": user.role}

    # -- Dashboard ----------------------------------------------------------

    @router.get("/dashboard")
    def dashboard(
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        return repo.admin_dashboard_stats()

    # -- Learners -----------------------------------------------------------

    @router.get("/learners")
    def list_learners(
        limit: int = 50,
        offset: int = 0,
        search: str = "",
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        return repo.admin_list_learners(limit=limit, offset=offset, search=search.strip())

    @router.get("/learners/{user_id}")
    def get_learner(
        user_id: str,
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        detail = repo.admin_get_learner_detail(user_id)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Learner not found: {user_id}")
        return detail

    # -- Hotspots -----------------------------------------------------------

    @router.get("/hotspots")
    def list_hotspots(
        status: str = "",
        limit: int = 50,
        offset: int = 0,
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        return repo.admin_list_hotspots(
            status=status.strip() or None,
            limit=limit,
            offset=offset,
        )

    @router.get("/hotspots/{hotspot_id}")
    def get_hotspot(
        hotspot_id: str,
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        hotspot = repo.admin_get_hotspot(hotspot_id)
        if not hotspot:
            raise HTTPException(status_code=404, detail=f"Hotspot not found: {hotspot_id}")
        return hotspot

    @router.patch("/hotspots/{hotspot_id}")
    def update_hotspot(
        hotspot_id: str,
        payload: HotspotStatusPayload,
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        try:
            repo.update_hotspot_status(
                hotspot_id,
                payload.status,
                reviewed_guidance=payload.reviewed_guidance or None,
                suggested_activity_adjustment=payload.suggested_activity_adjustment,
                suggested_checkpoint_focus=payload.suggested_checkpoint_focus,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        updated = repo.admin_get_hotspot(hotspot_id)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Hotspot not found: {hotspot_id}")
        return updated

    # -- Content analytics --------------------------------------------------

    @router.get("/content/stats")
    def content_stats(
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        return repo.admin_content_stats()

    @router.get("/checkpoint-analytics")
    def checkpoint_analytics(
        user: AuthUser = Depends(admin_user),
        repo: PostgresRepository = Depends(repo_dep),
    ) -> dict[str, Any]:
        return repo.admin_checkpoint_analytics()

    app.include_router(router)
