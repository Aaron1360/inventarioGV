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

# def get_available_stores(session, pos_url):
#     """Return a list of available store names and their links from the store selection page."""
#     store_page_url = full_url(pos_url, '?modulo=pdv&accion=tienda')
#     response = session.get(store_page_url)
#     if not response.ok:
#         raise Exception("Failed to fetch store selection page")
#     soup = BeautifulSoup(response.text, "html.parser")
#     stores = []
#     for a in soup.find_all('a'):
#         store_name = a.text.strip()
#         store_href = a.get('href')
#         if store_name and store_href:
#             stores.append({"name": store_name, "href": store_href})
#     return stores

# def select_store(session, store_name: str, pos_url):
#     """Find the store link for the given store name, and return the response after selecting the store."""
#     store_page_url = full_url(pos_url, '?modulo=pdv&accion=tienda')
#     response = session.get(store_page_url)
#     if not response.ok:
#         raise Exception("Failed to fetch store selection page")
#     soup = BeautifulSoup(response.text, "html.parser")
#     store_link = None
#     for a in soup.find_all('a'):
#         if store_name.lower() in a.text.lower():
#             store_link = a.get('href')
#             break
#     if not store_link:
#         raise Exception(f"Store '{store_name}' not found on the page")
#     select_url = full_url(pos_url, store_link)
#     select_response = session.get(select_url)
#     if select_response.ok:
#         return select_response
#     else:
#         raise Exception(f"Failed to select store '{store_name}'")

# def get_product_lines(session, store_name: str, pos_url):
#     """Return a list of product lines for the selected store, excluding unwanted lines, only from panel_lineas div."""
#     response = select_store(session, store_name, pos_url)
#     soup = BeautifulSoup(response.text, "html.parser")
#     product_lines = []
#     panel_lineas = soup.find('div', class_='panel_lineas')
#     if panel_lineas:
#         for a in panel_lineas.find_all('a'):
#             line_text = a.text.strip().upper()
#             if line_text and line_text not in EXCLUDED_LINES:
#                 product_lines.append({
#                     "name": line_text,
#                     "href": a.get('href')
#                 })
#     return product_lines

# def get_article_panel(session, relative_href: str, pos_url):
#     """Generic function to extract <a> tags from <div class=panel_articulos> for any given page."""
#     url = full_url(pos_url, relative_href)
#     response = session.get(url)
#     if not response.ok:
#         raise Exception(f"Failed to fetch page: {relative_href}")
#     soup = BeautifulSoup(response.text, "html.parser")
#     panel_articulos = soup.find('div', class_='panel_articulos')
#     items = []
#     if panel_articulos:
#         for a in panel_articulos.find_all('a'):
#             text = a.text.strip()
#             href = a.get('href')
#             if text:
#                 items.append({"name": text, "href": href})
#     return items

# def get_dataframe(session, store_name: str, pos_url, max_threads: int = 32):
#     print(f"[SCRAPER] Triggered for store: {store_name}")
#     all_products = []
#     product_lines = get_product_lines(session, store_name, pos_url)
#     # Use a single ThreadPoolExecutor for all network-bound tasks
#     with ThreadPoolExecutor(max_workers=max_threads) as executor:
#         # Fetch articles for each line in parallel, preserving order
#         article_futures = [
#             executor.submit(get_article_panel, session, line['href'], pos_url)
#             for line in product_lines
#         ]
#         articles_by_line = []
#         for idx, future in enumerate(article_futures):
#             try:
#                 articles = future.result()
#             except Exception:
#                 articles = []
#             articles_by_line.append(articles)
#         # For each line, fetch presentations for each article in parallel, preserving order
#         presentations_by_line = []
#         for articles in articles_by_line:
#             pres_futures = [
#                 executor.submit(get_article_panel, session, article['href'], pos_url)
#                 for article in articles
#             ]
#             presentations = []
#             for jdx, pres_future in enumerate(pres_futures):
#                 try:
#                     pres = pres_future.result()
#                 except Exception:
#                     pres = []
#                 presentations.append(pres)
#             presentations_by_line.append(presentations)
#         # For each presentation, fetch stock in parallel, preserving order
#         for line_idx, (line, articles, presentations_list) in enumerate(zip(product_lines, articles_by_line, presentations_by_line)):
#             for art_idx, (article, presentations) in enumerate(zip(articles, presentations_list)):
#                 stock_futures = [
#                     executor.submit(get_article_panel, session, presentation['href'], pos_url)
#                     for presentation in presentations
#                 ]
#                 stocks_by_presentation = []
#                 for kdx, stock_future in enumerate(stock_futures):
#                     try:
#                         stock_list = stock_future.result()
#                     except Exception:
#                         stock_list = []
#                     stocks_by_presentation.append(stock_list)
#                 # Assemble all products, preserving order
#                 for pres_idx, (presentation, stock_list) in enumerate(zip(presentations, stocks_by_presentation)):
#                     for stock in stock_list:
#                         all_products.append({
#                             "line": line["name"],
#                             "name": article["name"],
#                             "presentation": presentation["name"],
#                             "stock": stock["name"]
#                         })
#     # Remove duplicates
#     df = pd.DataFrame(all_products).drop_duplicates()
#     print(f"[SCRAPER] Done for store: {store_name}, products scraped: {len(df)}")
#     return df

# def save_dataframe_to_csv(df, store_name, filename=None):
#     """Save the DataFrame to a CSV file with the format inv_{store_name}_{date}_{time}.csv using America/Mexico_City timezone."""
#     tz = pytz.timezone("America/Mexico_City")
#     now = datetime.now(tz)
#     date_str = now.strftime('%Y%m%d')
#     time_str = now.strftime('%H%M%S')
#     safe_store = store_name.replace(' ', '_').replace('/', '_')
#     if filename is None:
#         filename = f"inv_{safe_store}_{date_str}_{time_str}.csv"
#     df.to_csv(filename, index=False)
#     print(f"DataFrame saved to {filename}")
#     return filename

