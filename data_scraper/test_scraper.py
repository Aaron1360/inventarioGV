import os
from dotenv import load_dotenv
from scraper_tools import authenticated_session, get_available_stores, select_store, get_product_lines, get_article_panel, get_dataframe, save_dataframe_to_csv, get_wholesale_dataframe, get_retail_dataframe

# Load environment variables from .env if present
load_dotenv()

LOGIN_URL = os.environ.get("LOGIN_URL") 
POS_URL = os.environ.get("POS_URL") 
USERNAME = os.environ.get("APP_USERNAME")
PASSWORD = os.environ.get("APP_PASSWORD")

def test_authenticated_session():
    print("Running test_authenticated_session...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            resp = session.get(POS_URL)
            assert resp.ok, "Session not authenticated or POS page not reachable"
        print("test_authenticated_session: PASSED")
    except Exception as e:
        print(f"test_authenticated_session: FAILED ({e})")

def test_get_available_stores():
    print("Running test_get_available_stores...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert isinstance(stores, list), "Stores result is not a list"
            assert len(stores) > 0, "No stores found"
            for store in stores:
                assert "name" in store and "href" in store, "Store dict missing keys"
        print("test_get_available_stores: PASSED")
    except Exception as e:
        print(f"test_get_available_stores: FAILED ({e})")

def test_select_store():
    print("Running test_select_store...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert stores, "No stores available to select"
            first_store = stores[0]["name"]
            response = select_store(session, first_store, POS_URL)
            assert response.ok, f"Failed to select store: {first_store}"
        print("test_select_store: PASSED")
    except Exception as e:
        print(f"test_select_store: FAILED ({e})")

def test_get_product_lines():
    print("Running test_get_product_lines...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert stores, "No stores available to select"
            first_store = stores[0]["name"]
            product_lines = get_product_lines(session, first_store, POS_URL)
            assert isinstance(product_lines, list), "Product lines result is not a list"
            assert len(product_lines) > 0, "No product lines found"
            for line in product_lines:
                assert "name" in line and "href" in line, "Product line dict missing keys"
        print("test_get_product_lines: PASSED")
    except Exception as e:
        print(f"test_get_product_lines: FAILED ({e})")

def test_get_article_panel():
    print("Running test_get_article_panel...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert stores, "No stores available to select"
            first_store = stores[0]["name"]
            product_lines = get_product_lines(session, first_store, POS_URL)
            assert product_lines, "No product lines found"
            first_line_href = product_lines[0]["href"]
            articles = get_article_panel(session, first_line_href, POS_URL)
            assert isinstance(articles, list), "Articles result is not a list"
            assert len(articles) > 0, "No articles found"
            for article in articles:
                assert "name" in article and "href" in article, "Article dict missing keys"
        print("test_get_article_panel: PASSED")
    except Exception as e:
        print(f"test_get_article_panel: FAILED ({e})")

def test_get_dataframe():
    print("Running test_get_dataframe...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert stores, "No stores available to select"
            first_store = stores[0]["name"]
            df = get_dataframe(session, first_store, POS_URL, max_threads=4)  # Use a low thread count for test stability
            assert df is not None, "DataFrame is None"
            assert not df.empty, "DataFrame is empty"
            required_columns = {"line", "name", "presentation", "stock"}
            assert required_columns.issubset(df.columns), f"Missing columns in DataFrame: {required_columns - set(df.columns)}"
        print("test_get_dataframe: PASSED")
    except Exception as e:
        print(f"test_get_dataframe: FAILED ({e})")

def test_save_dataframe_to_csv():
    print("Running test_save_dataframe_to_csv...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert stores, "No stores available to select"
            first_store = stores[0]["name"]
            df = get_dataframe(session, first_store, POS_URL, max_threads=4)
            assert not df.empty, "DataFrame is empty, cannot test CSV export"
            filename = save_dataframe_to_csv(df, first_store)
            assert os.path.exists(filename), f"CSV file was not created: {filename}"
            # Optionally, check file is not empty
            assert os.path.getsize(filename) > 0, "CSV file is empty"
            # Clean up
            # os.remove(filename)
        print("test_save_dataframe_to_csv: PASSED")
    except Exception as e:
        print(f"test_save_dataframe_to_csv: FAILED ({e})")

def test_get_wholesale_dataframe():
    print("Running test_get_wholesale_dataframe...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert stores, "No stores available to select"
            first_store = stores[0]["name"]
            df = get_dataframe(session, first_store, POS_URL, max_threads=4)
            assert not df.empty, "DataFrame is empty, cannot test wholesale processing"
            wholesale_df = get_wholesale_dataframe(df)
            assert not wholesale_df.empty, "Wholesale DataFrame is empty"
            required_columns = {"line", "name", "presentation", "# of boxes"}
            assert required_columns.issubset(wholesale_df.columns), f"Missing columns in wholesale DataFrame: {required_columns - set(wholesale_df.columns)}"
            # Check only one row per unique (line, name, presentation)
            assert wholesale_df.duplicated(subset=["line", "name", "presentation"]).sum() == 0, "Duplicate rows found in wholesale DataFrame"
            # Check # of boxes is a number (float or int)
            assert wholesale_df["# of boxes"].apply(lambda x: isinstance(x, (int, float))).all(), "# of boxes column contains non-numeric values"
            # Save to CSV
            filename = f"wholesale_{first_store.replace(' ', '_')}.csv"
            wholesale_df.to_csv(filename, index=False)
            print(f"Wholesale DataFrame saved to {filename}")
        print("test_get_wholesale_dataframe: PASSED")
    except Exception as e:
        print(f"test_get_wholesale_dataframe: FAILED ({e})")

def test_get_retail_dataframe():
    print("Running test_get_retail_dataframe...")
    try:
        with authenticated_session(LOGIN_URL, USERNAME, PASSWORD) as session:
            stores = get_available_stores(session, POS_URL)
            assert stores, "No stores available to select"
            first_store = stores[0]["name"]
            df = get_dataframe(session, first_store, POS_URL, max_threads=4)
            assert not df.empty, "DataFrame is empty, cannot test retail processing"
            retail_df = get_retail_dataframe(df)
            assert not retail_df.empty, "Retail DataFrame is empty"
            required_columns = {"line", "name", "presentation", "# of pz"}
            assert required_columns.issubset(retail_df.columns), f"Missing columns in retail DataFrame: {required_columns - set(retail_df.columns)}"
            # Check only one row per unique (line, name, presentation)
            assert retail_df.duplicated(subset=["line", "name", "presentation"]).sum() == 0, "Duplicate rows found in retail DataFrame"
            # Check # of pz is an integer
            assert retail_df["# of pz"].apply(lambda x: isinstance(x, int)).all(), "# of pz column contains non-integer values"
            # Save to CSV
            filename = f"retail_{first_store.replace(' ', '_')}.csv"
            retail_df.to_csv(filename, index=False)
            print(f"Retail DataFrame saved to {filename}")
        print("test_get_retail_dataframe: PASSED")
    except Exception as e:
        print(f"test_get_retail_dataframe: FAILED ({e})")

if __name__ == "__main__":
    # test_authenticated_session()
    # test_get_available_stores()
    # test_select_store()
    # test_get_product_lines()
    # test_get_article_panel()
    # test_get_dataframe()
    # test_save_dataframe_to_csv()
    # test_get_wholesale_dataframe()
    test_get_retail_dataframe()
