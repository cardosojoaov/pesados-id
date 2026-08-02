"""
Fix definitivo do trigger e reprocessamento de marca_deduzida.

Problemas identificados:
1. Trigger não roda se marca_deduzida já = 'NÃO IDENTIFICADA' (condição IS NULL ou '' ou 'NÃO SE APLICA')
2. Dealer_marca usa match exato, mas fornecedor_normalizado ainda tem nomes longos

Solução:
1. Zera marca_deduzida dos registros sem marca conhecida (para o trigger poder re-processar)
2. Faz UPDATE para re-disparar o trigger com o match correto
"""
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.environ.get("SUPABASE_DB_URL"))
cur = conn.cursor()

print("=== VERIFICANDO FORNECEDORES ATUAIS EM COMPRA_NOVA+HOMOLOGADO ===")
cur.execute("""
    SELECT fornecedor_normalizado, COUNT(*) as n
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
    GROUP BY fornecedor_normalizado ORDER BY 2 DESC LIMIT 20
""")
print("fornecedor_normalizado | count")
for r in cur.fetchall(): print(f"  {repr(r[0])} | {r[1]}")

print("\n=== VERIFICANDO ENTRADAS EM dealer_marca ===")
cur.execute("SELECT fornecedor_normalizado, marca FROM dealer_marca ORDER BY id")
dm = {r[0]: r[1] for r in cur.fetchall()}
print(f"  {len(dm)} entradas: {list(dm.keys())[:10]}")

# Passo 1: Zerar marca_deduzida para poder re-disparar o trigger
print("\nZerando marca_deduzida para forçar re-processamento...")
cur.execute("""
    UPDATE transacao
    SET marca_deduzida = NULL
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
""")
print(f"  {cur.rowcount} registros com marca_deduzida zerados.")
conn.commit()

# Passo 2: Re-disparar o trigger (agora com marcas zeradas, vai processar)
print("\nRe-disparando trigger com mark_deduzida=NULL...")
cur.execute("""
    UPDATE transacao
    SET fornecedor_normalizado = fornecedor_normalizado
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
""")
print(f"  Trigger disparado em {cur.rowcount} registros.")
conn.commit()

print("\n=== RESULTADO FINAL ===")
cur.execute("""
    SELECT marca_deduzida, COUNT(*)
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
    GROUP BY marca_deduzida ORDER BY 2 DESC
""")
total_ok = 0
total_nao = 0
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]}")
    if r[0] and r[0] not in ('NÃO IDENTIFICADA', 'N\xc3O IDENTIFICADA'):
        total_ok += r[1]
    else:
        total_nao += r[1]
print(f"\n  Com marca: {total_ok} | Sem marca: {total_nao}")

# Diagnóstico: fornecedores que não bateram
print("\n=== FORNECEDORES QUE NAO BATERAM NA dealer_marca ===")
cur.execute("""
    SELECT DISTINCT fornecedor_normalizado
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND (marca_deduzida IS NULL OR marca_deduzida LIKE '%IDENTIFICADA%')
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
    ORDER BY 1
""")
nao_bateram = [r[0] for r in cur.fetchall()]
print("  (estes precisam ser adicionados à dealer_marca):")
for n in nao_bateram: print(f"  '{n}'")

cur.close()
conn.close()
