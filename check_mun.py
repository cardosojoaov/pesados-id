import psycopg2
import os

try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(DISTINCT municipio) FROM view_vendas_maquinas_reais WHERE uf='MG' AND categoria_sigla='BHL';")
    print(f"Distinct in VIEW: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(DISTINCT municipio_nome) FROM transacao WHERE uf='MG' AND categoria_sigla='BHL' AND situacao_compra='Homologado';")
    print(f"Distinct in RAW: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM view_vendas_maquinas_reais WHERE uf='MG' AND categoria_sigla='BHL';")
    print(f"Total Rows in VIEW: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM transacao WHERE uf='MG' AND categoria_sigla='BHL' AND situacao_compra='Homologado';")
    print(f"Total Rows in RAW: {cur.fetchone()[0]}")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
