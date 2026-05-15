"""
Share Token Auth — Roadmap #15.

Validates share tokens on routes mounted under ``/api/v1/share/*``. The
global JWT gate in ``app/api/__init__.py:authenticate_request`` whitelists
this URL prefix, so unauthenticated viewers can reach the route. The
``@require_share_token`` decorator then runs per-route and either:

1. Resolves the share row, confirms it's not revoked / not expired, and
   for invited mode confirms the caller is logged in with a matching
   email — attaches the result to ``g.share_context`` and continues.

2. 401 / 403 / 410 with a clear error body otherwise.

Design intent: every share endpoint stays short. They read
``g.share_context.project_id`` and treat it as a pre-authorized scope.
They never call the regular project ownership check (``project_service``
filters by ``user_id``, which a share viewer doesn't have).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional

from flask import g, jsonify, request

from app.services.auth.rbac import get_request_identity
from app.services.data_services import share_service


@dataclass(frozen=True)
class ShareContext:
    project_id: str
    mode: str               # "public" | "invited"
    share_id: str
    owner_user_id: str      # the user who created the share (project owner)
    viewer_user_id: Optional[str]   # set iff the viewer is JWT-authenticated
    viewer_email: Optional[str]     # set iff the viewer is JWT-authenticated


def _error(payload: dict, status: int):
    return jsonify(payload), status


def _resolve_token() -> Optional[str]:
    # The route always carries the token as a path param. The decorator
    # picks it out of ``request.view_args`` so individual routes don't need
    # to thread it through manually.
    view_args = request.view_args or {}
    token = view_args.get("token")
    if isinstance(token, str) and token:
        return token
    return None


def require_share_token(*, require_jwt: bool = False) -> Callable:
    """
    Decorator factory.

    Args:
        require_jwt: When True, also requires the caller to be
            JWT-authenticated. Used for the fork endpoint — we need a
            real user_id to assign ownership of the new chat.

    The decorated function receives the same arguments as before; the
    share row + viewer identity are available via ``g.share_context``.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _resolve_token()
            if not token:
                return _error(
                    {"success": False, "error": "Share token missing in URL."},
                    400,
                )

            row = share_service.get_share_by_token(token)
            if not row:
                return _error(
                    {"success": False, "error": "Share link not found."},
                    404,
                )

            if not share_service.is_share_usable(row):
                # Distinguish revoked vs expired so the UI can show the
                # right message, but use 410 Gone for both — semantically
                # "the resource is no longer available".
                reason = "revoked" if row.get("revoked_at") else "expired"
                return _error(
                    {"success": False, "error": f"This share link has {reason}."},
                    410,
                )

            # Resolve the caller's identity. For public mode this can be
            # anonymous; for invited mode we need a JWT with a verified
            # mailbox (or a user_id already in the invitee list — see
            # share_service.viewer_invited for the resolution order).
            identity = get_request_identity()
            viewer_user_id = identity.user_id if identity.is_authenticated else None
            viewer_email = identity.email if identity.is_authenticated else None
            viewer_email_verified = identity.email_verified if identity.is_authenticated else False

            if row.get("mode") == "invited":
                if not identity.is_authenticated:
                    return _error(
                        {
                            "success": False,
                            "error": "Sign in to view this shared project.",
                            "code": "auth_required",
                        },
                        401,
                    )
                if not share_service.viewer_invited(
                    row,
                    viewer_user_id=viewer_user_id,
                    viewer_email=viewer_email,
                    email_verified=viewer_email_verified,
                ):
                    return _error(
                        {
                            "success": False,
                            "error": "Your account isn't on this share's invite list.",
                            "code": "not_invited",
                        },
                        403,
                    )

            if require_jwt and not identity.is_authenticated:
                return _error(
                    {
                        "success": False,
                        "error": "Sign in to continue this conversation in your workspace.",
                        "code": "auth_required",
                    },
                    401,
                )

            g.share_context = ShareContext(
                project_id=row["project_id"],
                mode=row["mode"],
                share_id=row["id"],
                owner_user_id=row["created_by"],
                viewer_user_id=viewer_user_id,
                viewer_email=viewer_email,
            )

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def get_share_context() -> Optional[ShareContext]:
    """Convenience accessor for routes that share helpers."""
    return getattr(g, "share_context", None)
