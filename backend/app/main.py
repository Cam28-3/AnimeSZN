from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import access_gate_middleware
from app.config import settings
from app.rate_limit import limiter
from app.routers import anime, discover, recommend

app = FastAPI(title="AnimeSZN")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=access_gate_middleware)

# CORS must stay the outermost middleware (added last) so it can attach CORS headers to
# every response, including a 401 from the access gate -- otherwise the browser blocks the
# frontend from ever reading the rejection and it looks like a network failure, not a bad key.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend.router)
app.include_router(anime.router)
app.include_router(discover.router)


# Liveness check -- exempt from CORS/auth concerns, used by deploy platforms for healthchecks.
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
