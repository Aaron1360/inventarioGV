import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from contextlib import contextmanager
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import unicodedata
import pytz

EXCLUDED_LINEA_IDS = [
    "IMPO",
    "FLETE",
    "ADMIN",
]

BASE_URL = "https://grupogranvalle.com/sistema/index.php?"

TARGET_STORES = ["11JULIO", "CEDIS", "CENTRAL"]
TARGET_PRESENTATIONS = ["CAJ", "PAQ", "PZA"]
ALMACEN_NAMES = {
    "001": "MAYOREO",
    "002": "MENUDEO",
}

# MAYOREO uses CAJ when available, falling back to PAQ (e.g. ENCENDEDOR ECO has no CAJ).
MAYOREO_PRESENTACION_PRIORITY = ["CAJ", "PAQ"]
MENUDEO_PRESENTACION = "PZA"

EXISTENCIAS_HEADERS = ("Tienda", "Almacen", "Cantidad Unitaria")
PRESENTACIONES_HEADERS = ("Presentación", "Cant")
PRECIOS_HEADERS = ("Tienda", "Pres", "Importe")
PRODUCT_INFO_HEADERS = ("Producto",)
SUBLINEAS_HEADERS = ("Id", "Nombre", "Est")

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

def _to_number(value: str):
    """Convert a numeric-looking string to float, otherwise return it unchanged."""
    try:
        return float(value.replace(",", ""))
    except (TypeError, ValueError):
        return value

def _normalize_label(text: str) -> str:
    """Lowercase and strip accents so label comparisons survive encoding quirks."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip().lower()

def _parse_products_table(soup: BeautifulSoup):
    """Parse a single products page into a list of {id, nombre} dicts."""
    table = soup.find("table", class_="TablaColor")
    if table is None:
        return []

    products = []
    for row in table.find_all("tr"):
        if row.find("th"):
            continue

        cells = row.find_all("td")
        # Skip section separator rows, e.g. <td colspan="9">Venta</td>
        if len(cells) < 8:
            continue

        nombre = cells[1].get_text(strip=True)

        id_link = cells[0].find("a")
        url = full_url(BASE_URL, id_link["href"]) if id_link and id_link.get("href") else None

        products.append({
            "id": cells[0].get_text(strip=True),
            "nombre": nombre,
            "url": url,
        })
    return products

def _parse_lineas_table(soup: BeautifulSoup):
    """Parse a lineas list page into a list of {id, url} dicts."""
    table = soup.find("table", class_="TablaColor")
    if table is None:
        return []

    lineas = []
    for row in table.find_all("tr"):
        if row.find("th"):
            continue

        cells = row.find_all("td")
        if not cells:
            continue

        id_link = cells[0].find("a")
        if id_link is None or not id_link.get("href"):
            continue

        lineas.append({
            "id": cells[0].get_text(strip=True),
            "url": full_url(BASE_URL, id_link["href"]),
        })
    return lineas

def _find_next_page_url(soup: BeautifulSoup, current_url: str):
    """Return the URL of the next page, or None if there isn't one."""
    for link in soup.find_all("a"):
        if link.get_text(strip=True).lower() == "siguiente" and link.get("href"):
            return full_url(current_url, link["href"])
    return None

def _find_table_by_headers(soup: BeautifulSoup, headers: tuple):
    """Find a table whose header row's non-empty <th> texts exactly match `headers`."""
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if header_row is None:
            continue
        th_texts = tuple(th.get_text(strip=True) for th in header_row.find_all("th") if th.get_text(strip=True))
        if th_texts == headers:
            return table
    return None

def _table_has_data_rows(table) -> bool:
    """Return True if the table has at least one row with <td> cells below its header."""
    if table is None:
        return False
    return any(row.find_all("td") for row in table.find_all("tr")[1:])

