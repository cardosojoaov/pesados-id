import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            SUM(quantidade) AS total_unidades,
            SUM(valor_total) AS total_reais,
            COUNT(DISTINCT municipio) AS total_municipios,
            ROUND(SUM(valor_total) / SUM(quantidade), 2) AS ticket_medio
        FROM view_vendas_maquinas_reais
        WHERE uf = 'MG' AND categoria_sigla = 'BHL';
    """)
    row = cur.fetchone()
    
    if row:
        print(f"Unidades: {row[0]}")
        print(f"Reais: {row[1]}")
        print(f"Municipios: {row[2]}")
        print(f"Ticket: {row[3]}")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
