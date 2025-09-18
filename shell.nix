{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python3
    python3Packages.pip
    python3Packages.fastapi
    python3Packages.uvicorn
    python3Packages.jinja2
    python3Packages.requests
    python3Packages.beautifulsoup4
    python3Packages.lxml
    python3Packages.pandas
    python3Packages.sqlalchemy
    python3Packages.python-dotenv
    python3Packages.python-multipart
    python3Packages.pytz
  ];

  shellHook = ''
    echo "FastAPI web development environment loaded!"
    echo "Python version: $(python --version)"
    echo "FastAPI version: $(python -c 'import fastapi; print(fastapi.__version__)')"
    echo "Uvicorn version: $(python -c 'import uvicorn; print(uvicorn.__version__)')"
    echo "Jinja2 version: $(python -c 'import jinja2; print(jinja2.__version__)')"
    echo "Requests version: $(python -c 'import requests; print(requests.__version__)')"
    echo "BeautifulSoup4 version: $(python -c 'import bs4; print(bs4.__version__)')"
    echo "lxml version: $(python -c 'import lxml; print(lxml.__version__)')"
    echo "pandas version: $(python -c 'import pandas; print(pandas.__version__)')"
    echo "SQLAlchemy version: $(python -c 'import sqlalchemy; print(sqlalchemy.__version__)')"
    echo ""
    echo "Note: For exact package versions, run 'pip install -r requirements.txt' inside this shell."
    echo "You can now use FastAPI, uvicorn, jinja2, requests, beautifulsoup4, lxml, pandas, SQLAlchemy, and python-dotenv for web development and scraping."
  '';
}
