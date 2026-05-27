"""
DEPRECATED — use ``backend.api.dependencies`` instead.

This module previously declared Bearer-only auth dependencies that did not
support HttpOnly cookies, did not check the user's active status against the
database (TODO comment that was never resolved), and duplicated logic that
already lived in ``backend.api.dependencies``.

For any new code, import from ``backend.api.dependencies``:

    from backend.api.dependencies import get_current_user, get_current_session

The names below are kept as thin re-exports so any in-flight imports keep
working. A future cleanup can remove this file entirely once nothing imports
from it.
"""

from __future__ import annotations

import warnings
from typing import Any, Optional

from fastapi import Depends, Header, Request

from backend.api.dependencies import (  # noqa: F401 — re-export for back-compat
    get_admin_session,
    get_current_session,
    get_current_user,
)

warnings.warn(
    "backend.auth_dependencies is deprecated; import from backend.api.dependencies instead.",
    DeprecationWarning,
    stacklevel=2,
)


# get_current_user is itself a FastAPI dependency (declares session via
# Depends(get_current_session)); it can't be called bare. The shim accepts
# the resolved user as a sub-dependency so FastAPI does the injection.
async def get_current_active_user(
    current_user: Any = Depends(get_current_user),
) -> Any:
    """Back-compat shim. Real disabled-user check lives in get_current_session."""
    return current_user


async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[Any]:
    """Cookie- and Bearer-aware optional auth.

    Returns the user dict if a valid session exists, otherwise None.
    The prior shim unconditionally returned None, silently breaking any
    optional-auth route that depended on it.
    """
    try:
        from backend.api.dependencies import (
            get_auth_service_dep,
            get_rate_limiter_dep,
            get_current_session,
        )
        token_and_user = await get_current_session(
            request=request,
            authorization=authorization,
            auth_service=get_auth_service_dep(),
            rate_limiter=get_rate_limiter_dep(),
        )
        _, user = token_and_user
        return user
    except Exception:
        return None
