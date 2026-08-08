import psycopg2
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
conn = psycopg2.connect(os.getenv("SUPABASE_DB_URL"))

query = """
SELECT 
    municipio,
    fornecedor_normalizado,
    quantidade,
    valor_unitario,
    (quantidade * valor_unitario) as valor_total
FROM view_vendas_maquinas_reais 
WHERE 
    uf = 'MG' 
    AND categoria_sigla = 'BHL'
"""

import warnings
warnings.filterwarnings('ignore')

df = pd.read_sql(query, conn)

print(f"--- RESULTADOS ATUAIS (VIEW) ---")
unidades = df['quantidade'].sum()
print(f"Unidades (Total): {unidades}")

valor_total = (df['quantidade'] * df['valor_unitario']).sum()
print(f"Valor Total (R$): {valor_total:,.2f}")

municipios = df['municipio'].nunique()
print(f"Municípios únicos: {municipios}")

ticket_medio = valor_total / unidades if unidades > 0 else 0
print(f"Ticket Médio: R$ {ticket_medio:,.2f}")

# Share
df_share = df.groupby('fornecedor_normalizado')['quantidade'].sum().reset_index()
df_share['share_percent'] = (df_share['quantidade'] / unidades) * 100

print(f"\\n--- MARKET SHARE (UNIDADES) ---")
for f in ['BAMAQ', 'BRASIF', 'VALENCE']:
    s = df_share[df_share['fornecedor_normalizado'] == f]['share_percent'].sum() if f in df_share['fornecedor_normalizado'].values else 0
    print(f"{f}: {s:.1f}%")

conn.close()
