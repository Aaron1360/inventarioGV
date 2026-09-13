import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from contextlib import contextmanager
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import unicodedata
import pytz

EXCLUDED_LINES = [
    "IMPORTE",
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
        raise Exception(
            f"Login failed with HTTP {response.status_code} at {response.url}"
        )
    try:
        yield session
    finally:
        session.close()

def full_url(base_url: str, relative_path: str):
    """Generate full URL from base URL and relative path."""
    return urljoin(base_url, relative_path)

def _normalize_label(text: str) -> str:
    """Lowercase and strip accents so label comparisons survive encoding quirks."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip().lower()

def _parse_linked_table(soup: BeautifulSoup, table_class: str | None = None):
    """Parse the first Id/Nombre table whose IDs link to detail pages."""
    tables = soup.find_all("table", class_=table_class) if table_class else soup.find_all("table")
    for table in tables:
        header_row = table.find("tr")
        if header_row is None:
            continue

        header_indexes = {
            _normalize_label(header.get_text(strip=True)): index
            for index, header in enumerate(header_row.find_all("th"))
        }
        id_index = header_indexes.get("id")
        nombre_index = header_indexes.get("nombre")
        if id_index is None or nombre_index is None:
            continue

        records = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if max(id_index, nombre_index) >= len(cells):
                continue

            id_cell = cells[id_index]
            record_id = id_cell.get_text(strip=True)
            id_link = id_cell.find("a")
            if not record_id or id_link is None or not id_link.get("href"):
                continue

            records.append({
                "id": record_id,
                "nombre": cells[nombre_index].get_text(strip=True),
                "url": full_url(BASE_URL, id_link["href"]),
            })
        if records:
            return records
    return []

def _parse_lineas_table(soup: BeautifulSoup):
    """Parse lines, excluding configured names."""
    excluded_names = {_normalize_label(name) for name in EXCLUDED_LINES}
    return [
        record
        for record in _parse_linked_table(soup, table_class="TablaColor")
        if _normalize_label(record["nombre"]) not in excluded_names
    ]

def fetch_lineas_dataframe(session: requests.Session, lineas_url: str):
    """Fetch LINEAS_URL and return the filtered lines dataframe."""
    response = session.get(lineas_url)
    response.raise_for_status()
    lineas = _parse_lineas_table(BeautifulSoup(response.text, "html.parser"))
    if not lineas:
        raise RuntimeError(f"No lineas found at {response.url}")
    return pd.DataFrame(lineas, columns=["id", "nombre", "url"])

def _parse_sublineas_table(soup: BeautifulSoup):
    """Parse the sublineas table from a single linea page."""
    return _parse_linked_table(soup, table_class="TablaColor")

def parse_sublineas_dataframe(html: str):
    """Build a dataframe of sublinea names and their product-page targets."""
    sublineas = _parse_sublineas_table(BeautifulSoup(html, "html.parser"))
    return pd.DataFrame(sublineas, columns=["id", "nombre", "url"])

def fetch_sublineas_dataframe(session: requests.Session, linea_url: str):
    """Fetch one linea page and return its sublineas dataframe."""
    response = session.get(linea_url)
    response.raise_for_status()
    return parse_sublineas_dataframe(response.text)

def _parse_productos_table(soup: BeautifulSoup):
    """Parse the products table from a single sublinea page."""
    return _parse_linked_table(soup)

def fetch_productos_dataframe(session: requests.Session, sublinea_url: str):
    """Fetch one sublinea page and return its products dataframe."""
    response = session.get(sublinea_url)
    response.raise_for_status()
    products = _parse_productos_table(BeautifulSoup(response.text, "html.parser"))
    return pd.DataFrame(products, columns=["id", "nombre", "url"])

def _select_mayoreo_presentacion(product):
    """Pick MAYOREO's presentacion: CAJ if available, otherwise fall back to PAQ.

    Uses pd.notna since missing columns become NaN (not None) once merged into a DataFrame.
    """
    for presentacion in MAYOREO_PRESENTACION_PRIORITY:
        if pd.notna(product.get(f"presentacion_{presentacion}")):
            return presentacion
    return MAYOREO_PRESENTACION_PRIORITY[0]

def _compute_n_cajas(almacen: str, cantidad_unitaria, cant):
    """Compute N° CAJAS for MAYOREO rows with positive stock, else None."""
    if almacen != "MAYOREO":
        return None
    if not pd.notna(cantidad_unitaria) or cantidad_unitaria <= 0:
        return None
    if not pd.notna(cant) or cant == 0:
        return None
    return f"{cantidad_unitaria / cant:.2f}"

def build_store_report(
    lineas_df: pd.DataFrame,
    session: requests.Session,
    max_workers: int = 12,
) -> pd.DataFrame:
    """Build the product hierarchy with bounded concurrent HTTP requests."""
    lineas = lineas_df.to_dict("records")

    def fetch_linea_sublineas(linea):
        sublineas_df = fetch_sublineas_dataframe(session, linea["url"])
        return linea, sublineas_df.to_dict("records")

    sublineas_by_linea = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        sublineas_by_linea.extend(executor.map(fetch_linea_sublineas, lineas))

    sublineas = [
        (linea, sublinea)
        for linea, sublinea_records in sublineas_by_linea
        for sublinea in sublinea_records
    ]
    if not sublineas:
        raise RuntimeError("No sublineas found for the fetched lineas")

    def fetch_sublinea_productos(linea_and_sublinea):
        linea, sublinea = linea_and_sublinea
        productos_df = fetch_productos_dataframe(session, sublinea["url"])
        return linea, sublinea, productos_df.to_dict("records")

    rows = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(fetch_sublinea_productos, sublineas)
        for linea, sublinea, productos in results:
            rows.extend({
                "PRODUCTO": producto["nombre"],
                "LINEA": linea["nombre"],
                "SUBLINEA": sublinea["nombre"],
            } for producto in productos)

    if not rows:
        raise RuntimeError("No productos found for the fetched sublineas")
    return pd.DataFrame(rows, columns=["PRODUCTO", "LINEA", "SUBLINEA"])
