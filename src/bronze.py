import pandas as pd
import requests
from itertools import count

def ingestao_bronze():
    # Buscar dados da API com paginacao
    per_page = 100
    data = []

    for page in count(1):
        params = {"page": page, "per_page": per_page}
        response = requests.get("https://api.openbrewerydb.org/v1/breweries", params=params)
        response.raise_for_status()
        page_data = response.json()

        if not page_data:
            break

        data.extend(page_data)

    # Converter a lista de dados em um DataFrame do Pandas
    df = pd.DataFrame(data)

    # Salvar o DataFrame no formato JSON
    df.to_json("/tmp/breweries.json", orient="records", lines=True)