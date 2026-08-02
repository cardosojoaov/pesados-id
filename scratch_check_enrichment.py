import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ.get("SUPABASE_DB_URL"))
cur = conn.cursor()

print("=== ESTADO ATUAL DO RE-ENRIQUECIMENTO ===")
cur.execute("SELECT COUNT(*) FROM transacao WHERE fornecedor_original IS NOT NULL AND fornecedor_original != ''")
com_forn = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM transacao")
total = cur.fetchone()[0]
sem_forn = total - com_forn
print(f"Total: {total}")
print(f"COM fornecedor_original preenchido: {com_forn} ({100*com_forn/total:.1f}%)")
print(f"SEM fornecedor_original:            {sem_forn} ({100*sem_forn/total:.1f}%)")

print("\n=== COMPRA_NOVA + HOMOLOGADO (maquinas reais) ===")
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE fornecedor_original IS NOT NULL AND fornecedor_original != '') AS com_forn,
        COUNT(*) AS total
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
""")
r = cur.fetchone()
print(f"  Com fornecedor: {r[0]} de {r[1]}")

print("\n=== FORNECEDOR_NORMALIZADO E MARCA_DEDUZIDA (COMPRA_NOVA+HOMOLOGADO) ===")
cur.execute("""
    SELECT fornecedor_normalizado, marca_deduzida, COUNT(*) 
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
    GROUP BY fornecedor_normalizado, marca_deduzida
    ORDER BY 3 DESC LIMIT 20
""")
print("  normalizado -> marca_deduzida : count")
for r in cur.fetchall(): print(f"  {repr(r[0])} -> {repr(r[1])}: {r[2]}")

print("\n=== BHL + MG (criterio aceite §8.2) ===")
cur.execute("""
    SELECT COUNT(*), SUM(valor_unitario), COUNT(DISTINCT municipio)
    FROM transacao
    WHERE categoria_sigla='BHL' AND uf='MG'
      AND tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
""")
r = cur.fetchone()
print(f"  BHL+MG: count={r[0]}, soma_valor={r[1]}, municipios={r[2]}")

cur.execute("""
    SELECT fornecedor_normalizado, marca_deduzida, COUNT(*) 
    FROM transacao
    WHERE categoria_sigla='BHL' AND uf='MG'
      AND tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
    GROUP BY fornecedor_normalizado, marca_deduzida ORDER BY 3 DESC
""")
print("  Shares BHL+MG:")
for r in cur.fetchall(): print(f"    {repr(r[0])} -> {repr(r[1])}: {r[2]}")

cur.close()
conn.close()
