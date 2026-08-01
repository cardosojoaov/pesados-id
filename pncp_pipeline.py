import os
import time
import re
import requests
import psycopg
from datetime import datetime
from urllib.parse import urlparse

# Carregar variáveis de ambiente (pode usar dotenv na prática, ou ler do os.environ)
from dotenv import load_dotenv
load_dotenv()

DB_URI = os.getenv("SUPABASE_DB_URL")

# Termos de busca da especificação
TERMOS_BUSCA = [
    "retroescavadeira", "escavadeira hidráulica", "pá carregadeira", 
    "motoniveladora", "rolo compactador", "trator de esteira", 
    "minicarregadeira", "manipulador telescópico"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://pncp.gov.br/app/editais",
    "Accept": "application/json"
}

# 4.4 Regras de classificação
REGEX_LOCACAO = re.compile(r"LOCA[ÇC][ÃA]O|ALUGUEL|HORA\s*M[ÁA]QUINA|COM\s*OPERADOR", re.IGNORECASE)
REGEX_PECAS_MANUTENCAO = re.compile(r"PE[ÇC]A|MANUTEN[ÇC][ÃA]O|REVIS[ÃA]O|PNEU|REPARO|TURBINA|FILTRO|[ÓO]LEO|BATERIA", re.IGNORECASE)
REGEX_COMPRA_NOVA = re.compile(r"AQUISI[ÇC][ÃA]O|COMPRA|ZERO\s*HORA|NOVA\s*DE\s*F[ÁA]BRICA|NOVO", re.IGNORECASE)

# 4.6 Frota instalada - Regex básicas (simplificadas, ideal expandir conforme os dados reais)
REGEX_FROTA_MARCA = re.compile(r"(CATERPILLAR|NEW HOLLAND|JCB|CASE|KOMATSU|XCMG|VOLVO|JOHN DEERE|SANY|LIUGONG|HYUNDAI)", re.IGNORECASE)
REGEX_FROTA_ANO = re.compile(r"ANO\s*(20[0-2][0-9])", re.IGNORECASE)
REGEX_FROTA_MODELO = re.compile(r"(?:MODELO|MOD\.)\s*([A-Z0-9\-]+)", re.IGNORECASE)


def db_connect():
    return psycopg.connect(DB_URI)


def get_parametros_categoria(conn):
    """Carrega parâmetros para filtro de COMPRA_NOVA"""
    params = {}
    with conn.cursor() as cur:
        cur.execute("SELECT categoria_sigla, valor_unitario_min, valor_unitario_max, quantidade_max FROM pncp_parametros WHERE ativo = TRUE;")
        for row in cur.fetchall():
            params[row[0].lower()] = {
                "val_min": row[1],
                "val_max": row[2],
                "qtd_max": row[3]
            }
    return params


def get_normalizacoes_fornecedor(conn):
    """Carrega regras de normalização de fornecedores"""
    rules = {}
    with conn.cursor() as cur:
        cur.execute("SELECT palavra_chave, nome_normalizado FROM fornecedor_normalizacao WHERE ativo = TRUE;")
        for row in cur.fetchall():
            rules[row[0].upper()] = row[1].upper()
    return rules


def get_dealer_marca_map(conn):
    """Carrega mapeamento Dealer -> Marca"""
    mapping = {}
    with conn.cursor() as cur:
        # Pega a vigência mais recente para o dealer
        cur.execute("""
            SELECT fornecedor_normalizado, marca 
            FROM dealer_marca 
            WHERE (data_fim_vigencia IS NULL OR data_fim_vigencia >= CURRENT_DATE)
        """)
        for row in cur.fetchall():
            mapping[row[0].upper()] = row[1].upper()
    return mapping


def classificar_descricao(descricao):
    if not descricao:
        return "INDEFINIDO"
    if REGEX_LOCACAO.search(descricao):
        return "LOCACAO"
    if REGEX_PECAS_MANUTENCAO.search(descricao):
        return "PECAS_MANUTENCAO"
    if REGEX_COMPRA_NOVA.search(descricao):
        return "COMPRA_NOVA"
    return "INDEFINIDO"