def _parse_existencias(table):
    """Extract quantity per (Tienda, Almacen) for the target stores/almacenes."""
    details = {}
    if table is None:
        return details

    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        tienda = cells[0].get_text(strip=True)
        almacen_name = ALMACEN_NAMES.get(cells[1].get_text(strip=True))
        if tienda not in TARGET_STORES or almacen_name is None:
            continue
        details[f"existencia_{tienda}_{almacen_name}"] = _to_number(cells[2].get_text(strip=True))
    return details

def _parse_presentaciones(table):
    """Extract the unit-equivalence quantity for the target presentations."""
    details = {}
    if table is None:
        return details

    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        presentacion = cells[1].get_text(strip=True)
        if presentacion not in TARGET_PRESENTATIONS:
            continue
        details[f"presentacion_{presentacion}"] = _to_number(cells[2].get_text(strip=True))
    return details

def _parse_precios(table):
    """Extract price per (Tienda, Pres) for the target stores/presentations."""
    details = {}
    if table is None:
        return details

    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        tienda = cells[0].get_text(strip=True)
        presentacion = cells[1].get_text(strip=True)
        if tienda not in TARGET_STORES or presentacion not in TARGET_PRESENTATIONS:
            continue
        details[f"precio_{tienda}_{presentacion}"] = _to_number(cells[2].get_text(strip=True))
    return details

def _parse_product_info(table):
    """Extract the Sublínea value from the key/value product info table."""
    details = {}
    if table is None:
        return details

    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        if _normalize_label(cells[0].get_text(strip=True)) == "sublinea":
            details["sublinea"] = cells[1].get_text(strip=True)
    return details

def parse_product_detail(soup: BeautifulSoup):
    """Parse the Producto, Existencias, Presentaciones and Precios sections of a product page.

    Sections missing from the page (empty) simply contribute no keys.
    """
    details = {}
    details.update(_parse_product_info(_find_table_by_headers(soup, PRODUCT_INFO_HEADERS)))

    existencias_table = _find_table_by_headers(soup, EXISTENCIAS_HEADERS)
    details["has_existencias"] = _table_has_data_rows(existencias_table)
    details.update(_parse_existencias(existencias_table))

    details.update(_parse_presentaciones(_find_table_by_headers(soup, PRESENTACIONES_HEADERS)))
    details.update(_parse_precios(_find_table_by_headers(soup, PRECIOS_HEADERS)))
    return details

def fetch_product_details(session: requests.Session, url: str, retries: int = 3):
    """Fetch a single product detail page and parse its sections of interest.

    Concurrent requests over a shared session occasionally come back as an
    incomplete/invalid page (missing even the "Producto" info table); retry
    those instead of treating them as products with no data.
    """
    details = {}
    for _ in range(retries):
        response = session.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        if _find_table_by_headers(soup, PRODUCT_INFO_HEADERS) is not None:
            return parse_product_detail(soup)
        details = parse_product_detail(soup)
    return details

def fetch_all_product_details(session: requests.Session, products: list, max_workers: int = 8):
    """Fetch and merge detail data into each product dict concurrently, in place."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_product = {
            executor.submit(fetch_product_details, session, product["url"]): product
            for product in products if product.get("url")
        }
        for future in as_completed(future_to_product):
            future_to_product[future].update(future.result())
    return products

def fetch_all_products(session: requests.Session, products_url: str):
    """Follow the pager and collect every product row across all pages.

    Returns a tuple of (products, page_count).
    """
    products = []
    visited_urls = set()
    next_url = products_url

    while next_url and next_url not in visited_urls:
        visited_urls.add(next_url)
        response = session.get(next_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        products.extend(_parse_products_table(soup))
        next_url = _find_next_page_url(soup, next_url)

    return products, len(visited_urls)

def fetch_all_lineas(session: requests.Session, lineas_url: str):
    """Follow the pager and collect every linea (id, url) across all pages."""
    lineas = []
    visited_urls = set()
    next_url = lineas_url

    while next_url and next_url not in visited_urls:
        visited_urls.add(next_url)
        response = session.get(next_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        lineas.extend(_parse_lineas_table(soup))
        next_url = _find_next_page_url(soup, next_url)

    return lineas

def fetch_linea_sublineas(session: requests.Session, url: str):
    """Fetch one linea's detail page and return the list of sublinea ids it contains."""
    response = session.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    table = _find_table_by_headers(soup, SUBLINEAS_HEADERS)
    if table is None:
        return []
    return [
        row.find_all("td")[0].get_text(strip=True)
        for row in table.find_all("tr")[1:]
        if row.find_all("td")
    ]

