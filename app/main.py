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

from data_scraper.scraper_tools import authenticated_session

load_dotenv()
LOGIN_URL = os.getenv("LOGIN_URL")
PRODUCTS_URL = os.getenv("PRODUCTS_URL")
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

@app.get("/")
def root(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login")
    # Render homepage if authenticated
    return templates.TemplateResponse("index.html", {"request": request})
