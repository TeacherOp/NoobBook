"""
RBAC (Role-Based Access Control) helpers.

Current scope:
- Two roles: "admin" and "user"
- Admin-only gating for endpoints that expose/change secrets and global config.

Authentication note:
- NoobBook is currently largely single-user (DEFAULT_USER_ID).
- If an Authorization Bearer token is present and Supabase is configured, we try
  to resolve the user via Supabase Auth and load the role from public.users.
- Otherwise we fall back to DEFAULT_USER_ID (admin).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
import os
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

import jwt
from flask import g, jsonify, request

from app.services.integrations.supabase import (
    get_supabase,
    get_auth_verifier_client,
    is_supabase_enabled,
)
from app.services.data_services.project_service import DEFAULT_USER_ID


logger = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_USER = "user"
_VALID_ROLES = {ROLE_ADMIN, ROLE_USER}

# Same env vars auth_middleware uses. When JWT_SECRET is set, we decode the
# JWT locally instead of round-tripping to Kong's /auth/v1/user. This is
# what eliminates the second wave of Kong calls per request: even though
# auth_middleware already validates the token at before_request, every
# `get_request_identity()` call further down the stack used to call
# `supabase.auth.get_user()` again to fetch email/role.
_JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SUPABASE_JWT_SECRET") or ""
_JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "authenticated")

T = TypeVar("T", bound=Callable[..., Any])


@dataclass(frozen=True)
class RequestIdentity:
    user_id: str
    email: Optional[str]
    role: str
    is_authenticated: bool
    # True only when the JWT carries an operator-verified mailbox claim.
    # Defaults to False so non-JWT identity sources (single-user fallback,
    # legacy callers constructing this manually) never accidentally
    # signal verified ownership. Consumed by share gating to decide
    # whether to trust the email claim for invite matching.
    email_verified: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


def is_auth_required() -> bool:
    """
    Check if authentication is required for all API routes.

    Controlled via env var NOOBBOOK_AUTH_REQUIRED.
    """
    value = os.getenv("NOOBBOOK_AUTH_REQUIRED", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _get_bearer_token() -> Optional[str]:
    """
    Extract the JWT from the request.

    Checks Authorization header first, then falls back to ?token= query parameter.
    The query param fallback is needed for browser elements like <img>, <video>,
    <audio>, and <iframe> that can't send custom headers.
    """
    auth = request.headers.get("Authorization", "")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None
    # Fallback: check query parameter for browser elements (img, video, etc.)
    return request.args.get("token") or None


def _load_role_from_users_table(user_id: str) -> Optional[str]:
    if not is_supabase_enabled():
        return None
    try:
        supabase = get_supabase()
        resp = supabase.table("users").select("role").eq("id", user_id).execute()
        if resp.data and isinstance(resp.data, list):
            role = (resp.data[0].get("role") or "").strip().lower()
            return role if role in _VALID_ROLES else None
    except Exception:
        return None
    return None


def get_request_identity() -> RequestIdentity:
    """
    Resolve the current request's identity + role.

    Priority:
    1) Supabase Auth JWT (Authorization: Bearer <jwt>) if Supabase configured
    2) Single-user fallback (DEFAULT_USER_ID as admin/user depending on NOOBBOOK_AUTH_REQUIRED)

    Per-request caching: result is stashed on Flask's `g` so multiple
    callers within the same request (the before_request hook,
    @require_admin, the route's own use, etc.) don't each rebuild the
    identity. Without this, a single request hitting an admin endpoint
    can trigger 3+ duplicate Kong roundtrips just to look up the role.
    """
    cached = getattr(g, "_rbac_identity", None)
    if cached is not None:
        return cached

    identity = _resolve_identity()
    try:
        g._rbac_identity = identity
    except RuntimeError:
        # Outside an app context (e.g. background thread). Skip cache.
        pass
    return identity


def _resolve_identity() -> RequestIdentity:
    # 1) Supabase Auth JWT — local decode when JWT_SECRET is configured,
    #    network roundtrip otherwise (matches auth_middleware behavior).
    token = _get_bearer_token()
    if token and is_supabase_enabled():
        # Fast path: decode the JWT locally. user_id + email come from
        # claims; role still needs a Postgrest lookup but that's cheap
        # (~5ms vs ~50-100ms for the Kong/GoTrue path).
        if _JWT_SECRET:
            try:
                claims = jwt.decode(
                    token,
                    _JWT_SECRET,
                    algorithms=["HS256"],
                    audience=_JWT_AUDIENCE,
                )
                user_id = claims.get("sub")
                email = claims.get("email")
                # Trust ONLY `email_confirmed_at` — it's set server-side
                # by GoTrue when the user completes email verification
                # and ends up in the JWT's signed claims, NOT writable
                # by the user. `user_metadata.email_verified` maps to
                # `raw_user_meta_data` which any authenticated caller
                # can overwrite via `auth.updateUser({data: {...}})`, so
                # treating it as a verification signal is a forgeable
                # gate. Top-level `email_verified` is non-standard in
                # GoTrue v2 and not consistently populated, so we don't
                # honour it either. If `email_confirmed_at` isn't in the
                # token, default to False and rely on the slow path
                # (auth.get_user()) below for an authoritative check.
                email_verified = bool(claims.get("email_confirmed_at"))
                if user_id:
                    role = _load_role_from_users_table(str(user_id)) or ROLE_USER
                    return RequestIdentity(
                        user_id=str(user_id),
                        email=str(email) if email else None,
                        role=role,
                        is_authenticated=True,
                        email_verified=email_verified,
                    )
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                # Local decode rejected — fall through to network path
                # so we have a single source-of-truth error message.
                pass
            except Exception as e:
                logger.warning("Local JWT decode in rbac raised %s: %s", type(e).__name__, e)

        # Slow path: original Supabase Auth roundtrip. Only reached
        # when JWT_SECRET isn't set or local decode unexpectedly failed.
        # Dedicated client so gotrue's auth-event listener can't flip the
        # data singleton's role to authenticated (see
        # supabase_client.get_auth_verifier_client for the full incident
        # write-up).
        try:
            supabase = get_auth_verifier_client()
            user_resp = supabase.auth.get_user(token)
            user = getattr(user_resp, "user", None) or user_resp
            user_id = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
            email = getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)
            # GoTrue marks verified mailboxes with a non-null
            # `email_confirmed_at` timestamp. Some client versions also
            # expose `email_verified` directly — accept either.
            confirmed_at = (
                getattr(user, "email_confirmed_at", None)
                or (user.get("email_confirmed_at") if isinstance(user, dict) else None)
            )
            email_verified = bool(
                confirmed_at
                or getattr(user, "email_verified", False)
                or (user.get("email_verified") if isinstance(user, dict) else False)
            )
            if user_id:
                role = _load_role_from_users_table(user_id) or ROLE_USER
                return RequestIdentity(
                    user_id=str(user_id),
                    email=str(email) if email else None,
                    role=role,
                    is_authenticated=True,
                    email_verified=email_verified,
                )
        except Exception:
            pass  # Fall through to single-user mode

    # Single-user fallback. The previous dev-headers branch
    # (X-NoobBook-User-Id / X-NoobBook-Role) was removed — it
    # unconditionally trusted the caller's claimed identity which
    # broke the share-route invariant that unauthenticated callers
    # cannot fork into another user's workspace. Local development
    # should use a real JWT (GoTrue sign-in) or the single-user
    # fallback below.
    auth_required = is_auth_required()
    fallback_role = ROLE_ADMIN if not auth_required else ROLE_USER
    return RequestIdentity(
        user_id=DEFAULT_USER_ID,
        email=None,
        role=fallback_role,
        is_authenticated=False,
        email_verified=False,
    )


def require_admin(fn: T) -> T:
    """Decorator to enforce admin role."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        identity = get_request_identity()
        if is_auth_required() and not identity.is_authenticated:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Authentication required",
                        "required_role": ROLE_ADMIN,
                    }
                ),
                401,
            )
        if not identity.is_admin:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Admin access required",
                        "required_role": ROLE_ADMIN,
                        "role": identity.role,
                    }
                ),
                403,
            )
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_auth(fn: T) -> T:
    """Decorator to enforce authenticated user (any role)."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        if not is_auth_required():
            return fn(*args, **kwargs)

        identity = get_request_identity()
        if not identity.is_authenticated:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Authentication required",
                    }
                ),
                401,
            )
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_permission(category: str, item: str | None = None):
    """
    Decorator to enforce per-user module permissions.

    Educational Note: Works alongside @require_auth / @require_admin.
    Admins always pass (they have full access). For non-admin users,
    checks the permissions JSONB on the users table.

    Args:
        category: Permission category (e.g., "data_sources", "studio")
        item: Optional sub-item (e.g., "database", "flow_diagrams")

    Usage:
        @require_permission("data_sources", "database")
        def add_database_source(project_id):
            ...
    """
    def decorator(fn: T) -> T:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            identity = get_request_identity()

            # Admins always have full access
            if identity.is_admin:
                return fn(*args, **kwargs)

            # Check permission for non-admin users
            from app.services.auth.permissions import user_has_permission

            if not user_has_permission(identity.user_id, category, item):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "This feature is not available for your account. Contact your admin.",
                        }
                    ),
                    403,
                )
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