def build_sublinea_to_linea_map(session: requests.Session, lineas_url: str, max_workers: int = 8):
    """Fetch every linea's sublineas and return a {sublinea_id: linea_id} map."""
    lineas = fetch_all_lineas(session, lineas_url)
    mapping = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_linea_id = {
            executor.submit(fetch_linea_sublineas, session, linea["url"]): linea["id"]
            for linea in lineas
        }
        for future in as_completed(future_to_linea_id):
            linea_id = future_to_linea_id[future]
            for sublinea_id in future.result():
                mapping[sublinea_id] = linea_id

    return mapping

def apply_linea_mapping(products: list, sublinea_to_linea: dict):
    """Add a 'linea' key to each product dict based on its sublinea, in place."""
    for product in products:
        product["linea"] = sublinea_to_linea.get(product.get("sublinea"))
    return products

def scrape_products(login_url: str, products_url: str, username: str, password: str):
    """Log in, scrape every products page and their detail data, and return (DataFrame, scraped_at, page_count)."""
    with authenticated_session(login_url, username, password) as session:
        products, page_count = fetch_all_products(session, products_url)
        fetch_all_product_details(session, products)

    scraped_at = datetime.now(pytz.timezone("America/Mexico_City"))
    return pd.DataFrame(products), scraped_at, page_count

def _select_mayoreo_presentacion(product):
    """Pick MAYOREO's presentacion: CAJ if available, otherwise fall back to PAQ.

    Uses pd.notna since missing columns become NaN (not None) once merged into a DataFrame.
    """
    for presentacion in MAYOREO_PRESENTACION_PRIORITY:
        if pd.notna(product.get(f"presentacion_{presentacion}")):
            return presentacion
    return MAYOREO_PRESENTACION_PRIORITY[0]

def build_store_report(df: pd.DataFrame, store: str) -> pd.DataFrame:
    """Build a tidy report for one store: NOMBRE, LINEA, SUBLINEA, TIENDA, ALMACEN, CANTIDAD UNITARIA, PRESENTACION, CANT, IMPORTE.

    Products with no Existencias table at all (no stock data anywhere), or whose
    linea is in EXCLUDED_LINEA_IDS, are excluded. Each remaining product contributes
    exactly 2 rows for the store: MAYOREO paired with CAJ (or PAQ when CAJ isn't
    available), MENUDEO paired with PZA.
    """
    rows = []
    for _, product in df.iterrows():
        if not product.get("has_existencias", False):
            continue
        if product.get("linea") in EXCLUDED_LINEA_IDS:
            continue
        almacen_presentacion = {
            "MAYOREO": _select_mayoreo_presentacion(product),
            "MENUDEO": MENUDEO_PRESENTACION,
        }
        for almacen, presentacion in almacen_presentacion.items():
            rows.append({
                "NOMBRE": product.get("nombre"),
                "LINEA": product.get("linea"),
                "SUBLINEA": product.get("sublinea"),
                "TIENDA": store,
                "ALMACEN": almacen,
                "CANTIDAD UNITARIA": product.get(f"existencia_{store}_{almacen}"),
                "PRESENTACION": presentacion,
                "CANT": product.get(f"presentacion_{presentacion}"),
                "IMPORTE": product.get(f"precio_{store}_{presentacion}"),
            })
    return pd.DataFrame(rows)
