import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == USERNAME and password == PASSWORD:
        # Redirect to data page or show scraped info
        return RedirectResponse(url="/data", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "error": "Invalid credentials"})

@app.get("/data", response_class=HTMLResponse)
def data_page(request: Request):
    # TODO: Add scraping logic and pass data to template
    scraped_data = "Scraped info goes here"
    return templates.TemplateResponse("index.html", {"request": request, "data": scraped_data})

