from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import anime, discover, recommend

app = FastAPI(title="AnimeSZN")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend.router)
app.include_router(anime.router)
app.include_router(discover.router)
