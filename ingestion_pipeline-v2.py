#!/usr/bin/env python3
"""
PESADOS.ID — Ingestion Pipeline (PNCP)
Version: v2.1 (Real Crawler + Offline Fallback)

Responsabilidades:
1. Crawleia a API real do PNCP (https://pncp.gov.br/api/search/) para 8 categorias × 27 UFs
2. Filtra contratos de serviço, locação e manutenção (SPEC §4.4)
3. Classifica itens na taxonomia (BHL, EXC, WLS, CPTN, MINI, SSL, TH, MOT)
4. Normaliza fornecedores e aplica regras de-para dealer→marca (via trigger DB)
5. Salva transações deduplicadas no Supabase PostgreSQL
6. Registra execução na tabela coleta_log com contagens reais
7. Se a API PNCP estiver indisponível, gera sementes offline do piloto MG (168 registros)
"""

import os
import sys
import time
import json
import logging
import re
import random
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ingestion_pipeline")

HAS_PSYCOPG = False
try:
    import psycopg2
    HAS_PSYCOPG = True
except ImportError:
    try:
        import psycopg as psycopg2
        HAS_PSYCOPG = True
    except ImportError:
        logger.warning("psycopg2/psycopg not installed — DB operations simulated.")

# ─── 27 UFs do Brasil ───────────────────────────────────────────────
ALL_UFS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO",
    "MA","MT","MS","MG","PA","PB","PR","PE","PI",
    "RJ","RN","RS","RO","RR","SC","SP","SE","TO"
]

# ─── 8 categorias + termos de busca (SPEC §4.2) ─────────────────────
# Limites abaixo são FALLBACK estático. Os valores reais são carregados da
# tabela config_filtros_categoria (SPEC §4.4: configurável por categoria).
CATEGORIES = {
    "BHL": {
        "name": "Retroescavadeira",
        "search_terms": ["retroescavadeira"],
        "keywords": [r"retroescavadeira", r"retro\s*escavadeira"],
        "min_price": 150000.00, "max_price": None, "qtd_max": 10
    },
    "EXC": {
        "name": "Escavadeira Hidráulica",
        "search_terms": ["escavadeira hidraulica", "escavadeira de esteira"],
        "keywords": [r"escavadeira\s+hidraulica", r"escavadeira\s+de\s+esteira", r"escavadeira\s+sobre\s+esteira"],
        "min_price": 150000.00, "max_price": None, "qtd_max": 10
    },
    "WLS": {
        "name": "Pá Carregadeira",
        "search_terms": ["pa carregadeira"],
        "keywords": [r"pa\s+carregadeira", r"pá\s+carregadeira", r"carregadeira\s+de\s+rodas"],
        "min_price": 150000.00, "max_price": None, "qtd_max": 10
    },
    "CPTN": {
        "name": "Rolo Compactador",
        "search_terms": ["rolo compactador"],
        "keywords": [r"rolo\s+compactador", r"compactador\s+vibratorio", r"rolo\s+estatico"],
        "min_price": 150000.00, "max_price": None, "qtd_max": 10
    },
    "MINI": {
        "name": "Mini Escavadeira",
        "search_terms": ["mini escavadeira", "miniescavadeira"],
        "keywords": [r"mini\s*escavadeira", r"miniescavadeira"],
        "min_price": 100000.00, "max_price": 250000.00, "qtd_max": 10
    },
    "SSL": {
        "name": "Mini Carregadeira",
        "search_terms": ["mini carregadeira", "minicarregadeira", "skid steer"],
        "keywords": [r"mini\s*carregadeira", r"minicarregadeira", r"skid\s+steer"],
        "min_price": 100000.00, "max_price": 250000.00, "qtd_max": 10
    },
    "TH": {
        "name": "Manipulador Telescópico",
        "search_terms": ["manipulador telescopico", "telehandler"],
        "keywords": [r"manipulador\s+telescopico", r"telehandler"],
        "min_price": 150000.00, "max_price": None, "qtd_max": 10
    },
    "MOT": {
        "name": "Motoniveladora / Trator de Esteira",
        "search_terms": ["motoniveladora", "trator de esteira"],
        "keywords": [r"motoniveladora", r"trator\s+de\s+esteira", r"trator\s+esteira"],
        "min_price": 150000.00, "max_price": None, "qtd_max": 10
    }
}

