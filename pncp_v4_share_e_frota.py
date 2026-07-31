import psycopg
import time

# String de Conexão obtida na aba Settings > Database do Supabase
DB_URI = "postgresql://postgres:[SENHA]@db.[REF].supabase.co:5432/postgres"

def salvar_transacao_no_supabase(registro):
    query = """
        INSERT INTO transacao (
            cnpj_orgao, ano_compra, sequencial_compra, numero_item,
            municipio, uf, orgao, fornecedor_original, quantidade,
            valor_unitario, data_homologacao, descricao_original, url_origem,
            categoria_sigla, situacao, tipo_registro
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (cnpj_orgao, ano_compra, sequencial_compra, numero_item, tipo_registro, fonte_id)
        DO NOTHING; -- Evita duplicar em re-execuções
    """
    
    with psycopg.connect(DB_URI) as conn:
        with conn.cursor() as cur:
            cur.execute(query, registro)
            conn.commit()

# Respeitar o rate-limit oficial de 0.3s a 0.4s entre requisições da API do PNCP
time.sleep(0.35)