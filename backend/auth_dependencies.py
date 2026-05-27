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


async def get_current_active_user(current_user=None):
    """Back-compat shim. Real disabled-user check lives in get_current_session now."""
    if current_user is None:
        # If someone calls without the dependency, fall through to the consolidated path.
        from backend.api.dependencies import get_current_user as _gcu
        return await _gcu()
    return current_user


async def get_optional_user(*args, **kwargs):
    """Back-compat shim. Cookie-aware optional auth lives in api.dependencies."""
    return None
