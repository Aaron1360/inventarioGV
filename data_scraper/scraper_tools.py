import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urljoin
from contextlib import contextmanager

load_dotenv()

LOGIN_URL = os.getenv("LOGIN_URL")
POS_URL = os.getenv("POS_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

def build_login_payload():
    """Build the payload for the login form."""
    payload = {
        "uid": USERNAME,
        "pass": PASSWORD,
        "ok": "1"
    }
    return payload

@contextmanager
def authenticated_session():
    """Context manager for an authenticated session."""
    session = requests.Session()
    payload = build_login_payload()
    response = session.post(LOGIN_URL, data=payload)
    if not response.ok:
        raise Exception("Login failed")
    try:
        yield session
    finally:
        session.close()

def full_url(base_url: str, relative_path: str):
    """Generate full URL from base URL and relative path."""
    return urljoin(base_url, relative_path)
    
def save_html_from_link(session, link: str, filename: str):
    """Access the page at the given link (relative to POS_URL), and save its HTML content."""
    url = full_url(POS_URL, link)
    response = session.get(url)
    if response.ok:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)
    else:
        raise Exception(f"Failed to fetch page for link: {link}")

def select_store(session, store_name: str):
    """Find the store link for the given store name, and return the response after selecting the store."""
    store_page_url = full_url(POS_URL, '?modulo=pdv&accion=tienda')
    response = session.get(store_page_url)
    if not response.ok:
        raise Exception("Failed to fetch store selection page")
    soup = BeautifulSoup(response.text, "html.parser")
    store_link = None
    for a in soup.find_all('a'):
        if store_name.lower() in a.text.lower():
            store_link = a.get('href')
            break
    if not store_link:
        raise Exception(f"Store '{store_name}' not found on the page")
    select_url = full_url(POS_URL, store_link)
    select_response = session.get(select_url)
    if select_response.ok:
        return select_response
    else:
        raise Exception(f"Failed to select store '{store_name}'")

if __name__ == "__main__":
    with authenticated_session() as session:
        print("Authenticated successfully.")
        response = select_store(session, 'CENTRAL DE ABASTOS')
        with open('central_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("Page saved successfully.")
        
    print("Session closed.")