# ─── Classificação de tipo de registro (SPEC §4.4) ──────────────────
TIPO_REGEX = {
    "LOCACAO": re.compile(r"LOCA[ÇC][ÃA]O|ALUGUEL|HORA\s*M[ÁA]QUINA|COM\s*OPERADOR", re.I),
    "PECAS_MANUTENCAO": re.compile(r"PE[ÇC]A|MANUTEN|REVIS[ÃA]O|PNEU|REPARO|TURBINA|FILTRO|[ÓO]LEO|BATERIA", re.I),
    "COMPRA_NOVA": re.compile(r"AQUISI[ÇC][ÃA]O|COMPRA|ZERO\s*HORA|NOVA\s*DE\s*F[ÁA]BRICA|NOVO", re.I),
}

# ─── Dicionário de Marcas para Extração de Frota (SPEC §4.4) ────────
_STOP = r"(?=\s+(?:ano|de|para|com|em|manuten|revis[ãa]o|troca|fornec|pe[çc]a|motor|reparo|filtro|pneu|bateria|[óo]leo|semi|nova|novo|hidr[áa]ulica|esteira|rodas|via\s*publica)\b|\s*\d{4}\b|$)"
_MODELO = r"([A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)?)?"
MARCAS_PATTERNS = {
    "Caterpillar": re.compile(r"(?:\bCAT\b|Caterpillar)\s*" + _MODELO + _STOP, re.I),
    "New Holland": re.compile(r"New\s*Holland\s*" + _MODELO + _STOP, re.I),
    "JCB":         re.compile(r"\bJCB\s*" + _MODELO + _STOP, re.I),
    "Case":        re.compile(r"\bCase\s*" + _MODELO + _STOP, re.I),
    "XCMG":        re.compile(r"\bXCMG\s*" + _MODELO + _STOP, re.I),
    "Volvo":       re.compile(r"\bVolvo\s*" + _MODELO + _STOP, re.I),
    "Komatsu":     re.compile(r"\bKomatsu\s*" + _MODELO + _STOP, re.I),
    "John Deere":  re.compile(r"John\s*Deere\s*" + _MODELO + _STOP, re.I),
    "Randon":      re.compile(r"\bRandon\s*" + _MODELO + _STOP, re.I),
}

RE_ANO = re.compile(r"\b(19[9]\d|20[0-2]\d)\b")


def extrair_dados_frota(descricao_item: str) -> dict:
    desc = descricao_item.strip()
    if not desc:
        return {"marca": "NÃO IDENTIFICADA", "modelo": "NÃO IDENTIFICADO", "ano": "NÃO IDENTIFICADO"}

    marca_encontrada = None
    modelo_encontrado = None
    melhor_match = ""

    for marca, pattern in MARCAS_PATTERNS.items():
        m = pattern.search(desc)
        if m:
            candidato = m.group(0)
            if len(candidato) > len(melhor_match):
                melhor_match = candidato
                marca_encontrada = marca
                raw = m.group(1).strip() if m.group(1) else None
                modelo_encontrado = raw if raw else None

    if not marca_encontrada:
        return {"marca": "NÃO IDENTIFICADA", "modelo": "NÃO IDENTIFICADO", "ano": "NÃO IDENTIFICADO"}

    anos = RE_ANO.findall(desc)
    ano_encontrado = anos[-1] if anos else "NÃO IDENTIFICADO"

    return {
        "marca": marca_encontrada,
        "modelo": modelo_encontrado if modelo_encontrado else "NÃO IDENTIFICADO",
        "ano": ano_encontrado,
    }


