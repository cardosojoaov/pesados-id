import psycopg2
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
conn = psycopg2.connect(os.getenv("SUPABASE_DB_URL"))

query = """
SELECT 
    municipio, url_origem, quantidade, valor_unitario
FROM transacao 
WHERE 
    uf = 'MG' 
    AND categoria_sigla = 'BHL'
    AND fornecedor_normalizado = 'VALENCE'
    AND situacao = 'EM ANDAMENTO'
    AND tipo_registro = 'COMPRA_NOVA'
"""
df = pd.read_sql(query, conn)
print(df)
conn.close()