# def get_wholesale_dataframe(df):
#     """
#     Process the DataFrame to create a wholesale DataFrame with columns:
#     presentacion, cajas
#     For each presentacion, keep only one row. Calculate cajas from the stock column:
#     - Use CAJ if present, else PAQ
#     - stock format: TYPE (# OF PZ PER TYPE)PRICE [# OF PZ IN EXISTANCE]
#     - cajas = # OF PZ IN EXISTANCE / # OF PZ PER TYPE
#     The output preserves the order of the first occurrence of each presentacion in the original DataFrame.
#     """
#     import re
#     result_rows = []
#     seen = set()
#     for idx, row in df.iterrows():
#         key = row["presentation"]
#         if key in seen:
#             continue
#         group = df[df["presentation"] == row["presentation"]]
#         caj_row = group[group["stock"].str.startswith("CAJ")]
#         paq_row = group[group["stock"].str.startswith("PAQ")]
#         use_row = None
#         if not caj_row.empty:
#             use_row = caj_row.iloc[0]
#         elif not paq_row.empty:
#             use_row = paq_row.iloc[0]
#         else:
#             continue
#         stock_str = use_row["stock"]
#         m = re.match(r"(CAJ|PAQ) \((\d+)\)[^\[]*\[(\d+(?:,\d+)*(?:\.\d+)?)\]", stock_str)
#         if m:
#             n_per_type = float(m.group(2))
#             n_exist_str = m.group(3).replace(",", "")
#             n_exist = float(n_exist_str)
#             n_cajas = round(n_exist / n_per_type, 2) if n_per_type else 0
#         else:
#             n_cajas = 0
#         result_rows.append({
#             "presentacion": row["presentation"],
#             "cajas": n_cajas
#         })
#         seen.add(key)
#     return pd.DataFrame(result_rows, columns=["presentacion", "cajas"])


# def get_retail_dataframe(df):
#     """
#     Process the DataFrame to create a retail DataFrame with columns:
#     presentacion, piezas
#     For each presentacion, keep only one row if it contains type PZA in the stock column and its value is not 0.
#     The output preserves the order of the first occurrence of each presentacion in the original DataFrame.
#     """
#     import re
#     result_rows = []
#     seen = set()
#     for idx, row in df.iterrows():
#         key = row["presentation"]
#         if key in seen:
#             continue
#         group = df[df["presentation"] == row["presentation"]]
#         pza_row = group[group["stock"].str.startswith("PZA")]
#         if not pza_row.empty:
#             use_row = pza_row.iloc[0]
#             stock_str = use_row["stock"]
#             m = re.match(r"PZA \(\d+\)[^\[]*\[(\d+(?:,\d+)*(?:\.\d+)?)\]", stock_str)
#             n_piezas = int(m.group(1).replace(",", "")) if m else 0
#             if n_piezas != 0:
#                 result_rows.append({
#                     "presentacion": row["presentation"],
#                     "piezas": n_piezas
#                 })
#         seen.add(key)
#     return pd.DataFrame(result_rows, columns=["presentacion", "piezas"])

# def get_prices_dataframe(df):
#     """
#     Create a prices DataFrame with columns: presentacion, precio
#     The precio is taken from the CAJ type in the stock column, or PAQ if CAJ is missing.
#     The output preserves the order of the first occurrence of each presentacion in the original DataFrame.
#     """
#     import re
#     result_rows = []
#     seen = set()
#     for idx, row in df.iterrows():
#         key = row["presentation"]
#         if key in seen:
#             continue
#         group = df[df["presentation"] == row["presentation"]]
#         caj_row = group[group["stock"].str.startswith("CAJ")]
#         paq_row = group[group["stock"].str.startswith("PAQ")]
#         use_row = None
#         if not caj_row.empty:
#             use_row = caj_row.iloc[0]
#         elif not paq_row.empty:
#             use_row = paq_row.iloc[0]
#         else:
#             continue
#         stock_str = use_row["stock"]
#         m = re.match(r"(CAJ|PAQ) \(\d+\)([\d\.]+)", stock_str)
#         if m:
#             precio = float(m.group(2))
#         else:
#             precio = 0.0
#         result_rows.append({
#             "presentacion": row["presentation"],
#             "precio": f"${precio:.2f}"
#         })
#         seen.add(key)
#     return pd.DataFrame(result_rows, columns=["presentacion", "precio"])

# def export_all_dataframes_to_excel(df, filename):
#     """
#     Export the wholesale, retail, and prices DataFrames to a single Excel file with Spanish sheet names.
#     Sheet names: mayoreo, menudeo, precios
#     Adjusts the first column width to fit content.
#     """
#     wholesale_df = get_wholesale_dataframe(df)
#     retail_df = get_retail_dataframe(df)
#     prices_df = get_prices_dataframe(df)
#     with pd.ExcelWriter(filename, engine="openpyxl") as writer:
#         for sheet_name, dataf in [("mayoreo", wholesale_df), ("menudeo", retail_df), ("precios", prices_df)]:
#             dataf.to_excel(writer, sheet_name=sheet_name, index=False)
#             worksheet = writer.sheets[sheet_name]
#             # Adjust first column width
#             max_len = max([len(str(x)) for x in dataf.iloc[:, 0].astype(str)] + [len(dataf.columns[0])])
#             worksheet.column_dimensions["A"].width = max_len + 2  # Add some padding
#     print(f"All dataframes exported to {filename}")
