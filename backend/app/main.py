from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.rate_limit import limiter
from app.routers import anime, discover, recommend

app = FastAPI(title="AnimeSZN")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
