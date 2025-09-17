# GV_inventario

A web-based inventory scraper and viewer for GV, built with Python (FastAPI) and a simple web frontend served directly by the backend.

## Project Structure
```
inventarioGV/
│
├── app/            # Backend app (FastAPI routes, logic, main.py)
├── data_scraper/   # Scraper modules
├── static/         # Frontend JS and CSS
├── templates/      # HTML templates (Jinja2)
├── requirements.txt
├── Dockerfile
├── README.md
└── .env
```

## Tech Stack
- Python (FastAPI)
- Jinja2 (HTML templates)
- Vanilla JavaScript & CSS (frontend)
- Docker (containerization)

## Usage
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the backend with Uvicorn:
   ```bash
   uvicorn app.main:app --reload
   ```
3. Access the web interface at `http://localhost:8000` (or the port you configure).

## Features
- Login page
- Scrapes inventory data
- Displays scraped information in browser

## Docker
Build and run with Docker:
```bash
docker build -t gv_inventario .
docker run -p 8000:8000 gv_inventario
```

---
Feel free to customize and extend as needed!