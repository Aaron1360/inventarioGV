import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from contextlib import contextmanager
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import unicodedata
import pytz
import time

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

def _to_number(value: str):
    """Convert a formatted numeric value to float, preserving non-numeric text."""
    if not isinstance(value, str):
        return value
    normalized = value.strip().replace(" ", "")
    if not normalized:
        return value
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        parts = normalized.split(",")
        normalized = (
            "".join(parts)
            if len(parts[-1]) == 3 and all(part.isdigit() for part in parts)
            else normalized.replace(",", ".")
        )
    try:
        return float(normalized)
    except ValueError:
        return value

def _normalize_label(text: str) -> str:
    """Lowercase and strip accents so label comparisons survive encoding quirks."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip().lower()

def _find_next_page_url(soup: BeautifulSoup, current_url: str):
    """Return the next pagination URL, if the page provides one."""
    for link in soup.find_all("a"):
        if link.get_text(strip=True).lower() == "siguiente" and link.get("href"):
            return full_url(current_url, link["href"])
    return None

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
    lineas = _fetch_paginated_records(session, lineas_url, _parse_lineas_table)
    if not lineas:
        raise RuntimeError(f"No lineas found at {lineas_url}")
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
    sublineas = _fetch_paginated_records(session, linea_url, _parse_sublineas_table)
    return pd.DataFrame(sublineas, columns=["id", "nombre", "url"])

def _parse_productos_table(soup: BeautifulSoup):
    """Parse the products table from a single sublinea page."""
    return _parse_linked_table(soup)

def fetch_productos_dataframe(session: requests.Session, sublinea_url: str):
    """Fetch one sublinea page and return its products dataframe."""
    products = _fetch_paginated_records(session, sublinea_url, _parse_productos_table)
    return pd.DataFrame(products, columns=["id", "nombre", "url"])

def _find_table_by_headers(soup: BeautifulSoup, headers: tuple):
    """Find a table whose non-empty headers match the requested headers."""
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if header_row is None:
            continue
        actual_headers = tuple(
            cell.get_text(strip=True)
            for cell in header_row.find_all("th")
            if cell.get_text(strip=True)
        )
        if actual_headers == headers:
            return table
    return None

def _parse_product_detail(soup: BeautifulSoup):
    """Extract stock, presentations, and prices from a product page."""
    details = {"existencias": {}, "presentaciones": {}, "precios": {}}

    existencias = _find_table_by_headers(soup, EXISTENCIAS_HEADERS)
    if existencias is not None:
        for row in existencias.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            store = cells[0].get_text(strip=True)
            warehouse = ALMACEN_NAMES.get(cells[1].get_text(strip=True))
            if store in TARGET_STORES and warehouse:
                details["existencias"][(store, warehouse)] = _to_number(
                    cells[2].get_text(strip=True)
                )

    presentations = _find_table_by_headers(soup, PRESENTACIONES_HEADERS)
    if presentations is not None:
        for row in presentations.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            presentation = cells[1].get_text(strip=True)
            if presentation in TARGET_PRESENTATIONS:
                details["presentaciones"][presentation] = _to_number(
                    cells[2].get_text(strip=True)
                )

    prices = _find_table_by_headers(soup, PRECIOS_HEADERS)
    if prices is not None:
        for row in prices.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            store = cells[0].get_text(strip=True)
            presentation = cells[1].get_text(strip=True)
            if store in TARGET_STORES and presentation in TARGET_PRESENTATIONS:
                details["precios"][(store, presentation)] = _to_number(
                    cells[2].get_text(strip=True)
                )
    return details

def fetch_product_detail(session: requests.Session, product_url: str):
    """Fetch and parse one product detail page."""
    for attempt in range(3):
        response = session.get(product_url)
        response.raise_for_status()
        details = _parse_product_detail(BeautifulSoup(response.text, "html.parser"))
        if any(details.values()):
            return details
        if attempt < 2:
            time.sleep(0.25 * (attempt + 1))
    return details

def _fetch_paginated_records(session: requests.Session, url: str, parser):
    """Fetch and combine all pages for a linked table."""
    records = []
    visited_urls = set()
    next_url = url
    while next_url and next_url not in visited_urls:
        visited_urls.add(next_url)
        page_records = []
        for attempt in range(3):
            response = session.get(next_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            page_records = parser(soup)
            if page_records or attempt == 2:
                break
            time.sleep(0.25 * (attempt + 1))
        records.extend(page_records)
        next_url = _find_next_page_url(soup, next_url)
    return records

def _copy_authenticated_session(session: requests.Session):
    """Create an independent read session with the authenticated cookies."""
    worker = requests.Session()
    worker.headers.update(session.headers)
    worker.cookies.update(session.cookies.get_dict())
    return worker

def _select_mayoreo_presentacion(presentaciones):
    """Pick CAJ for MAYOREO, falling back to PAQ when CAJ is unavailable."""
    for presentacion in MAYOREO_PRESENTACION_PRIORITY:
        if presentacion in presentaciones and pd.notna(presentaciones[presentacion]):
            return presentacion
    return None

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
    """Build the inventory dataframe with bounded concurrent HTTP requests."""
    lineas = lineas_df.to_dict("records")

    def fetch_linea_sublineas(linea):
        worker = _copy_authenticated_session(session)
        try:
            sublineas_df = fetch_sublineas_dataframe(worker, linea["url"])
            return linea, sublineas_df.to_dict("records")
        finally:
            worker.close()

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
        worker = _copy_authenticated_session(session)
        try:
            productos_df = fetch_productos_dataframe(worker, sublinea["url"])
            return linea, sublinea, productos_df.to_dict("records")
        finally:
            worker.close()

    product_targets = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(fetch_sublinea_productos, sublineas)
        for linea, sublinea, productos in results:
            product_targets.extend(
                (linea, sublinea, producto) for producto in productos
            )

    def fetch_target_detail(target):
        linea, sublinea, producto = target
        worker = _copy_authenticated_session(session)
        try:
            details = fetch_product_detail(worker, producto["url"])
            return linea, sublinea, producto, details
        finally:
            worker.close()

    rows = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(fetch_target_detail, product_targets)
        for linea, sublinea, producto, details in results:
            presentations = details["presentaciones"]
            wholesale_presentation = _select_mayoreo_presentacion(presentations)
            warehouse_presentations = {
                "MAYOREO": wholesale_presentation,
                "MENUDEO": MENUDEO_PRESENTACION,
            }
            for store in TARGET_STORES:
                if not any(
                    (store, warehouse) in details["existencias"]
                    for warehouse in warehouse_presentations
                ):
                    continue
                for warehouse, presentation in warehouse_presentations.items():
                    if presentation is None:
                        continue
                    rows.append({
                        "PRODUCTO": producto["nombre"],
                        "LINEA": linea["nombre"],
                        "SUBLINEA": sublinea["nombre"],
                        "TIENDA": store,
                        "ALMACEN": warehouse,
                        "CANTIDAD UNITARIA": details["existencias"].get(
                            (store, warehouse)
                        ),
                        "PRESENTACION": presentation,
                        "CANT": presentations.get(presentation),
                        "N° CAJAS": _compute_n_cajas(
                            warehouse,
                            details["existencias"].get((store, warehouse)),
                            presentations.get(presentation),
                        ),
                        "IMPORTE": details["precios"].get(
                            (store, presentation)
                        ),
                    })

    if not rows:
        raise RuntimeError("No productos found for the fetched sublineas")
    return pd.DataFrame(rows, columns=[
        "PRODUCTO",
        "LINEA",
        "SUBLINEA",
        "TIENDA",
        "ALMACEN",
        "CANTIDAD UNITARIA",
        "PRESENTACION",
        "CANT",
        "N° CAJAS",
        "IMPORTE",
    ])
