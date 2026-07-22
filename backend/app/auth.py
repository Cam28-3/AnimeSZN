from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

ACCESS_KEY_HEADER = "X-AnimeSZN-Key"
_EXEMPT_PATHS = {"/health"}


# Gates every route behind a shared secret header, except health checks (deploy-platform
# probes have no way to attach a custom header) and CORS preflight (browsers send OPTIONS
# without app headers by design -- the actual request is still gated). A no-op when
# ACCESS_KEY is unset, so local dev is unaffected unless it's explicitly configured.
async def access_gate_middleware(request: Request, call_next):
    if not settings.access_key:
        return await call_next(request)
    if request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
        return await call_next(request)
    if request.headers.get(ACCESS_KEY_HEADER) != settings.access_key:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing access key"})
    return await call_next(request)
