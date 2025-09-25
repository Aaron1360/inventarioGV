# app/main.py
import os
from jose import jwt
import pytz
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, Request, Response, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from jose import JWTError
from io import BytesIO

from data_scraper.scraper_tools import authenticated_session, get_available_stores, get_dataframe, save_dataframe_to_csv, export_all_dataframes_to_excel, get_wholesale_dataframe, get_retail_dataframe, get_prices_dataframe

load_dotenv()
LOGIN_URL = os.getenv("LOGIN_URL")
POS_URL = os.getenv("POS_URL")
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
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
        access_token = create_access_token({"sub": username})
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

@app.get("/stores")
def list_stores():
    with authenticated_session(LOGIN_URL, APP_USERNAME, APP_PASSWORD) as session:
        stores = get_available_stores(session, POS_URL)
    return stores

@app.get("/scrape")
def scrape_inventory(store_name: str = Query(...), request: Request = None):
    token = get_token_from_request(request)
    now = datetime.utcnow()
    if token not in user_cache:
        user_cache[token] = {"df": None, "store_name": None, "last_scrape": None}
    cache = user_cache[token]
    # Cooldown logic
    last_scrape = cache.get("last_scrape")
    if last_scrape:
        if isinstance(last_scrape, str):
            last_scrape = datetime.fromisoformat(last_scrape)
        elapsed = (now - last_scrape).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            retry_after = int(COOLDOWN_SECONDS - elapsed)
            return JSONResponse({"success": False, "error": f"Debes esperar {retry_after} segundos antes de volver a actualizar."}, status_code=429)
    try:
        if cache["df"] is None or cache["store_name"] != store_name:
            with authenticated_session(LOGIN_URL, APP_USERNAME, APP_PASSWORD) as session:
                df = get_dataframe(session, store_name, POS_URL)
            cache["df"] = df
            cache["store_name"] = store_name
        else:
            df = cache["df"]
        cache["last_scrape"] = now.isoformat()
        scrape_status["last_scrape"] = now.isoformat()
        scrape_status["success"] = True
        scrape_status["error"] = None
        wholesale = get_wholesale_dataframe(df).to_dict(orient="records")
        retail = get_retail_dataframe(df).to_dict(orient="records")
        prices = get_prices_dataframe(df).to_dict(orient="records")
        return {"wholesale": wholesale, "retail": retail, "prices": prices}
    except Exception as e:
        scrape_status["last_scrape"] = now.isoformat()
        scrape_status["success"] = False
        scrape_status["error"] = str(e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/save")
def save_inventory(request: Request = None):
    token = get_token_from_request(request)
    if token not in user_cache or user_cache[token]["df"] is None or user_cache[token]["store_name"] is None:
        return JSONResponse({"success": False, "error": "No scraped data available. Please call /scrape first."}, status_code=400)
    df = user_cache[token]["df"]
    store_name = user_cache[token]["store_name"]
    tz = pytz.timezone("America/Mexico_City")
    now = datetime.now(tz)
    date_str = now.strftime('%Y%m%d')
    time_str = now.strftime('%H%M%S')
    safe_store = store_name.replace(' ', '_').replace('/', '_')
    filename = f"inventario_{safe_store}_{date_str}_{time_str}.xlsx"
    # Write Excel to memory
    output = BytesIO()
    export_all_dataframes_to_excel(df, output)
    output.seek(0)
    return Response(
        content=output.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/status")
def get_status():
    return scrape_status

@app.get("/")
def root(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login")
    # Render homepage if authenticated
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/clear_cache")
def clear_cache(request: Request):
    token = get_token_from_request(request)
    if token in user_cache:
        # Only clear data and store name, preserve last_scrape for cooldown
        last_scrape = user_cache[token].get("last_scrape")
        user_cache[token] = {"df": None, "store_name": None, "last_scrape": last_scrape}
        return JSONResponse({"success": True, "message": "Cache borrado correctamente."}, status_code=200)
    return JSONResponse({"success": False, "message": "No hay datos en caché para borrar."}, status_code=404)

@app.get("/cooldown_status")
def cooldown_status(request: Request):
    token = get_token_from_request(request)
    now = datetime.utcnow()
    cooldown = 0
    if token in user_cache:
        last_scrape = user_cache[token].get("last_scrape")
        if last_scrape:
            if isinstance(last_scrape, str):
                last_scrape = datetime.fromisoformat(last_scrape)
            elapsed = (now - last_scrape).total_seconds()
            if elapsed < COOLDOWN_SECONDS:
                cooldown = int(COOLDOWN_SECONDS - elapsed)
    return {"cooldown": cooldown}