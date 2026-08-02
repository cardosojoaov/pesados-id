import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get('SUPABASE_DB_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'normalizacao_fornecedores'
    ORDER BY ordinal_position;
""")
print("normalizacao_fornecedores columns:")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'transacao'
    ORDER BY ordinal_position;
""")
print("\ntransacao columns:")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")

cur.execute("SELECT * FROM normalizacao_fornecedores LIMIT 5;")
print("\nnormalizacao_fornecedores sample:")
for r in cur.fetchall(): print(f"  {r}")

cur.close()
conn.close()