def extrair_frota(descricao):
    marca = REGEX_FROTA_MARCA.search(descricao)
    ano = REGEX_FROTA_ANO.search(descricao)
    modelo = REGEX_FROTA_MODELO.search(descricao)
    
    return {
        "marca": marca.group(1).upper() if marca else None,
        "ano": int(ano.group(1)) if ano else None,
        "modelo": modelo.group(1).upper() if modelo else None
    }


def normalizar_fornecedor(fornecedor, regras):
    if not fornecedor:
        return None
    fornecedor_upper = fornecedor.upper()
    for chave, normalizado in regras.items():
        if re.search(r'\b' + re.escape(chave) + r'\b', fornecedor_upper):
            return normalizado
    return fornecedor_upper


def extrair_dados_pncp(termo):
    print(f"Coletando para: {termo}", flush=True)
    pagina = 1
    tam_pagina = 100
    base_url = "https://pncp.gov.br/api/search/"
    itens_processados = []

    while True:
        params = {
            "q": termo,
            "tipos_documento": "edital",
            "ordenacao": "-data",
            "pagina": pagina,
            "tam_pagina": tam_pagina,
            "status": "todos"
        }
        
        try:
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Erro ao buscar página {pagina} de {termo}: {e}", flush=True)
            break

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            url_compra = item.get("item_url", "")
            if not url_compra:
                continue

            parts = url_compra.strip("/").split("/")
            if len(parts) >= 4 and parts[0] == "compras":
                cnpj = parts[1]
                ano = parts[2]
                seq = parts[3]

                # Buca itens da compra
                url_itens = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
                try:
                    resp_itens = requests.get(url_itens, headers=HEADERS, timeout=15)
                    time.sleep(0.35) # rate limit
                    if resp_itens.status_code == 200:
                        itens_compra = resp_itens.json()
                        for i_c in itens_compra:
                            numero_item = i_c.get("numeroItem")
                            # Busca resultados (onde está o fornecedor e valor)
                            url_resultados = f"{url_itens}/{numero_item}/resultados"
                            resp_res = requests.get(url_resultados, headers=HEADERS, timeout=15)
                            time.sleep(0.35)
                            
                            fornecedor = None
                            valor_unitario = 0.0
                            quantidade = float(i_c.get("quantidade", 0))
                            situacao = i_c.get("situacaoCompraItemNome")
                            data_homologacao = i_c.get("dataAtualizacao")
                            
                            if resp_res.status_code == 200:
                                res_list = resp_res.json()
                                if res_list and isinstance(res_list, list) and len(res_list) > 0:
                                    res_obj = res_list[0]
                                    fornecedor = res_obj.get("nomeRazaoSocialFornecedor")
                                    valor_unitario = res_obj.get("valorUnitarioHomologado")
                                    if data_homologacao is None:
                                        data_homologacao = res_obj.get("dataAtualizacao")
                            
                            itens_processados.append({
                                "cnpj_orgao": cnpj,
                                "ano_compra": ano,
                                "sequencial_compra": seq,
                                "numero_item": numero_item,
                                "municipio": item.get("municipioNome"),
                                "uf": item.get("ufSigla"),
                                "orgao": item.get("orgaoEntidade", {}).get("razaoSocial"),
                                "fornecedor_original": fornecedor,
                                "quantidade": quantidade,
                                "valor_unitario": valor_unitario,
                                "data_homologacao": data_homologacao.split("T")[0] if data_homologacao else None,
                                "descricao_original": i_c.get("descricao"),
                                "url_origem": f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}",
                                "categoria_sigla": termo,
                                "situacao": situacao
                            })
                except Exception as e:
                    print(f"Erro ao buscar detalhes do item {url_compra}: {e}")

        # Paginação (se tem menos que o max, acabou)
        if len(items) < tam_pagina:
            break
        pagina += 1
        
        # Limite de debug para nao rodar eternamente
        if pagina > 2:
            break

    return itens_processados


