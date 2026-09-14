# app/main.py
import os
import logging
import time
from jose import jwt
import pytz
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, Request, Response, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jose import JWTError
from io import BytesIO
from typing import Any
import pandas as pd
from threading import Lock, Thread

from data_scraper.scraper_tools import (
    authenticated_session,
    build_store_report,
    fetch_lineas_dataframe,
)
from data_scraper.dataframe_tools import (
    dataframe_to_inventory_xlsx,
    filter_inventory_dataframe,
)

load_dotenv()
LOGIN_URL = os.getenv("LOGIN_URL")
LINEAS_URL = os.getenv("LINEAS_URL")
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
COOLDOWN_SECONDS = 60

app = FastAPI(docs_url=None, redoc_url=None)

# Mount static files for frontend assets
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://localhost:8000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Jinja2 templates setup
templates = Jinja2Templates(directory="templates")

scrape_status = {
    "last_scrape": None,
    "success": None,
    "error": None
}

# Per-user cache
user_cache = {}
scrape_jobs = {}
scrape_jobs_lock = Lock()
last_manual_scrape = {}
logger = logging.getLogger(__name__)

def _get_inventory_dataframe(username: str):
    """Return the dataframe from the primary cache or completed job backup."""
    dataframe = user_cache.get(username)
    if dataframe is not None:
        return dataframe
    return scrape_jobs.get(username, {}).get("dataframe")

def _dataframe_records(dataframe) -> list[dict[str, Any]]:
    """Convert dataframe values to JSON-safe records."""
    records = dataframe.to_dict(orient="records")
    return [
        {
            key: None if pd.isna(value) else value
            for key, value in record.items()
        }
        for record in records
    ]

def _scrape_inventory_dataframe():
    """Scrape the complete inventory dataframe before user filtering."""
    logger.info("Scraper: starting inventory build")
    with authenticated_session(LOGIN_URL, APP_USERNAME, APP_PASSWORD) as session:
        logger.info("Scraper: authenticated against external inventory site")
        lineas = fetch_lineas_dataframe(session, LINEAS_URL)
        logger.info("Scraper: fetched %d lines", len(lineas))
        return build_store_report(lineas, session)

def _run_inventory_scrape(username: str):
    """Run the scraper in the background and update the user's job state."""
    try:
        logger.info("Scraper: background job started for user %s", username)
        dataframe = _scrape_inventory_dataframe()
        logger.info("Scraper: dataframe completed with %d rows", len(dataframe))
        with scrape_jobs_lock:
            user_cache[username] = dataframe
            scrape_jobs[username] = {
                "status": "completed",
                "message": "Inventario listo.",
                "total": len(dataframe),
                "built_at": datetime.now(pytz.timezone("America/Mexico_City")).isoformat(),
                "dataframe": dataframe,
            }
    except Exception as error:
        logger.exception("Scraper: failed for user %s", username)
        with scrape_jobs_lock:
            scrape_jobs[username] = {
                "status": "error",
                "message": str(error),
                "total": 0,
            }

def _start_inventory_scrape(username: str):
    """Start one background scrape unless one is already running."""
    with scrape_jobs_lock:
        current = scrape_jobs.get(username, {}).get("status")
        if current == "running":
            return False
        scrape_jobs[username] = {
            "status": "running",
            "message": "Accediendo a https://grupogranvalle.com/sistema/",
            "total": 0,
        }
        user_cache.pop(username, None)
    Thread(target=_run_inventory_scrape, args=(username,), daemon=True).start()
    return True

def get_token_from_request(request: Request):
    # Try to get token from Authorization header first
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    # Fallback to cookie
    token = request.cookies.get("access_token")
    if token:
        return token
    raise HTTPException(status_code=401, detail="No access token found")

# Helper to get current username from JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
def get_current_username(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def get_authenticated_username(request: Request):
    """Read the authenticated username from a Bearer header or access cookie."""
    try:
        token = get_token_from_request(request)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...), response: Response = None):
    if username == APP_USERNAME and password == APP_PASSWORD:
        logger.info("App login accepted for user %s; starting scraper", username)
        access_token = create_access_token({"sub": username})
        _start_inventory_scrape(username)
        response = JSONResponse({"success": True, "message": "Login successful", "access_token": access_token})
        response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES*60)
        return response
    else:
        print("Login failed: credentials do not match.")
        return JSONResponse({"success": False, "message": "Usuario y/o contraseña incorrectos"}, status_code=401)

