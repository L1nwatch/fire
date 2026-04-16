from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import connect, init_db, load_finance_state, save_finance_state

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

app = FastAPI(title="Fire")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    with connect() as conn:
        init_db(conn)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/finance")
def get_finance() -> dict[str, Any]:
    with connect() as conn:
        init_db(conn)
        return load_finance_state(conn)


@app.put("/api/finance")
def put_finance(state: dict[str, Any]) -> dict[str, bool]:
    with connect() as conn:
        init_db(conn)
        save_finance_state(conn, state)
    return {"ok": True}


assets_dir = FRONTEND_DIST / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    index_html = FRONTEND_DIST / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    return JSONResponse(
        status_code=503,
        content={"detail": "Frontend build not found. Run npm run build in frontend."},
    )