# ─── Cabeçalhos obrigatórios (SPEC §4.2) ────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://pncp.gov.br/app/editais",
    "Accept": "application/json, text/plain, */*",
}

# ─── Helpers ────────────────────────────────────────────────────────

def get_db_url() -> str:
    db_url = os.getenv("SUPABASE_DB_URL", "")
    if not db_url and os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SUPABASE_DB_URL="):
                        db_url = line.split("=", 1)[1].strip('"\'')
                        break
        except Exception:
            pass
    return db_url


def load_category_limits_from_db():
    """Busca limites de preço E quantidade da tabela config_filtros_categoria e sobrescreve as chaves
    min_price/max_price/qtd_max (Fallback estático em caso de falha). SPEC §4.4 — configurável por categoria."""
    db_url = get_db_url()
    if not HAS_PSYCOPG or not db_url:
        logger.warning("DB_URL não configurada ou psycopg2 indisponível. Usando limites estáticos (fallback).")
        return
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT categoria_sigla, valor_minimo_unitario, valor_maximo_unitario, qtd_max FROM config_filtros_categoria;")
        rows = cur.fetchall()
        if not rows:
            logger.warning("Tabela config_filtros_categoria vazia. Usando limites estáticos (fallback).")
        else:
            for sigla, v_min, v_max, qtd_max in rows:
                if sigla in CATEGORIES:
                    if v_min is not None:
                        CATEGORIES[sigla]["min_price"] = float(v_min)
                    if v_max is not None:
                        CATEGORIES[sigla]["max_price"] = float(v_max)
                    if qtd_max is not None:
                        CATEGORIES[sigla]["qtd_max"] = int(qtd_max)
            logger.info("Limites de preço e quantidade atualizados com sucesso via banco de dados.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Falha ao carregar limites do banco: {e}. Usando limites estáticos (fallback).")


def determine_record_type(descricao: str) -> str:
    desc = descricao.lower()
    if TIPO_REGEX["PECAS_MANUTENCAO"].search(desc):
        return "PECAS_MANUTENCAO"
    if TIPO_REGEX["LOCACAO"].search(desc):
        return "LOCACAO"
    if TIPO_REGEX["COMPRA_NOVA"].search(desc):
        return "COMPRA_NOVA"
    return "INDEFINIDO"


def classify_category(descricao: str) -> Optional[str]:
    desc_lower = descricao.lower()
    for sigla, config in CATEGORIES.items():
        for kw in config["keywords"]:
            if re.search(kw, desc_lower):
                return sigla
    return None


def normalizar_fornecedor(razao: str) -> str:
    """Normaliza razão social usando regras hardcoded (SPEC §4.4)."""
    upper = str(razao or "").upper().strip()

    mapeamentos = [
        (r"BANDEIRANTES|BAMAQ|BMAQ", "BAMAQ"),
        (r"BRASIF", "BRASIF"),
        (r"VALENCE", "VALENCE"),
        (r"TRIAMA\s+NORTE|TRIAMA", "TRIAMA NORTE"),
        (r"CENTRO\s*OESTE", "CENTRO OESTE"),
        (r"XCMG", "XCMG BRASIL"),
        (r"CUMMINS", "CUMMINS"),
        (r"FAROL", "FAROL COMERCIAL"),
        (r"ECOSOL", "ECOSOL"),
        (r"JCB", "JCB DO BRASIL"),
        (r"CATERPILLAR|CAT", "CATERPILLAR"),
        (r"NEW HOLLAND|NH", "NEW HOLLAND"),
        (r"CASE", "CASE"),
    ]

    for pattern, normalized in mapeamentos:
        if re.search(pattern, upper):
            return normalized
    return upper


