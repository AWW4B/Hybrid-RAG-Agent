# =============================================================================
# app/core/limiter.py
# Shared slowapi Limiter instance.
#
# Extracted to its own module to break the circular import between:
#   app.main   (creates limiter, imports router from routes.py)
#   app.routes (needs limiter, imports from app.main → circular)
#
# Both app.main and app.api.routes now import from here instead.
# =============================================================================

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
