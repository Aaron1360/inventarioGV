import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urljoin
from contextlib import contextmanager
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

LOGIN_URL = os.getenv("LOGIN_URL")
POS_URL = os.getenv("POS_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

EXCLUDED_LINES = [
    "IMPORTE",
    "FLETE"
]

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

def get_product_lines(session, store_name: str):
    """Return a list of product lines for the selected store, excluding unwanted lines, only from panel_lineas div."""
    response = select_store(session, store_name)
    soup = BeautifulSoup(response.text, "html.parser")
    product_lines = []
    panel_lineas = soup.find('div', class_='panel_lineas')
    if panel_lineas:
        for a in panel_lineas.find_all('a'):
            line_text = a.text.strip().upper()
            if line_text and line_text not in EXCLUDED_LINES:
                product_lines.append({
                    "name": line_text,
                    "href": a.get('href')
                })
    return product_lines

def get_article_panel(session, relative_href: str):
    """Generic function to extract <a> tags from <div class=panel_articulos> for any given page."""
    url = full_url(POS_URL, relative_href)
    response = session.get(url)
    if not response.ok:
        raise Exception(f"Failed to fetch page: {relative_href}")
    soup = BeautifulSoup(response.text, "html.parser")
    panel_articulos = soup.find('div', class_='panel_articulos')
    items = []
    if panel_articulos:
        for a in panel_articulos.find_all('a'):
            text = a.text.strip()
            href = a.get('href')
            if text:
                items.append({"name": text, "href": href})
    return items

def get_dataframe(session, store_name: str, max_threads: int = 28):
    """Scrape all products for a store using multithreading and return a pandas DataFrame."""
    all_products = []
    product_lines = get_product_lines(session, store_name)
    # Use 4 threads per line
    num_threads = min(len(product_lines) * 4, max_threads)
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        article_futures = {
            executor.submit(get_article_panel, session, line['href']): line['name']
            for line in product_lines
        }
        for future in as_completed(article_futures):
            line_name = article_futures[future]
            try:
                articles = future.result()
            except Exception:
                continue
            # Thread pool for presentations per article
            with ThreadPoolExecutor(max_workers=4) as pres_executor:
                pres_futures = {
                    pres_executor.submit(get_article_panel, session, article['href']): article['name']
                    for article in articles
                }
                for pres_future in as_completed(pres_futures):
                    article_name = pres_futures[pres_future]
                    try:
                        presentations = pres_future.result()
                    except Exception:
                        continue
                    # Thread pool for stock per presentation
                    with ThreadPoolExecutor(max_workers=4) as stock_executor:
                        stock_futures = {
                            stock_executor.submit(get_article_panel, session, presentation['href']): presentation['name']
                            for presentation in presentations
                        }
                        for stock_future in as_completed(stock_futures):
                            presentation_name = stock_futures[stock_future]
                            try:
                                stock_list = stock_future.result()
                            except Exception:
                                continue
                            for stock in stock_list:
                                all_products.append({
                                    "line": line_name,
                                    "name": article_name,
                                    "presentation": presentation_name,
                                    "stock": stock['name']
                                })
    # Remove duplicates
    df = pd.DataFrame(all_products).drop_duplicates()
    return df

def save_dataframe_to_csv(df, filename="inventory.csv"):
    """Save the DataFrame to a CSV file."""
    df.to_csv(filename, index=False)
    print(f"DataFrame saved to {filename}")

if __name__ == "__main__":
    with authenticated_session() as session:
        store_name = "11 DE JULIO"
        df = get_dataframe(session, store_name)
        save_dataframe_to_csv(df)
        print("DONE")