def processar_e_salvar(conn, itens_processados, params_filtro, regras_fornecedor, dealer_marca):
    
    query = """
        INSERT INTO transacao (
            cnpj_orgao, ano_compra, sequencial_compra, numero_item,
            municipio, uf, orgao, fornecedor_original, quantidade,
            valor_unitario, data_homologacao, descricao_original, url_origem,
            categoria_sigla, situacao, tipo_registro, 
            fornecedor_normalizado, marca_deduzida, 
            marca, modelo, ano, fonte_id
        ) VALUES (
            %(cnpj_orgao)s, %(ano_compra)s, %(sequencial_compra)s, %(numero_item)s,
            %(municipio)s, %(uf)s, %(orgao)s, %(fornecedor_original)s, %(quantidade)s,
            %(valor_unitario)s, %(data_homologacao)s, %(descricao_original)s, %(url_origem)s,
            %(categoria_sigla)s, %(situacao)s, %(tipo_registro)s,
            %(fornecedor_normalizado)s, %(marca_deduzida)s,
            %(maquina_marca)s, %(maquina_modelo)s, %(maquina_ano)s, 'PNCP'
        )
        ON CONFLICT (cnpj_orgao, ano_compra, sequencial_compra, numero_item, tipo_registro, fonte_id) 
        DO UPDATE SET
            situacao = EXCLUDED.situacao,
            fornecedor_normalizado = EXCLUDED.fornecedor_normalizado,
            marca_deduzida = EXCLUDED.marca_deduzida,
            atualizado_em = CURRENT_TIMESTAMP;
    """
    
    count_salvos = 0
    with conn.cursor() as cur:
        for item in itens_processados:
            desc = item["descricao_original"]
            tipo_reg = classificar_descricao(desc)
            item["tipo_registro"] = tipo_reg
            
            # Filtro de Máquina Real (só para COMPRA_NOVA HOMOLOGADO)
            if tipo_reg == "COMPRA_NOVA" and str(item["situacao"]).upper() == "HOMOLOGADO":
                cat = str(item["categoria_sigla"]).lower()
                limites = params_filtro.get(cat)
                
                # Para cruzar string parcial ex: "escavadeira hidráulica" pega o limitador "escavadeira" se existir
                if not limites:
                    for key_cat, lim in params_filtro.items():
                        if key_cat in cat:
                            limites = lim
                            break

                val_unit = float(item["valor_unitario"] or 0)
                qtd = float(item["quantidade"] or 0)
                
                if limites:
                    if not (float(limites["val_min"]) <= val_unit <= float(limites["val_max"]) and qtd <= int(limites["qtd_max"])):
                        # Não passou no filtro de máquina real, descartar ou reclassificar.
                        # Para este pipeline, vamos reclassificar como INDEFINIDO para manter rastreabilidade
                        item["tipo_registro"] = "INDEFINIDO"
            
            # Normalização e Dedução de Marca
            fornecedor = normalizar_fornecedor(item["fornecedor_original"], regras_fornecedor)
            item["fornecedor_normalizado"] = fornecedor
            
            marca_deduzida = dealer_marca.get(fornecedor, "NÃO IDENTIFICADA") if fornecedor else "NÃO IDENTIFICADA"
            item["marca_deduzida"] = marca_deduzida
            
            # Extração de Frota se for Peça/Manutenção
            frota = {}
            if tipo_reg == "PECAS_MANUTENCAO":
                frota = extrair_frota(desc)
            
            item["maquina_marca"] = frota.get("marca")
            item["maquina_modelo"] = frota.get("modelo")
            item["maquina_ano"] = frota.get("ano")
            
            cur.execute(query, item)
            count_salvos += 1
            
        conn.commit()
    print(f"Salvos/Atualizados {count_salvos} registros.")


def run_pipeline():
    print("Iniciando Pipeline PNCP...")
    
    with db_connect() as conn:
        # 1. Carregar configurações do banco
        params_filtro = get_parametros_categoria(conn)
        regras_fornecedor = get_normalizacoes_fornecedor(conn)
        dealer_marca = get_dealer_marca_map(conn)
        
        # 2. Coletar e processar para cada termo
        for termo in TERMOS_BUSCA:
            itens_processados = extrair_dados_pncp(termo)
            
            # 3. Processar regras (classificacao, normalizacao) e Salvar
            if itens_processados:
                processar_e_salvar(conn, itens_processados, params_filtro, regras_fornecedor, dealer_marca)

    print("Pipeline PNCP finalizado.")

if __name__ == "__main__":
    run_pipeline()
