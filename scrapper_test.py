import os

from dotenv import load_dotenv

from data_scraper.scraper_tools import (
    authenticated_session,
    build_store_report,
    fetch_lineas_dataframe,
)

load_dotenv()

LOGIN_URL = os.getenv("LOGIN_URL")
LINEAS_URL = os.getenv("LINEAS_URL")
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")
MAX_WORKERS = 12

REFERENCE_HTML_URLS = {
    # "products_page.html": "https://grupogranvalle.com/sistema/index.php?modulo=producto&accion=index",
    # "product_CCC0235.html": "https://grupogranvalle.com/sistema/index.php?modulo=producto&accion=show&id=CCC0235",
    # "lineas_page.html": "https://grupogranvalle.com/sistema/index.php?modulo=linea&accion=index",
    "coca_clasica_page.html": "https://grupogranvalle.com/sistema/index.php?modulo=sublinea&accion=show&id=CCLASIC",
}

MENU = """
Select an option:
    1) Download reference HTML files
    2) Build PRODUCTO/LINEA/SUBLINEA dataframe from the website
  0) Exit
"""

def download_reference_html(session):
    for filename, url in REFERENCE_HTML_URLS.items():
        response = session.get(url)
        response.raise_for_status()
        with open(filename, "w", encoding=response.encoding or "utf-8") as html_file:
            html_file.write(response.text)
        print(f"Saved to {filename}")

def main():
    with authenticated_session(LOGIN_URL, APP_USERNAME, APP_PASSWORD) as session:
        while True:
            print(MENU)
            choice = input("Option: ").strip()

            if choice == "0":
                break

            if choice not in ("1", "2"):
                print("Invalid option.")
                continue

            if choice == "1":
                download_reference_html(session)
                continue

            if choice == "2":
                lineas_df = fetch_lineas_dataframe(session, LINEAS_URL)
                df = build_store_report(lineas_df, session, max_workers=MAX_WORKERS)
                df.to_csv("output_dataframe.csv", index=False, encoding="utf-8-sig")
                print(f"Total lines: {len(lineas_df)}")
                print(f"Total product rows: {len(df)}")
                print("Saved to output_dataframe.csv")
                continue

if __name__ == "__main__":
    main()
