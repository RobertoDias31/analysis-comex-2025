import pandas as pd
import sqlalchemy
import json

engine = sqlalchemy.create_engine("sqlite:///../data/database.db")

with open("dados_das_tabelas.json", "r") as open_file:
    leitura_dados = json.load(open_file)

for i in leitura_dados:
    path = i['path']
    df = pd.read_csv(i["path"], sep=";", encoding="latin-1")
    df.to_sql(i["table"], engine, if_exists="replace", index=False)