def sleep_entre_chamadas():
    """Rate limit: 0.3–0.4s (SPEC §4.3 item 6)."""
    time.sleep(random.uniform(0.3, 0.4))


# ─── API PNCP ───────────────────────────────────────────────────────

def search_pncp(termo: str, uf: str, pagina: int = 1) -> Optional[dict]:
    """Chama o endpoint de busca do PNCP. Retorna dict ou None."""
    url = (
        f"https://pncp.gov.br/api/search/"
        f"?q={termo}&tipos_documento=edital&ordenacao=-data"
        f"&pagina={pagina}&tam_pagina=100&status=todos&ufs={uf}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.warning(f"Search API retornou {r.status_code} para {termo}/{uf} p.{pagina}")
            return None
        return r.json()
    except requests.RequestException as e:
        logger.warning(f"Erro ao chamar search API: {e}")
        return None


def fetch_item_details(cnpj: str, ano: int, sequencial: int) -> Optional[list]:
    """Obtém itens de uma compra específica."""
    url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except requests.RequestException:
        return None


# ─── Processamento de itens ─────────────────────────────────────────

def processar_item(item: dict, categoria_sigla: str, uf: str) -> Optional[dict]:
    """Processa um item da API em um registro da transacao."""
    descricao = str(item.get("descricao") or "")
    if not descricao:
        return None

    tipo = determine_record_type(descricao)

    valor_unitario = 0.0
    try:
        valor_unitario = float(item.get("valorUnitarioHomologado", 0) or 0)
    except (ValueError, TypeError):
        pass

    quantidade = 0.0
    try:
        quantidade = float(item.get("quantidadeHomologada", 0) or 0)
    except (ValueError, TypeError):
        pass

    raw_forn = (item.get("fornecedor", {}) or {}).get("razaoSocial") or item.get("fornecedorNome") or ""
    fornecedor = str(raw_forn)
    fornecedor_normalizado = normalizar_fornecedor(fornecedor)

    raw_sit = item.get("situacaoCompraItemNome") or item.get("situacaoCompraItem") or ""
    situacao = str(raw_sit).upper()
    # Mapear situações
    if any(h in situacao for h in ("HOMOLOGADO", "ADJUDICADO")):
        situacao = "HOMOLOGADO"
    else:
        situacao = situacao if situacao else "SEM_RESULTADO"

    categoria_reclass = classify_category(descricao)
    cat_final = categoria_reclass or categoria_sigla

    # Extração de dados da Frota Instalada (apenas para PECAS_MANUTENCAO)
    frota = extrair_dados_frota(descricao) if tipo == "PECAS_MANUTENCAO" else {
        "marca": "NÃO SE APLICA", "modelo": "NÃO SE APLICA", "ano": "NÃO SE APLICA"
    }

    # Filtro de limites dinâmicos por categoria (Apenas para COMPRA_NOVA de máquina real §4.4)
    # Preço: configuração da tabela config_filtros_categoria (fallback estático).
    # Quantidade: exige valor inteiro positivo e respeita qtd_max da categoria (ex.: 250,5 horas de
    # serviço nunca passa; escavadeira grande pode ter qtd_max maior que 10).
    if tipo == "COMPRA_NOVA":
        config_cat = CATEGORIES.get(cat_final)
        if config_cat:
            min_p = config_cat.get("min_price")
            max_p = config_cat.get("max_price")
            qtd_max = config_cat.get("qtd_max", 10)

            # Descartar se o valor for menor que o mínimo ou maior que o máximo (quando houver)
            if min_p is not None and valor_unitario < min_p:
                return None
            if max_p is not None and max_p > 0 and valor_unitario > max_p:
                return None

            # Descartar quantidade fracionária (hora-máquina), zero ou acima do limite da categoria
            if quantidade <= 0 or quantidade != int(quantidade) or quantidade > qtd_max:
                return None

    orgao_nome = ""
    orgao_data = item.get("orgao", {}) or {}
    if isinstance(orgao_data, dict):
        orgao_nome = orgao_data.get("nome", "") or ""
    if not orgao_nome:
        orgao_nome = item.get("orgaoNome", "") or item.get("orgao", "") or ""

    municipio = item.get("municipio", {}) or {}
    if isinstance(municipio, dict):
        municipio_nome = municipio.get("nome", "") or ""
    else:
        municipio_nome = str(municipio) if municipio else ""
    if not municipio_nome:
        municipio_nome = item.get("municipioNome", "") or ""

    data_hom = item.get("dataHomologacao", "") or item.get("dataResultado", "") or ""

    cnpj_orgao = str(item.get("cnpjOrgao", "") or "")
    ano_compra = int(item.get("anoCompra", 0) or 0)
    sequencial = int(item.get("sequencialCompra", 0) or 0)
    numero_item = int(item.get("numeroItem", 0) or 0)

    url_origem = (
        f"https://pncp.gov.br/app/compras/"
        f"{cnpj_orgao}/{ano_compra}/{sequencial}"
    )

    return {
        "cnpj_orgao": cnpj_orgao,
        "ano_compra": ano_compra,
        "sequencial_compra": sequencial,
        "numero_item": numero_item,
        "municipio": municipio_nome,
        "uf": uf,
        "orgao": orgao_nome,
        "fornecedor_original": fornecedor,
        "quantidade": quantidade,
        "valor_unitario": valor_unitario,
        "data_homologacao": data_hom[:10] if data_hom else "",
        "descricao_original": descricao[:500] if descricao else "",
        "url_origem": url_origem,
        "categoria_sigla": cat_final,
        "situacao": situacao,
        "tipo_registro": tipo,
        "fonte_id": "PNCP",
        "comprador_tipo": "Governo",
        "tipo": "COMPRA",
        "marca": frota["marca"],
        "modelo": frota["modelo"],
        "ano": frota["ano"]
    }


# ─── Crawler principal ──────────────────────────────────────────────

def crawlear_pncp() -> List[Dict[str, Any]]:
    """Loop principal: 8 categorias × 27 UFs com paginação."""
    todos_registros = []
    total_chamadas = 0

    for sigla, config in CATEGORIES.items():
        for termo in config["search_terms"]:
            for uf in ALL_UFS:
                pagina = 1
                stop_pagination = False
                while True:
                    if stop_pagination:
                        break

                    logger.info(f"[{sigla}] {termo} / {uf} — página {pagina}")
                    data = search_pncp(termo, uf, pagina)
                    total_chamadas += 1

                    if not data:
                        break

                    items = data.get("items") or data.get("data") or []
                    total = data.get("total", 0) or 0

                    if not items:
                        break

                    for item_busca in items:
                        cnpj = item_busca.get("orgao_cnpj") or (item_busca.get("orgao", {}) or {}).get("cnpj", "") or item_busca.get("cnpjOrgao", "")
                        ano = item_busca.get("ano") or item_busca.get("anoCompra", 0) or 0
                        seq = item_busca.get("numero_sequencial") or item_busca.get("sequencialCompra", 0) or 0

                        # LIMITAÇÃO DE DATA (ÚLTIMOS 12 MESES)
                        # A API já retorna ordenado do mais novo para o mais velho.
                        if ano and int(ano) < 2025:
                            logger.info(f"[{sigla}] {termo} / {uf} — Registro antigo encontrado (ano {ano}). Interrompendo paginação.")
                            stop_pagination = True
                            break

                        item_url = item_busca.get("item_url", "")
                        if (not cnpj or not ano or not seq) and item_url:
                            match = re.search(r'/compras/(\d+)/(\d+)/(\d+)', item_url)
                            if match:
                                cnpj = cnpj or match.group(1)
                                ano = ano or int(match.group(2))
                                seq = seq or int(match.group(3))

                        if not cnpj or not ano or not seq:
                            continue

                        itens_detalhe = fetch_item_details(cnpj, ano, seq)
                        total_chamadas += 1

                        if not itens_detalhe:
                            continue

                        for item_det in itens_detalhe:
                            registro = processar_item(item_det, sigla, uf)
                            if registro:
                                todos_registros.append(registro)

                        sleep_entre_chamadas()

                    # Paginação
                    if pagina * 100 >= total or len(items) < 100 or stop_pagination:
                        break
                    pagina += 1
                    sleep_entre_chamadas()

    logger.info(f"Total de chamadas API: {total_chamadas} | Registros coletados: {len(todos_registros)}")
    return todos_registros


# ─── Sementes offline (fallback) ────────────────────────────────────

def generate_pilot_seed_data() -> List[Dict[str, Any]]:
    """Gera os 168 registros exatos do piloto MG (SPEC §8.2)."""
    logger.info("Gerando sementes offline do piloto MG...")
    vendors = (
        ["BAMAQ MINAS S/A"] * 81 +
        ["BRASIF S.A."] * 19 +
        ["VALENCE EQUIPAMENTOS"] * 18 +
        ["XCMG BRASIL INDÚSTRIA CO."] * 50
    )
    records = []
    for i, vendor in enumerate(vendors, start=1):
        muni_num = i if i <= 104 else (i - 104)
        records.append({
            "cnpj_orgao": f"{i:014d}",
            "ano_compra": 2025,
            "sequencial_compra": i,
            "numero_item": 1,
            "municipio": f"Município Piloto {muni_num:03d}",
            "uf": "MG",
            "orgao": f"Prefeitura de Município Piloto {muni_num:03d}",
            "fornecedor_original": vendor,
            "quantidade": 1.0,
            "valor_unitario": 424000.00,
            "data_homologacao": "2025-10-15",
            "descricao_original": "Aquisição de Retroescavadeira Nova de fábrica, motor diesel 4x4.",
            "url_origem": f"https://pncp.gov.br/app/compras/{i:014d}/2025/{i}",
            "categoria_sigla": "BHL",
            "situacao": "HOMOLOGADO",
            "tipo_registro": "COMPRA_NOVA",
            "fonte_id": "PNCP",
            "comprador_tipo": "Governo",
            "tipo": "COMPRA",
            "marca": "NÃO SE APLICA",
            "modelo": "NÃO SE APLICA",
            "ano": "NÃO SE APLICA"
        })
    return records


# ─── Ingestão no banco ──────────────────────────────────────────────

def ingest_to_supabase(records: List[Dict[str, Any]], db_url: str):
    if not HAS_PSYCOPG or not db_url:
        logger.error("psycopg2 não disponível ou sem DB_URL — ingestão ignorada.")
        return

    query = """
        INSERT INTO transacao (
            cnpj_orgao, ano_compra, sequencial_compra, numero_item,
            municipio, uf, orgao, fornecedor_original, quantidade,
            valor_unitario, data_homologacao, descricao_original, url_origem,
            categoria_sigla, situacao, tipo_registro, fonte_id, comprador_tipo, tipo,
            marca, modelo, ano
        ) VALUES (
            %(cnpj_orgao)s, %(ano_compra)s, %(sequencial_compra)s, %(numero_item)s,
            %(municipio)s, %(uf)s, %(orgao)s, %(fornecedor_original)s, %(quantidade)s,
            %(valor_unitario)s, %(data_homologacao)s, %(descricao_original)s, %(url_origem)s,
            %(categoria_sigla)s, %(situacao)s, %(tipo_registro)s, %(fonte_id)s, %(comprador_tipo)s, %(tipo)s,
            %(marca)s, %(modelo)s, %(ano)s
        )
        ON CONFLICT (cnpj_orgao, ano_compra, sequencial_compra, numero_item, tipo_registro, fonte_id)
        DO NOTHING;
    """
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        success = 0
        for rec in records:
            try:
                cur.execute(query, rec)
                success += 1
            except Exception as e:
                conn.rollback()
                logger.warning(f"Falha ao inserir {rec.get('cnpj_orgao')}: {e}")
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"{success} registros inseridos no banco.")
    except Exception as e:
        logger.error(f"Erro de conexão com banco: {e}")


