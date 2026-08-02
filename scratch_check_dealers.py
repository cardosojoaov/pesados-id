import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ.get("SUPABASE_DB_URL"))
cur = conn.cursor()

print("=== TABELA dealer_marca ATUAL ===")
cur.execute("SELECT fornecedor_normalizado, marca, confianca FROM dealer_marca ORDER BY id")
for r in cur.fetchall(): print(f"  {r[0]} -> {r[1]} ({r[2]})")

print("\n=== VERIFICANDO TRIGGER ===")
cur.execute("""
    SELECT trigger_name, event_manipulation, action_timing, action_statement
    FROM information_schema.triggers
    WHERE event_object_table = 'transacao'
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} {r[2]}")

print("\n=== BAMAQ JA EXISTE EM dealer_marca? ===")
cur.execute("SELECT * FROM dealer_marca WHERE fornecedor_normalizado ILIKE '%BAMAQ%'")
rows = cur.fetchall()
print(f"  {len(rows)} linha(s):")
for r in rows: print(f"  {r}")

print("\n=== TOP DEALERS SEM MARCA (candidatos para dealer_marca) ===")
cur.execute("""
    SELECT fornecedor_normalizado, COUNT(*) as vendas, SUM(valor_unitario*quantidade) as total_R
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND (marca_deduzida IS NULL OR marca_deduzida = 'NAO IDENTIFICADA' OR marca_deduzida = 'N\u00c3O IDENTIFICADA')
      AND fornecedor_normalizado IS NOT NULL AND fornecedor_normalizado != ''
    GROUP BY fornecedor_normalizado
    ORDER BY vendas DESC
    LIMIT 20
""")
print("  fornecedor_normalizado | vendas | total_R")
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]} | R${r[2] or 0:,.0f}")

cur.close()
conn.close()
