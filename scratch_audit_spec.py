import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get('SUPABASE_DB_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

print('=== RESUMO GERAL DA TABELA transacao ===')
cur.execute('SELECT COUNT(*) FROM transacao')
print(f'Total linhas: {cur.fetchone()[0]}')

cur.execute("SELECT tipo_registro, COUNT(*) FROM transacao GROUP BY tipo_registro ORDER BY 2 DESC")
print('Por tipo_registro:')
for r in cur.fetchall(): print(f'  {repr(r[0])}: {r[1]}')

cur.execute("SELECT situacao, COUNT(*) FROM transacao GROUP BY situacao ORDER BY 2 DESC")
print('Por situacao:')
for r in cur.fetchall(): print(f'  {repr(r[0])}: {r[1]}')

cur.execute("SELECT categoria_sigla, COUNT(*) FROM transacao GROUP BY categoria_sigla ORDER BY 2 DESC")
print('Por categoria_sigla:')
for r in cur.fetchall(): print(f'  {repr(r[0])}: {r[1]}')

print()
print('=== NORMALIZACAO ===')
cur.execute("SELECT fornecedor_normalizado, COUNT(*) FROM transacao GROUP BY fornecedor_normalizado ORDER BY 2 DESC LIMIT 20")
print('Top 20 fornecedor_normalizado:')
for r in cur.fetchall(): print(f'  {repr(r[0])}: {r[1]}')

print()
print('=== MARCA DEDUZIDA (COMPRA_NOVA + HOMOLOGADO) ===')
cur.execute("SELECT marca_deduzida, COUNT(*) FROM transacao WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO' GROUP BY marca_deduzida ORDER BY 2 DESC LIMIT 20")
for r in cur.fetchall(): print(f'  {repr(r[0])}: {r[1]}')

print()
print('=== CAMPOS CRITICOS COM PROBLEMA ===')
cur.execute("SELECT COUNT(*) FROM transacao WHERE url_origem IS NULL OR url_origem=''")
print(f'url_origem vazio: {cur.fetchone()[0]}')
cur.execute("SELECT COUNT(*) FROM transacao WHERE fornecedor_original IS NULL OR fornecedor_original=''")
print(f'fornecedor_original vazio: {cur.fetchone()[0]}')
cur.execute("SELECT COUNT(*) FROM transacao WHERE data_homologacao IS NULL")
print(f'data_homologacao NULL: {cur.fetchone()[0]}')
cur.execute("SELECT COUNT(*) FROM transacao WHERE municipio IS NULL OR municipio=''")
print(f'municipio vazio: {cur.fetchone()[0]}')

print()
print('=== AMOSTRAS COMPRA_NOVA + HOMOLOGADO ===')
cur.execute("""
    SELECT fornecedor_original, fornecedor_normalizado, marca_deduzida, categoria_sigla, uf, valor_unitario
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
    LIMIT 10
""")
for r in cur.fetchall():
    print(f'  fornorig={repr(r[0])} norm={repr(r[1])} marca={repr(r[2])} cat={r[3]} uf={r[4]} val={r[5]}')

print()
print('=== RETRO BHL + MG (CRITERIO ACEITE §8.2) ===')
cur.execute("""
    SELECT COUNT(*), SUM(valor_unitario), COUNT(DISTINCT municipio)
    FROM transacao
    WHERE categoria_sigla='BHL' AND uf='MG'
    AND tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
""")
r = cur.fetchone()
print(f'  BHL+MG: count={r[0]}, total={r[1]}, municipios={r[2]}')

cur.execute("""
    SELECT fornecedor_normalizado, marca_deduzida, COUNT(*) 
    FROM transacao
    WHERE categoria_sigla='BHL' AND uf='MG'
    AND tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
    GROUP BY fornecedor_normalizado, marca_deduzida
    ORDER BY 3 DESC
""")
print('  Shares BHL+MG:')
for r in cur.fetchall(): print(f'    {repr(r[0])} -> {repr(r[1])}: {r[2]}')

print()
print('=== FONTE_ID ===')
cur.execute("SELECT fonte_id, COUNT(*) FROM transacao GROUP BY fonte_id ORDER BY 2 DESC")
for r in cur.fetchall(): print(f'  fonte_id={repr(r[0])}: {r[1]}')

print()
print('=== TABELAS AUXILIARES ===')
cur.execute("SELECT COUNT(*) FROM normalizacao_fornecedores")
print(f'normalizacao_fornecedores: {cur.fetchone()[0]} regras')
cur.execute("SELECT COUNT(*) FROM dealer_marca")
print(f'dealer_marca: {cur.fetchone()[0]} registros')
cur.execute("SELECT COUNT(*) FROM config_filtros_categoria")
print(f'config_filtros_categoria: {cur.fetchone()[0]} categorias')

cur.close()
conn.close()
