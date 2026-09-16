"""Shared rate-limiter instance.

Imported by both main.py and v2/auth.py so the same in-memory bucket is
used for both the legacy /api/auth/login and the v2 /api/v2/auth/login
endpoints. Avoids a circular import (main → v2 → main).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
