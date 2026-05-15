"""
Share Service — CRUD over the project_shares table (Roadmap #15).

A share is a token that grants read-only access to a project's chats.
Two modes:

* **public**  — anyone with the URL gets access (no auth required).
* **invited** — only logged-in users whose email matches a row in
  ``invited_emails`` get access.

Shares can be **revoked** (sets ``revoked_at``) or **expire** (the
``expires_at`` timestamp passes). Either condition makes the share
inactive — the row stays in the table for audit but lookup fails.

Token generation uses ``secrets.token_urlsafe(32)`` (256 bits of entropy,
URL-safe base64), making brute-force enumeration infeasible. Tokens are
unique-indexed at the DB level.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)

# Token byte length — token_urlsafe(32) returns ~43 chars (32 bytes b64).
_TOKEN_BYTES = 32

VALID_MODES = {"public", "invited"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_active(row: Dict[str, Any]) -> bool:
    """Mirrors the SQL is_share_active() function for in-process checks."""
    if not row:
        return False
    if row.get("revoked_at"):
        return False
    expires_at = row.get("expires_at")
    if expires_at:
        # Supabase returns ISO strings; normalize for comparison.
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except Exception:
                return False
        if expires_at <= _now():
            return False
    return True


def _generate_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def _client():
    if not is_supabase_enabled():
        raise RuntimeError("Supabase is not configured.")
    return get_supabase()


def create_share(
    project_id: str,
    created_by: str,
    mode: str,
    invited_emails: Optional[List[str]] = None,
    expires_in_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a new share row for a project.

    Args:
        project_id: The project being shared.
        created_by: The owner user's id (already validated upstream).
        mode: "public" or "invited".
        invited_emails: Required and non-empty when mode == "invited".
                        Lower-cased and de-duped for stable matching.
        expires_in_days: 7, 30, or None. None means the share never expires.

    Returns:
        The inserted row (including the generated token).
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    normalized_emails: List[str] = []
    if mode == "invited":
        if not invited_emails:
            raise ValueError("invited mode requires at least one email")
        # Lower-case + de-dup. We compare against `users.email` which Supabase
        # also stores lower-cased, so consistent casing avoids subtle misses.
        seen = set()
        for raw in invited_emails:
            if not raw:
                continue
            email = raw.strip().lower()
            if email and email not in seen:
                seen.add(email)
                normalized_emails.append(email)
        if not normalized_emails:
            raise ValueError("invited mode requires at least one valid email")

    expires_at: Optional[str] = None
    if expires_in_days is not None:
        if expires_in_days <= 0:
            raise ValueError("expires_in_days must be positive (or None for never)")
        expires_at = (_now() + timedelta(days=expires_in_days)).isoformat()

    row = {
        "project_id": project_id,
        "token": _generate_token(),
        "mode": mode,
        "invited_emails": normalized_emails,
        "created_by": created_by,
        "expires_at": expires_at,
    }

    client = _client()
    response = client.table("project_shares").insert(row).execute()
    if not response.data:
        raise RuntimeError("Failed to create project share")
    return response.data[0]


def list_shares_for_project(project_id: str) -> List[Dict[str, Any]]:
    """List all share rows for a project (active + revoked + expired)."""
    client = _client()
    response = (
        client.table("project_shares")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_share_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Look up a share by its token. Returns the raw row regardless of
    active/revoked/expired status — callers decide what to do with it."""
    if not token:
        return None
    client = _client()
    response = (
        client.table("project_shares")
        .select("*")
        .eq("token", token)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def get_share_by_id(share_id: str, project_id: str) -> Optional[Dict[str, Any]]:
    """Look up a specific share row scoped to a project (for owner ops)."""
    client = _client()
    response = (
        client.table("project_shares")
        .select("*")
        .eq("id", share_id)
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def revoke_share(share_id: str, project_id: str) -> bool:
    """Mark a share as revoked. Idempotent — already-revoked shares
    return True without re-stamping the timestamp."""
    existing = get_share_by_id(share_id, project_id)
    if not existing:
        return False
    if existing.get("revoked_at"):
        return True
    client = _client()
    client.table("project_shares").update({
        "revoked_at": _now().isoformat(),
    }).eq("id", share_id).eq("project_id", project_id).execute()
    return True


def is_share_usable(row: Dict[str, Any]) -> bool:
    """Public wrapper around the active check so callers don't import _is_active."""
    return _is_active(row)


def viewer_invited(
    row: Dict[str, Any],
    viewer_user_id: Optional[str],
    viewer_email: Optional[str],
    email_verified: bool,
) -> bool:
    """Check whether a viewer is allowed through an invited-mode share.

    UUID-first with lazy email→user_id promotion. The historical
    plain-email check was only safe when the JWT email claim was
    operator-verified — with ``ENABLE_EMAIL_AUTOCONFIRM=true`` it
    wasn't, which let any signed-up attacker spoof an invitee by
    choosing their own email at signup.

    Resolution order:

    1. If ``viewer_user_id`` is already in ``invited_user_ids`` →
       allow. Fast path, no DB write. This is the only path future
       requests hit after first claim.
    2. Else if ``email_verified=True`` and ``viewer_email`` is in
       ``invited_emails`` → allow and lazily promote: move the
       invitee from the email list to the user_id list in one
       atomic update. One-time per invitee.
    3. Else → deny.

    Public-mode rows always return True (mode-mismatch is the caller's
    concern).
    """
    if row.get("mode") == "public":
        return True

    invited_user_ids = row.get("invited_user_ids") or []
    if viewer_user_id and viewer_user_id in invited_user_ids:
        return True

    # Email fallback path — strictly gated on a verified mailbox.
    if not (email_verified and viewer_email and viewer_user_id):
        return False

    normalized = viewer_email.strip().lower()
    invited_emails = row.get("invited_emails") or []
    matched_email = next(
        (e for e in invited_emails if e and e.lower() == normalized),
        None,
    )
    if not matched_email:
        return False

    # Promote: remove the matched email, add the user_id. Atomic
    # server-side via the `promote_share_invitee` RPC (migration 00036)
    # — using array_remove / array_append on the live row, not a
    # Python-side read-modify-write. This is what prevents two
    # concurrent invitees from clobbering each other's promotion and
    # leaving one of them stranded outside both arrays.
    #
    # Best-effort: if the RPC call fails (network blip / RLS / migration
    # not yet applied) we still grant access for THIS request. The next
    # request from the same invitee will retry the promotion. We never
    # cache a failed promotion in memory so retries stay correct.
    try:
        client = _client()
        client.rpc(
            "promote_share_invitee",
            {
                "p_share_id": row["id"],
                "p_email": matched_email,
                "p_user_id": viewer_user_id,
            },
        ).execute()
    except Exception as e:
        logger.warning(
            "viewer_invited: failed to promote invitee email→user_id for share %s: %s",
            row.get("id"), e,
        )

    return True


def email_invited(row: Dict[str, Any], email: Optional[str]) -> bool:  # pragma: no cover
    """Deprecated — kept as a no-arg-compatible shim so any out-of-tree
    callers fail loudly with a clear stack rather than silently passing
    the old plain-email gate. Real call sites use ``viewer_invited``."""
    raise NotImplementedError(
        "share_service.email_invited has been replaced by viewer_invited; "
        "callers must pass viewer_user_id and email_verified."
    )
