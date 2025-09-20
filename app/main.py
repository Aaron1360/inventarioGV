# app/main.py
import os
from jose import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, Request, Response
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from data_scraper.scraper_tools import authenticated_session, get_available_stores, get_dataframe, save_dataframe_to_csv

load_dotenv()
LOGIN_URL = os.getenv("LOGIN_URL")
POS_URL = os.getenv("POS_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI()

# Mount static files for frontend assets
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
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

last_scraped_df = None
last_scraped_store_name = None

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
    if username == USERNAME and password == PASSWORD:
        access_token = create_access_token({"sub": username})
        response = JSONResponse({"success": True, "message": "Login successful", "access_token": access_token})
        response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES*60)
        return response
    else:
        return JSONResponse({"success": False, "message": "Usuario y/o contraseña incorrectos"}, status_code=401)

@app.post("/logout")
def logout(response: Response):
    response = JSONResponse({"success": True, "message": "Logged out"})
    response.delete_cookie(key="access_token")
    return response

@app.get("/stores")
def list_stores():
    with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
        stores = get_available_stores(session, POS_URL)
    return stores

@app.get("/scrape")
def scrape_inventory(store_name: str = Query(...)):
    global last_scraped_df, last_scraped_store_name
    try:
        # Scrape and cache only if not already cached for this store
        if last_scraped_df is None or last_scraped_store_name != store_name:
            with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
                df = get_dataframe(session, store_name, POS_URL)
            last_scraped_df = df
            last_scraped_store_name = store_name
        else:
            df = last_scraped_df
        scrape_status["last_scrape"] = datetime.utcnow().isoformat()
        scrape_status["success"] = True
        scrape_status["error"] = None
        return df.to_dict(orient="records")
    except Exception as e:
        scrape_status["last_scrape"] = datetime.utcnow().isoformat()
        scrape_status["success"] = False
        scrape_status["error"] = str(e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/save")
def save_inventory():
    global last_scraped_df, last_scraped_store_name
    if last_scraped_df is None or last_scraped_store_name is None:
        return JSONResponse({"success": False, "error": "No scraped data available. Please call /scrape first."}, status_code=400)
    filename = save_dataframe_to_csv(last_scraped_df, last_scraped_store_name)
    return FileResponse(filename, media_type="text/csv", filename=filename)

@app.get("/status")
def get_status():
    return scrape_status

@app.get("/")
def root(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login")
    # If you want to show a homepage, render a template here
    return RedirectResponse(url="/login")  # Or render your main page if authenticated