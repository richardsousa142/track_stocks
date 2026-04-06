"""FastAPI backend para o Luria — análise de ativos B3."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.ativos import router as ativos_router
from .routers.valuation import router as valuation_router
from .routers.fiis import router as fiis_router

app = FastAPI(
    title="Luria API",
    description="API de análise de ativos da B3",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ativos_router)
app.include_router(valuation_router)
app.include_router(fiis_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
