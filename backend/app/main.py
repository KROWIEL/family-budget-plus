from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import accounts, auth, categories, debts, profile, rates, stats, transactions
from .seed import run_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    run_seed()
    yield


app = FastAPI(title="Budget+", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(debts.router)
app.include_router(transactions.router)
app.include_router(stats.router)
app.include_router(rates.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ==== Раздача собранного фронтенда (SPA) ====
_assets_dir = settings.static_dir / "assets"
if _assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    # Отдаём реальный файл из статики, если он существует (favicon.svg, robots.txt и т.п.)
    if full_path:
        static_root = settings.static_dir.resolve()
        candidate = (static_root / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(static_root):
            return FileResponse(candidate)

    index = settings.static_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend не собран"}, status_code=404)
