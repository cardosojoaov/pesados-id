import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('SUPABASE_DB_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("DELETE FROM transacao WHERE cnpj_orgao = '';")
print('Apagados registros corrompidos:', cur.rowcount)
conn.commit()
cur.close()
conn.close()
