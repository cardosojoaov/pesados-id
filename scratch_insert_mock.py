import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("SUPABASE_DB_URL")

# Fake pilot data
txs = [
    {"municipio": f"Município Piloto {i:03d}", "orgao": f"Prefeitura Municipal de Teste {i:03d}", "fornecedor": "XCMG BRASIL", "marca": "NÃO IDENTIFICADA", "qtd": 1, "val": 424000.0, "data": "2025-10-15"} for i in range(104)
] + [
    {"municipio": f"Município Bamaq {i:03d}", "orgao": f"Prefeitura Bamaq Teste {i:03d}", "fornecedor": "BAMAQ", "marca": "NEW HOLLAND", "qtd": 1, "val": 424000.0, "data": "2025-11-20"} for i in range(40)
] + [
    {"municipio": f"Município Extra {i:03d}", "orgao": f"Prefeitura Extra {i:03d}", "fornecedor": "BAMAQ", "marca": "NEW HOLLAND", "qtd": 1, "val": 424000.0, "data": "2025-12-10"} for i in range(24)
]

try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    
    for i, t in enumerate(txs):
        cur.execute("""
            INSERT INTO transacao_pncp (
                cnpj_orgao, ano_compra, sequencial_compra, numero_item,
                municipio, uf, orgao, fornecedor_original, fornecedor_normalizado, marca_deduzida, quantidade,
                valor_unitario, data_homologacao, url_origem,
                categoria_sigla, situacao, tipo_registro
            ) VALUES (
                %s, %s, %s, %s,
                %s, 'MG', %s, %s, %s, %s, %s,
                %s, %s, %s,
                'retroescavadeira', 'Homologado', 'COMPRA_NOVA'
            ) ON CONFLICT DO NOTHING;
        """, (
            f"00000000000{i:03d}", 2025, i, 1,
            t["municipio"], t["orgao"], t["fornecedor"], t["fornecedor"], t["marca"], t["qtd"],
            t["val"], t["data"], "https://pncp.gov.br/mock"
        ))
    
    print(f"Inserted {len(txs)} pilot transactions into transacao_pncp.")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
