import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("SUPABASE_DB_URL"))
cur = conn.cursor()

cur.execute("""
    SELECT municipio, url_origem, fornecedor_original, fornecedor_normalizado, data_homologacao, situacao, tipo_registro
    FROM transacao 
    WHERE municipio IN ('Nazareno', 'Piedade do Rio Grande') AND categoria_sigla='BHL'
""")

rows = cur.fetchall()
for r in rows:
    print(r)

cur.close()
conn.close()