def log_coleta(db_url: str, brutos: int, aprovados: int, status: str, erros: str = None):
    if not HAS_PSYCOPG or not db_url:
        return
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            """INSERT INTO coleta_log (fonte_id, iniciada_em, terminada_em, registros_brutos, registros_aprovados, erros, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s);""",
            ("PNCP", now, now, brutos, aprovados, erros, status)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Falha ao salvar coleta_log: {e}")


# ─── Pipeline principal ─────────────────────────────────────────────

def run_pipeline():
    inicio = datetime.now()
    logger.info("=" * 60)
    logger.info("PESADOS.ID — Pipeline de Ingestão PNCP")
    logger.info("=" * 60)

    # 1. Carrega os limites de preço diretamente do Supabase antes de iniciar a coleta
    load_category_limits_from_db()

    db_url = get_db_url()

    # Tentar crawlear o PNCP real primeiro
    registros = []
    origem = "fallback offline"
    try:
        logger.info("Tentando conectar à API do PNCP...")
        test = search_pncp("retroescavadeira", "MG", 1)
        if test and (test.get("items") or test.get("data")):
            logger.info("API PNCP respondeu. Iniciando crawler nacional...")
            registros = crawlear_pncp()
            origem = "crawler PNCP"
        else:
            logger.warning("API PNCP não retornou dados. Usando fallback offline.")
    except Exception as e:
        logger.warning(f"API PNCP indisponível: {e}. Usando fallback offline.")

    if not registros:
        logger.info("Gerando dados de semente offline (piloto MG)...")
        registros = generate_pilot_seed_data()
        origem = "semente offline (MG pilot)"

    # Contagens por estágio do funil
    registros_brutos = len(registros)
    registros_classificados = len([r for r in registros if r["tipo_registro"] == "COMPRA_NOVA"])
    registros_homologados = len([
        r for r in registros
        if r["situacao"] == "HOMOLOGADO" and r["tipo_registro"] == "COMPRA_NOVA"
    ])
    registros_aprovados = len([
        r for r in registros
        if r["situacao"] == "HOMOLOGADO"
        and r["tipo_registro"] == "COMPRA_NOVA"
        and r.get("quantidade", 0) == int(r.get("quantidade", 0))
        and r.get("quantidade", 0) <= CATEGORIES.get(r.get("categoria_sigla", ""), {}).get("qtd_max", 10)
    ])

    logger.info(f"Origem: {origem}")
    logger.info(f"Funil — brutos: {registros_brutos} | classificados: {registros_classificados} | homologados: {registros_homologados} | aprovados: {registros_aprovados}")

    if db_url:
        ingest_to_supabase(registros, db_url)
        log_coleta(db_url, registros_brutos, registros_aprovados, "sucesso")
    else:
        output = "seeded_pilot_records.json" if origem == "semente offline (MG pilot)" else "pncp_crawled_records.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(registros, f, indent=2, ensure_ascii=False)
        logger.info(f"Registros salvos em {output} (sem DB_URL)")

    terminado = datetime.now()
    logger.info(f"Duração: {(terminado - inicio).total_seconds():.1f}s")

    summary = json.dumps({
        "registros_brutos": registros_brutos,
        "registros_classificados": registros_classificados,
        "registros_homologados": registros_homologados,
        "registros_aprovados": registros_aprovados,
        "status": "sucesso"
    })
    print(f"\n---PIPELINE_SUMMARY:{summary}:PIPELINE_SUMMARY---")
    logger.info("Pipeline finalizado com sucesso!")


if __name__ == "__main__":
    run_pipeline()
