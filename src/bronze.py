import pandas as pd
import requests

def ingestao_bronze():
    # Buscar dados da API
    response = requests.get("https://api.openbrewerydb.org/breweries")
    data = response.json()
    print(data)
    # Converter a lista de dados em um DataFrame do Pandas
    df = pd.DataFrame(data)

    # Salvar o DataFrame no formato JSON
    df.to_json("/tmp/breweries.json", orient="records", lines=True)