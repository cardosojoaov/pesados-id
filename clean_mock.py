import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('SUPABASE_DB_URL')
if db_url:
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("DELETE FROM transacao WHERE municipio LIKE 'Munic%Piloto%';")
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        print(f'Sucesso! {deleted} registros do piloto foram apagados do banco.')
    except Exception as e:
        print('Erro ao deletar:', e)
else:
    print('DB URL não encontrada.')
