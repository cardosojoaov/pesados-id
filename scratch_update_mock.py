import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("SUPABASE_DB_URL")

try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute("UPDATE transacao_pncp SET municipio = '[REAL DB] ' || municipio WHERE url_origem = 'https://pncp.gov.br/mock';")
    print("Updated mock municipalities to show [REAL DB]")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
