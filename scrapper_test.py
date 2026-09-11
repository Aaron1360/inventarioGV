import os

from dotenv import load_dotenv
import pandas as pd

from data_scraper.scraper_tools import (
    TARGET_STORES,
    authenticated_session,
    build_store_report,
    fetch_all_product_details,
    fetch_all_products,
)

load_dotenv()

LOGIN_URL = os.getenv("LOGIN_URL")
PRODUCTS_URL = os.getenv("PRODUCTS_URL")
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")

# Number of concurrent detail-page requests; raise carefully to avoid overloading the target site.
MAX_WORKERS = 16

MENU = """
Select a stage to test:
  1) Product list (id, nombre, url)
  2) Product list + detail data (raw columns)
  3) Store report (NOMBRE, SUBLINEA, TIENDA, ALMACEN, CANTIDAD UNITARIA, PRESENTACION, CANT, IMPORTE)
  0) Exit
"""

def choose_store():
    for i, store in enumerate(TARGET_STORES, start=1):
        print(f"  {i}) {store}")
    choice = input("Select a store: ").strip()
    try:
        return TARGET_STORES[int(choice) - 1]
    except (ValueError, IndexError):
        print(f"Invalid choice, defaulting to {TARGET_STORES[0]}.")
        return TARGET_STORES[0]

def main():
    products = None
    details_fetched = False

    with authenticated_session(LOGIN_URL, APP_USERNAME, APP_PASSWORD) as session:
        while True:
            print(MENU)
            choice = input("Option: ").strip()

            if choice == "0":
                break

            if choice not in ("1", "2", "3"):
                print("Invalid option.")
                continue

            if products is None:
                products, page_count = fetch_all_products(session, PRODUCTS_URL)
                print(f"Pages scraped: {page_count}")

            if choice == "1":
                df = pd.DataFrame(products)[["id", "nombre", "url"]]
                out_path = "output_products.csv"
                df.to_csv(out_path, index=False, encoding="utf-8-sig")
                print(f"Total products: {len(df)}")
                print(f"Saved to {out_path}")
                continue

            if not details_fetched:
                fetch_all_product_details(session, products, max_workers=MAX_WORKERS)
                details_fetched = True

            df = pd.DataFrame(products)

            if choice == "2":
                out_path = "output_details.csv"
                df.to_csv(out_path, index=False, encoding="utf-8-sig")
                print(f"Total products: {len(df)}")
                print(f"Saved to {out_path}")
                continue

            store = choose_store()
            report = build_store_report(df, store)
            out_path = f"output_report_{store}.csv"
            report.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"Saved to {out_path}")

if __name__ == "__main__":
    main()
