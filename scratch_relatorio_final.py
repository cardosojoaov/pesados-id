import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ.get("SUPABASE_DB_URL"))
cur = conn.cursor()

print("=" * 60)
print("DIAGNOSTICO FINAL - ESTADO DOS DADOS REAIS")
print("=" * 60)

cur.execute("SELECT COUNT(*) FROM transacao")
total = cur.fetchone()[0]
print(f"\nTotal registros: {total}")

print("\n--- COMPRA_NOVA + HOMOLOGADO (maquinas reais) ---")
cur.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN fornecedor_original != '' AND fornecedor_original IS NOT NULL THEN 1 END) as com_forn,
        COUNT(CASE WHEN marca_deduzida IS NOT NULL AND marca_deduzida NOT LIKE '%IDENTIFICADA%' THEN 1 END) as com_marca,
        COUNT(CASE WHEN data_homologacao IS NOT NULL THEN 1 END) as com_data
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
""")
r = cur.fetchone()
print(f"  Total:          {r[0]}")
print(f"  Com fornecedor: {r[1]} ({100*r[1]//r[0] if r[0] else 0}%)")
print(f"  Com marca:      {r[2]} ({100*r[2]//r[0] if r[0] else 0}%)")
print(f"  Com data_hom:   {r[3]} ({100*r[3]//r[0] if r[0] else 0}%)")

print("\n--- SHARE DE MERCADO POR MARCA (151 COMPRA_NOVA+HOMOLOGADO) ---")
cur.execute("""
    SELECT marca_deduzida, COUNT(*) as vendas, 
           ROUND(AVG(valor_unitario)::numeric, 0) as ticket_medio
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND marca_deduzida IS NOT NULL AND marca_deduzida NOT LIKE '%IDENTIFICADA%'
    GROUP BY marca_deduzida ORDER BY 2 DESC
""")
total_marcas = 0
rows = cur.fetchall()
for r in rows: total_marcas += r[1]
for r in rows:
    pct = 100 * r[1] / total_marcas if total_marcas else 0
    print(f"  {r[0]:<20} | {r[1]:>3} vendas ({pct:.1f}%) | ticket medio R${r[2]:>10,.0f}")

print("\n--- POR CATEGORIA ---")
cur.execute("""
    SELECT categoria_sigla, COUNT(*), ROUND(SUM(valor_unitario*quantidade)::numeric,0) as total_R
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
    GROUP BY categoria_sigla ORDER BY 2 DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} vendas, R${r[2] or 0:,.0f}")

print("\n--- TOP 5 UFs ---")
cur.execute("""
    SELECT uf, COUNT(*) as vendas
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
    GROUP BY uf ORDER BY 2 DESC LIMIT 5
""")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]} vendas")

print("\n--- AMOSTRA DE REGISTROS (3 registros reais) ---")
cur.execute("""
    SELECT id, uf, municipio, marca_deduzida, fornecedor_normalizado, 
           valor_unitario, data_homologacao, categoria_sigla
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND marca_deduzida IS NOT NULL AND marca_deduzida NOT LIKE '%IDENTIFICADA%'
    ORDER BY RANDOM() LIMIT 3
""")
for r in cur.fetchall():
    print(f"  id={r[0]} uf={r[1]} mun={r[2]} marca={r[3]}")
    print(f"    dealer={r[4]} val=R${r[5]:,.0f} data={r[6]} cat={r[7]}")

cur.close()
conn.close()
print("\nDiagnostico concluido.")
