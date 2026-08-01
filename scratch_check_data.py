import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("SUPABASE_DB_URL")

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    cur.execute("SELECT uf, COUNT(*) FROM transacao_pncp WHERE tipo_registro = 'COMPRA_NOVA' GROUP BY uf;")
    print("UF for COMPRA_NOVA:", cur.fetchall())
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
