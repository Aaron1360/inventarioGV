import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from contextlib import contextmanager
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import pytz

EXCLUDED_LINES = [
    "IMPORTE",
    "FLETE"
]

def build_login_payload(username, password):
    """Build the payload for the login form."""
    payload = {
        "uid": username,
        "pass": password,
        "ok": "1"
    }
    return payload

@contextmanager
def authenticated_session(login_url, username, password):
    """Context manager for an authenticated session."""
    session = requests.Session()
    payload = build_login_payload(username, password)
    response = session.post(login_url, data=payload)
    if not response.ok:
        raise Exception("Login failed")
    try:
        yield session
    finally:
        session.close()

def full_url(base_url: str, relative_path: str):
    """Generate full URL from base URL and relative path."""
    return urljoin(base_url, relative_path)

def get_available_stores(session, pos_url):
    """Return a list of available store names and their links from the store selection page."""
    store_page_url = full_url(pos_url, '?modulo=pdv&accion=tienda')
    response = session.get(store_page_url)
    if not response.ok:
        raise Exception("Failed to fetch store selection page")
    soup = BeautifulSoup(response.text, "html.parser")
    stores = []
    for a in soup.find_all('a'):
        store_name = a.text.strip()
        store_href = a.get('href')
        if store_name and store_href:
            stores.append({"name": store_name, "href": store_href})
    return stores

def select_store(session, store_name: str, pos_url):
    """Find the store link for the given store name, and return the response after selecting the store."""
    store_page_url = full_url(pos_url, '?modulo=pdv&accion=tienda')
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
    select_url = full_url(pos_url, store_link)
    select_response = session.get(select_url)
    if select_response.ok:
        return select_response
    else:
        raise Exception(f"Failed to select store '{store_name}'")

def get_product_lines(session, store_name: str, pos_url):
    """Return a list of product lines for the selected store, excluding unwanted lines, only from panel_lineas div."""
    response = select_store(session, store_name, pos_url)
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

def get_article_panel(session, relative_href: str, pos_url):
    """Generic function to extract <a> tags from <div class=panel_articulos> for any given page."""
    url = full_url(pos_url, relative_href)
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

def get_dataframe(session, store_name: str, pos_url, max_threads: int = 28):
    print(f"[SCRAPER] Triggered for store: {store_name}")
    all_products = []
    product_lines = get_product_lines(session, store_name, pos_url)
    # Use 1 thread per line to preserve order
    num_threads = min(len(product_lines), max_threads)
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        article_futures = [
            executor.submit(get_article_panel, session, line['href'], pos_url)
            for line in product_lines
        ]
        for idx, future in enumerate(article_futures):
            line_name = product_lines[idx]['name']
            try:
                articles = future.result()
            except Exception:
                continue
            # Thread pool for presentations per article
            with ThreadPoolExecutor(max_workers=1) as pres_executor:
                pres_futures = [
                    pres_executor.submit(get_article_panel, session, article['href'], pos_url)
                    for article in articles
                ]
                for jdx, pres_future in enumerate(pres_futures):
                    article_name = articles[jdx]['name']
                    try:
                        presentations = pres_future.result()
                    except Exception:
                        continue
                    # Thread pool for stock per presentation
                    with ThreadPoolExecutor(max_workers=1) as stock_executor:
                        stock_futures = [
                            stock_executor.submit(get_article_panel, session, presentation['href'], pos_url)
                            for presentation in presentations
                        ]
                        for kdx, stock_future in enumerate(stock_futures):
                            presentation_name = presentations[kdx]['name']
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
    print(f"[SCRAPER] Done for store: {store_name}, products scraped: {len(df)}")
    return df

def save_dataframe_to_csv(df, store_name, filename=None):
    """Save the DataFrame to a CSV file with the format inv_{store_name}_{date}_{time}.csv using America/Mexico_City timezone."""
    tz = pytz.timezone("America/Mexico_City")
    now = datetime.now(tz)
    date_str = now.strftime('%Y%m%d')
    time_str = now.strftime('%H%M%S')
    safe_store = store_name.replace(' ', '_').replace('/', '_')
    if filename is None:
        filename = f"inv_{safe_store}_{date_str}_{time_str}.csv"
    df.to_csv(filename, index=False)
    print(f"DataFrame saved to {filename}")
    return filename

def get_wholesale_dataframe(df):
    """
    Process the DataFrame to create a wholesale DataFrame with columns:
    line, name, presentation, # of boxes
    For each presentation, keep only one row. Calculate # of boxes from the stock column:
    - Use CAJ if present, else PAQ
    - stock format: TYPE (# OF PZ PER TYPE)PRICE [# OF PZ IN EXISTANCE]
    - # of boxes = # OF PZ IN EXISTANCE / # OF PZ PER TYPE
    The output preserves the order of the first occurrence of each (line, name, presentation) in the original DataFrame.
    """
    import re
    result_rows = []
    seen = set()
    for idx, row in df.iterrows():
        key = (row["line"], row["name"], row["presentation"])
        if key in seen:
            continue
        # Find CAJ or PAQ row for this group
        group = df[(df["line"] == row["line"]) & (df["name"] == row["name"]) & (df["presentation"] == row["presentation"])]
        caj_row = group[group["stock"].str.startswith("CAJ")]
        paq_row = group[group["stock"].str.startswith("PAQ")]
        use_row = None
        if not caj_row.empty:
            use_row = caj_row.iloc[0]
        elif not paq_row.empty:
            use_row = paq_row.iloc[0]
        else:
            continue
        stock_str = use_row["stock"]
        m = re.match(r"(CAJ|PAQ) \((\d+)\)[^\[]*\[(\d+(?:\.\d+)?)\]", stock_str)
        if m:
            n_per_type = float(m.group(2))
            n_exist = float(m.group(3))
            n_boxes = round(n_exist / n_per_type, 2) if n_per_type else 0
        else:
            n_boxes = 0
        result_rows.append({
            "line": row["line"],
            "name": row["name"],
            "presentation": row["presentation"],
            "# of boxes": n_boxes
        })
        seen.add(key)
    return pd.DataFrame(result_rows, columns=["line", "name", "presentation", "# of boxes"])

def get_retail_dataframe(df):
    """
    Process the DataFrame to create a retail DataFrame with columns:
    line, name, presentation, # of pz
    For each presentation, keep only one row if it contains type PZA in the stock column and its value is not 0.
    The output preserves the order of the first occurrence of each (line, name, presentation) in the original DataFrame.
    """
    import re
    result_rows = []
    seen = set()
    for idx, row in df.iterrows():
        key = (row["line"], row["name"], row["presentation"])
        if key in seen:
            continue
        # Find PZA row for this group
        group = df[(df["line"] == row["line"]) & (df["name"] == row["name"]) & (df["presentation"] == row["presentation"])]
        pza_row = group[group["stock"].str.startswith("PZA")]
        if not pza_row.empty:
            use_row = pza_row.iloc[0]
            stock_str = use_row["stock"]
            m = re.match(r"PZA \(\d+\)[^\[]*\[(\d+)\]", stock_str)
            n_pz = int(m.group(1)) if m else 0
            if n_pz != 0:
                result_rows.append({
                    "line": row["line"],
                    "name": row["name"],
                    "presentation": row["presentation"],
                    "# of pz": n_pz
                })
        seen.add(key)
    return pd.DataFrame(result_rows, columns=["line", "name", "presentation", "# of pz"])
