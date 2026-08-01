import psycopg

DB_URI = "postgresql://postgres.srdmtgzbaljikrpavjmk:pesadosid%40%21@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
try:
    conn = psycopg.connect(DB_URI)
    with conn.cursor() as cur:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'dealer_marca';")
        for row in cur.fetchall():
            print(row)
except Exception as e:
    print(e)
