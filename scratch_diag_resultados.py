import os, psycopg2
from dotenv import load_dotenv
import requests

load_dotenv()
DB_URL = os.environ.get("SUPABASE_DB_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer":    "https://pncp.gov.br/app/editais",
    "Accept":     "application/json, text/plain, */*",
}

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Verifica distribuição de numero_item nos COMPRA_NOVA+HOMOLOGADO
print("=== DISTRIBUICAO numero_item (COMPRA_NOVA+HOMOLOGADO) ===")
cur.execute("""
    SELECT numero_item, COUNT(*) FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
    GROUP BY numero_item ORDER BY 2 DESC LIMIT 10
""")
for r in cur.fetchall(): print(f"  numero_item={r[0]}: {r[1]} registros")

# Pega os 10 primeiros COMPRA_NOVA+HOMOLOGADO com fornecedor vazio
print("\n=== PRIMEIROS 10 COMPRA_NOVA+HOMOLOGADO SEM FORNECEDOR ===")
cur.execute("""
    SELECT id, cnpj_orgao, ano_compra, sequencial_compra, numero_item, categoria_sigla, uf, valor_unitario
    FROM transacao
    WHERE (fornecedor_original IS NULL OR fornecedor_original = '')
      AND tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fonte_id='PNCP'
    ORDER BY id
    LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    print(f"  id={r[0]} cnpj={r[1]} ano={r[2]} seq={r[3]} item={r[4]} cat={r[5]} uf={r[6]} val={r[7]}")

# Testa a URL do /resultados para o primeiro registro
if rows:
    rec = rows[0]
    rec_id, cnpj, ano, seq, num_item, cat, uf, val = rec
    url_resultados = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{num_item}/resultados"
    url_itens      = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
    print(f"\n=== TESTE DIRETO NA API (id={rec_id}) ===")
    print(f"  URL itens:     {url_itens}")
    print(f"  URL resultados: {url_resultados}")

    r_itens = requests.get(url_itens, headers=HEADERS, timeout=15)
    print(f"  /itens status: {r_itens.status_code}")
    if r_itens.status_code == 200:
        itens = r_itens.json()
        print(f"  /itens count: {len(itens) if isinstance(itens, list) else 'not list'}")
        if isinstance(itens, list):
            for it in itens[:3]:
                print(f"    item numeroItem={it.get('numeroItem')} desc={str(it.get('descricao',''))[:60]}")

    r_res = requests.get(url_resultados, headers=HEADERS, timeout=15)
    print(f"  /resultados status: {r_res.status_code}")
    if r_res.status_code == 200:
        res = r_res.json()
        print(f"  /resultados response: {str(res)[:200]}")

    # Testa também com numero_item=1 caso esteja 0
    if num_item == 0:
        url2 = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens/1/resultados"
        r2 = requests.get(url2, headers=HEADERS, timeout=15)
        print(f"  /resultados (item=1) status: {r2.status_code}")
        if r2.status_code == 200:
            print(f"  response: {str(r2.json())[:200]}")

cur.close()
conn.close()
