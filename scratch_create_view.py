import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("SUPABASE_DB_URL")

try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    
    view_sql = """
    CREATE OR REPLACE VIEW view_vendas_maquinas_reais AS
    SELECT 
        id,
        municipio,
        uf,
        orgao,
        fornecedor_original,
        fornecedor_normalizado,
        marca_deduzida,
        quantidade,
        valor_unitario,
        (quantidade * valor_unitario) AS valor_total,
        data_homologacao,
        descricao_original,
        url_origem,
        CASE 
            WHEN categoria_sigla ILIKE 'retroescavadeira%' THEN 'BHL'
            WHEN categoria_sigla ILIKE 'escavadeira%' THEN 'EXC'
            WHEN categoria_sigla ILIKE 'pá carregadeira%' THEN 'WLS'
            WHEN categoria_sigla ILIKE 'rolo compactador%' THEN 'CPTN'
            WHEN categoria_sigla ILIKE 'minicarregadeira%' THEN 'SSL'
            WHEN categoria_sigla ILIKE 'manipulador telescópico%' THEN 'TH'
            ELSE UPPER(categoria_sigla)
        END AS categoria_sigla,
        'Governo' AS comprador_tipo
    FROM transacao_pncp
    WHERE UPPER(situacao) = 'HOMOLOGADO' 
      AND tipo_registro = 'COMPRA_NOVA';
    """
    
    cur.execute(view_sql)
    print("View updated successfully!")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