@app.post("/logout")
def logout(response: Response):
    response = JSONResponse({"success": True, "message": "Logged out"})
    response.delete_cookie(key="access_token")
    return response

@app.get("/")
def root(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login")
    # Render homepage if authenticated
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/inventory/scrape")
def scrape_inventory(username: str = Depends(get_authenticated_username)):
    """Scrape and return the complete inventory dataframe without filters."""
    now = time.monotonic()
    with scrape_jobs_lock:
        elapsed = now - last_manual_scrape.get(username, 0)
        remaining = max(0, int(COOLDOWN_SECONDS - elapsed))
        if remaining > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Espera {remaining} segundos antes de actualizar nuevamente.",
                headers={"Retry-After": str(remaining)},
            )
        last_manual_scrape[username] = now
    _start_inventory_scrape(username)
    dataframe = _get_inventory_dataframe(username)
    if dataframe is None:
        return inventory_status(username)
    return {
        "total": len(dataframe),
        "columns": list(dataframe.columns),
        "data": _dataframe_records(dataframe),
    }

@app.get("/api/inventory")
def get_inventory(username: str = Depends(get_authenticated_username)):
    """Return the last complete dataframe scraped for the current user."""
    dataframe = _get_inventory_dataframe(username)
    if dataframe is None:
        logger.error(
            "Inventory cache missing for user %s; scrape job status is %s",
            username,
            scrape_jobs.get(username, {}).get("status", "unknown"),
        )
        raise HTTPException(
            status_code=404,
            detail="No inventory dataframe is loaded. Run POST /api/inventory/scrape first.",
        )
    return {
        "total": len(dataframe),
        "columns": list(dataframe.columns),
        "data": _dataframe_records(dataframe),
    }

@app.get("/api/inventory/export")
def export_inventory(
    tienda: str,
    linea: str | None = None,
    sublinea: str | None = None,
    username: str = Depends(get_authenticated_username),
):
    """Export the current filtered inventory into three Excel worksheets."""
    dataframe = _get_inventory_dataframe(username)
    if dataframe is None:
        raise HTTPException(status_code=404, detail="No inventory dataframe is loaded.")
    try:
        filtered = filter_inventory_dataframe(
            dataframe,
            tienda=tienda,
            linea=linea or None,
            sublinea=sublinea or None,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    workbook = dataframe_to_inventory_xlsx(filtered)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=inventario.xlsx"
        },
    )

@app.get("/api/inventory/status")
def inventory_status(username: str = Depends(get_authenticated_username)):
    """Return whether a complete unfiltered dataframe is available."""
    dataframe = _get_inventory_dataframe(username)
    job = scrape_jobs.get(username, {})
    job_status = job.get("status", "idle")
    if job_status == "completed" and dataframe is None:
        job_status = "error"
        job = {
            **job,
            "message": "El scraper terminó, pero el dataframe no quedó disponible.",
        }
    return {
        "loaded": dataframe is not None,
        "status": job_status,
        "message": job.get("message", ""),
        "total": job.get("total", len(dataframe) if dataframe is not None else 0),
        "built_at": job.get("built_at"),
        "cooldown": COOLDOWN_SECONDS,
    }

@app.get("/api/inventory/stores")
def inventory_stores(username: str = Depends(get_authenticated_username)):
    """Return the stores present in the current user's dataframe."""
    dataframe = _get_inventory_dataframe(username)
    if dataframe is None:
        raise HTTPException(
            status_code=404,
            detail="No inventory dataframe is loaded.",
        )
    stores = sorted(dataframe["TIENDA"].dropna().unique().tolist())
    return {"stores": stores}

@app.delete("/api/inventory")
def clear_inventory(username: str = Depends(get_authenticated_username)):
    """Clear the current user's cached dataframe."""
    user_cache.pop(username, None)
    scrape_jobs.pop(username, None)
    return {"success": True}
