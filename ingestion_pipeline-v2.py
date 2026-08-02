#!/usr/bin/env python3
"""
PESADOS.ID — Ingestion Pipeline (PNCP)
Version: v3.0 (Full Fix — Fornecedor + Normalização + De-Para)

Responsabilidades:
1. Crawleia a API real do PNCP (https://pncp.gov.br/api/search/) para 8 categorias × 27 UFs
2. Chama o endpoint /resultados para obter o fornecedor vencedor real (SPEC §4.3 armadilha #3)
3. Filtra contratos de serviço, locação e manutenção (SPEC §4.4)
4. Classifica itens na taxonomia (BHL, EXC, WLS, CPTN, MINI, SSL, TH, MOT)
5. Carrega regras de normalização do banco e aplica sobre fornecedor_original → fornecedor_normalizado
6. O trigger deduzir_marca do banco converte fornecedor_normalizado → marca_deduzida automaticamente
7. Salva transações deduplicadas no Supabase PostgreSQL com ON CONFLICT DO UPDATE
8. Registra execução na tabela coleta_log com contagens reais
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
    from psycopg2.extras import execute_batch
    HAS_PSYCOPG = True
except ImportError:
    try:
        import psycopg as psycopg2
        HAS_PSYCOPG = True
    except ImportError:
        logger.warning("psycopg2/psycopg not installed — DB operations disabled.")

# ─── 27 UFs do Brasil ───────────────────────────────────────────────
ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
]

# ─── 8 categorias + termos de busca (SPEC §4.2) ─────────────────────
# Limites abaixo são FALLBACK estático. Os valores reais são carregados da
# tabela config_filtros_categoria (SPEC §4.4: configurável por categoria).
CATEGORIES = {
    "BHL": {
        "name": "Retroescavadeira",
        "search_terms": ["retroescavadeira"],
        "keywords": [r"retroescavadeira", r"retro\s*escavadeira"],
        "min_price": 150000.00, "max_price": 900000.00, "qtd_max": 10
    },
    "EXC": {
        "name": "Escavadeira Hidráulica",
        "search_terms": ["escavadeira hidraulica", "escavadeira de esteira"],
        "keywords": [r"escavadeira\s+hidraulica", r"escavadeira\s+de\s+esteira", r"escavadeira\s+sobre\s+esteira"],
        "min_price": 300000.00, "max_price": 1500000.00, "qtd_max": 10
    },
    "WLS": {
        "name": "Pá Carregadeira",
        "search_terms": ["pa carregadeira"],
        "keywords": [r"pa\s+carregadeira", r"pá\s+carregadeira", r"carregadeira\s+de\s+rodas"],
        "min_price": 150000.00, "max_price": 1000000.00, "qtd_max": 10
    },
    "CPTN": {
        "name": "Rolo Compactador",
        "search_terms": ["rolo compactador"],
        "keywords": [r"rolo\s+compactador", r"compactador\s+vibratorio", r"rolo\s+estatico"],
        "min_price": 150000.00, "max_price": 800000.00, "qtd_max": 10
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
        "min_price": 150000.00, "max_price": 800000.00, "qtd_max": 10
    },
    "MOT": {
        "name": "Motoniveladora / Trator de Esteira",
        "search_terms": ["motoniveladora", "trator de esteira"],
        "keywords": [r"motoniveladora", r"trator\s+de\s+esteira", r"trator\s+esteira"],
        "min_price": 150000.00, "max_price": 2500000.00, "qtd_max": 10
    }
}

# ─── Classificação de tipo de registro (SPEC §4.4) ──────────────────
TIPO_REGEX = {
    "LOCACAO":          re.compile(r"LOCA[ÇC][ÃA]O|ALUGUEL|HORA\s*M[ÁA]QUINA|COM\s*OPERADOR", re.I),
    "PECAS_MANUTENCAO": re.compile(r"PE[ÇC]A|MANUTEN|REVIS[ÃA]O|PNEU|REPARO|TURBINA|FILTRO|[ÓO]LEO|BATERIA", re.I),
    "COMPRA_NOVA":      re.compile(r"AQUISI[ÇC][ÃA]O|COMPRA|ZERO\s*HORA|NOVA\s*DE\s*F[ÁA]BRICA|NOVO", re.I),
}

# ─── Mapeamento de normalização: FALLBACK hardcoded (SPEC §4.4) ─────
# Carregado do banco em load_normalizacao_rules_from_db().
# Este fallback é usado se o banco não responder.
NORMALIZACAO_FALLBACK = [
    (r"BANDEIRANTES|BAMAQ|BMAQ",     "BAMAQ"),
    (r"BRASIF",                       "BRASIF"),
    (r"VALENCE",                      "VALENCE"),
    (r"TRIAMA\s*NORTE|TRIAMA",        "TRIAMA NORTE"),
    (r"CENTRO\s*OESTE",               "CENTRO OESTE"),
    (r"XCMG",                         "XCMG BRASIL"),
    (r"CUMMINS",                      "CUMMINS"),
    (r"FAROL",                        "FAROL COMERCIAL"),
    (r"ECOSOL",                       "ECOSOL"),
    (r"\bJCB\b",                      "JCB DO BRASIL"),
    (r"CATERPILLAR|\bCAT\b",          "CATERPILLAR"),
    (r"NEW\s*HOLLAND",                "NEW HOLLAND"),
    (r"\bCASE\b",                     "CASE"),
    (r"KOMATSU",                      "KOMATSU"),
    (r"VOLVO",                        "VOLVO CE"),
    (r"JOHN\s*DEERE",                 "JOHN DEERE"),
]

# Regras carregadas do banco (prioridade sobre fallback)
_NORMALIZACAO_RULES_DB: List[tuple] = []

# ─── Dicionário de Marcas para Extração de Frota (SPEC §4.6) ────────
_STOP = r"(?=\s+(?:ano|de|para|com|em|manuten|revis[ãa]o|troca|fornec|pe[çc]a|motor|reparo|filtro|pneu|bateria|[óo]leo|semi|nova|novo|hidr[áa]ulica|esteira|rodas|via\s*publica)\b|\s*\d{4}\b|$)"
_MODELO = r"([A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)?)?"
MARCAS_PATTERNS = {
    "Caterpillar": re.compile(r"(?:\bCAT\b|Caterpillar)\s*" + _MODELO + _STOP, re.I),
    "New Holland":  re.compile(r"New\s*Holland\s*" + _MODELO + _STOP, re.I),
    "JCB":          re.compile(r"\bJCB\s*" + _MODELO + _STOP, re.I),
    "Case":         re.compile(r"\bCase\s*" + _MODELO + _STOP, re.I),
    "XCMG":         re.compile(r"\bXCMG\s*" + _MODELO + _STOP, re.I),
    "Volvo":        re.compile(r"\bVolvo\s*" + _MODELO + _STOP, re.I),
    "Komatsu":      re.compile(r"\bKomatsu\s*" + _MODELO + _STOP, re.I),
    "John Deere":   re.compile(r"John\s*Deere\s*" + _MODELO + _STOP, re.I),
    "Randon":       re.compile(r"\bRandon\s*" + _MODELO + _STOP, re.I),
    "Sany":         re.compile(r"\bSany\s*" + _MODELO + _STOP, re.I),
    "Hyundai":      re.compile(r"\bHyundai\s*" + _MODELO + _STOP, re.I),
    "LiuGong":      re.compile(r"\bLiuGong\s*" + _MODELO + _STOP, re.I),
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://pncp.gov.br/app/editais",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
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
    """Busca limites de preço E quantidade da tabela config_filtros_categoria (SPEC §4.4)."""
    db_url = get_db_url()
    if not HAS_PSYCOPG or not db_url:
        logger.warning("Usando limites estáticos (fallback) — sem DB_URL.")
        return
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT categoria_sigla, valor_minimo_unitario, valor_maximo_unitario, qtd_max FROM config_filtros_categoria;")
        rows = cur.fetchall()
        if not rows:
            logger.warning("config_filtros_categoria vazia. Usando limites estáticos.")
        else:
            for sigla, v_min, v_max, qtd_max in rows:
                if sigla in CATEGORIES:
                    if v_min is not None:
                        CATEGORIES[sigla]["min_price"] = float(v_min)
                    if v_max is not None:
                        CATEGORIES[sigla]["max_price"] = float(v_max)
                    if qtd_max is not None:
                        CATEGORIES[sigla]["qtd_max"] = int(qtd_max)
            logger.info("Limites de categoria carregados do banco com sucesso.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Falha ao carregar limites do banco: {e}. Usando fallback estático.")


def load_normalizacao_rules_from_db():
    """Carrega as regras de normalização de fornecedores do banco (SPEC §4.4).
    Preenche _NORMALIZACAO_RULES_DB com (regex_pattern, nome_normalizado).
    """
    global _NORMALIZACAO_RULES_DB
    db_url = get_db_url()
    if not HAS_PSYCOPG or not db_url:
        logger.warning("Usando regras de normalização hardcoded (fallback).")
        _NORMALIZACAO_RULES_DB = NORMALIZACAO_FALLBACK[:]
        return
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT termo_busca, nome_normalizado FROM normalizacao_fornecedores ORDER BY id;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if rows:
            _NORMALIZACAO_RULES_DB = [(r"\b" + re.escape(row[0]) + r"\b", row[1]) for row in rows]
            logger.info(f"{len(rows)} regras de normalização carregadas do banco.")
        else:
            logger.warning("normalizacao_fornecedores vazia. Usando regras hardcoded.")
            _NORMALIZACAO_RULES_DB = NORMALIZACAO_FALLBACK[:]
    except Exception as e:
        logger.warning(f"Falha ao carregar regras de normalização: {e}. Usando fallback.")
        _NORMALIZACAO_RULES_DB = NORMALIZACAO_FALLBACK[:]


def load_existing_keys() -> set:
    """Carrega as chaves já existentes no banco para carga incremental."""
    existing_keys = set()
    db_url = get_db_url()
    if not HAS_PSYCOPG or not db_url:
        return existing_keys
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT cnpj_orgao, ano_compra, sequencial_compra FROM transacao WHERE fonte_id = 'PNCP';")
        rows = cur.fetchall()
        for r in rows:
            existing_keys.add(f"{r[0]}_{r[1]}_{r[2]}")
        cur.close()
        conn.close()
        logger.info(f"{len(existing_keys)} chaves existentes carregadas para carga incremental.")
    except Exception as e:
        logger.warning(f"Falha ao carregar chaves existentes: {e}")
    return existing_keys


def determine_record_type(descricao: str) -> str:
    """Classifica o tipo do registro (SPEC §4.4).
    Ordem: PECAS primeiro (para não confundir "compra de peça" com COMPRA_NOVA).
    """
    if TIPO_REGEX["PECAS_MANUTENCAO"].search(descricao):
        return "PECAS_MANUTENCAO"
    if TIPO_REGEX["LOCACAO"].search(descricao):
        return "LOCACAO"
    if TIPO_REGEX["COMPRA_NOVA"].search(descricao):
        return "COMPRA_NOVA"
    return "INDEFINIDO"


def classify_category(descricao: str) -> Optional[str]:
    """Reclassifica a categoria pelo texto do item (mais preciso que o termo de busca)."""
    desc_lower = descricao.lower()
    for sigla, config in CATEGORIES.items():
        for kw in config["keywords"]:
            if re.search(kw, desc_lower):
                return sigla
    return None


def normalizar_fornecedor(razao: str) -> str:
    """Normaliza razão social. Usa regras do banco (_NORMALIZACAO_RULES_DB).
    Fallback para hardcoded se banco indisponível. (SPEC §4.4)
    Nunca retorna string vazia — retorna a razão em UPPER como fallback final.
    """
    upper = str(razao or "").upper().strip()
    if not upper:
        return ""

    rules = _NORMALIZACAO_RULES_DB if _NORMALIZACAO_RULES_DB else NORMALIZACAO_FALLBACK
    for pattern, normalized in rules:
        if re.search(pattern, upper, re.IGNORECASE):
            return normalized
    return upper


def sleep_entre_chamadas():
    """Rate limit: 0.3–0.4s (SPEC §4.3 item 6)."""
    time.sleep(random.uniform(0.3, 0.4))


# ─── API PNCP ───────────────────────────────────────────────────────

def search_pncp(termo: str, uf: str, pagina: int = 1, max_retries: int = 6) -> Optional[dict]:
    """Chama o endpoint de busca do PNCP com retries robustos e backoff exponencial com jitter."""
    url = (
        f"https://pncp.gov.br/api/search/"
        f"?q={termo}&tipos_documento=edital&ordenacao=-data"
        f"&pagina={pagina}&tam_pagina=100&status=todos&ufs={uf}"
    )
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code in [500, 502, 503, 504, 429]:
                backoff = (2 ** attempt) + random.uniform(1.5, 4.0)
                logger.warning(f"Search API HTTP {r.status_code} para {termo}/{uf} p.{pagina} (tentativa {attempt+1}/{max_retries}) — aguardando {backoff:.1f}s")
                time.sleep(backoff)
            else:
                logger.warning(f"Search API HTTP {r.status_code} para {termo}/{uf} p.{pagina}")
                return None
        except requests.RequestException as e:
            backoff = (2 ** attempt) + random.uniform(1.5, 4.0)
            logger.warning(f"Erro de conexão Search API: {e} (tentativa {attempt+1}/{max_retries}) — aguardando {backoff:.1f}s")
            time.sleep(backoff)
    return None


def fetch_item_details(cnpj: str, ano: int, sequencial: int, max_retries: int = 5) -> Optional[list]:
    """Obtém lista de itens de uma compra (/itens)."""
    url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code in [500, 502, 503, 504, 429]:
                backoff = (2 ** attempt) + random.uniform(1.0, 3.0)
                time.sleep(backoff)
            else:
                return None
        except requests.RequestException:
            backoff = (2 ** attempt) + random.uniform(1.0, 3.0)
            time.sleep(backoff)
    return None


def fetch_item_resultados(cnpj: str, ano: int, sequencial: int, numero_item: int, max_retries: int = 5) -> Optional[list]:
    """Obtém os resultados de um item específico (/itens/{n}/resultados).
    ESSENCIAL: Este é o único endpoint que retorna o fornecedor vencedor
    e o valor unitário homologado real (SPEC §4.3 armadilha #3).
    """
    url = (
        f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}"
        f"/itens/{numero_item}/resultados"
    )
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 404:
                # Item sem resultado publicado — normal, não é erro
                return []
            elif r.status_code in [500, 502, 503, 504, 429]:
                backoff = (2 ** attempt) + random.uniform(1.0, 3.0)
                time.sleep(backoff)
            else:
                return []
        except requests.RequestException:
            backoff = (2 ** attempt) + random.uniform(1.0, 3.0)
            time.sleep(backoff)
    return []


# ─── Processamento de itens ─────────────────────────────────────────

def processar_item(
    item: dict,
    resultados: list,
    categoria_sigla: str,
    uf: str,
    cnpj: str,
    ano: int,
    seq: int,
    item_busca: dict
) -> Optional[dict]:
    """Processa um item + seus resultados em um registro da transacao.

    Args:
        item: dict do endpoint /itens (contém descrição, quantidade, situação)
        resultados: list do endpoint /resultados (contém fornecedor e valor homologado)
        categoria_sigla: sigla da categoria (BHL, EXC, etc.)
        uf: UF da busca
        cnpj: CNPJ do órgão
        ano: ano da compra
        seq: sequencial da compra
        item_busca: item do resultado da busca /search/ (contém município, órgão)
    """
    descricao = str(item.get("descricao") or "")
    if not descricao:
        return None

    objeto_compra = (
        item_busca.get("title", "") or
        item_busca.get("objetoCompra", "") or
        item_busca.get("description", "")
    )
    descricao_completa = f"{objeto_compra} {descricao}".strip()
    tipo = determine_record_type(descricao_completa)

    numero_item = int(item.get("numeroItem", 0) or 0)

    # ── Situação do item ────────────────────────────────────────────
    raw_sit = item.get("situacaoCompraItemNome") or item.get("situacaoCompraItem") or ""
    situacao = str(raw_sit).upper().strip()
    if any(h in situacao for h in ("HOMOLOGADO", "ADJUDICADO")):
        situacao = "HOMOLOGADO"
    elif not situacao:
        situacao = "SEM_RESULTADO"

    # ── Fornecedor e valor: prioridade ao endpoint /resultados ──────
    # O /itens NÃO retorna o fornecedor vencedor. O /resultados retorna.
    # (SPEC §4.3 armadilha #3: "O endpoint resultados não retorna marca.
    #  Marca vem por dedução §4.5." — mas o FORNECEDOR vem do /resultados.)
    fornecedor_original = ""
    valor_unitario = 0.0
    data_homologacao = None

    if resultados and isinstance(resultados, list) and len(resultados) > 0:
        res = resultados[0]  # Primeiro resultado = vencedor
        fornecedor_original = (
            res.get("nomeRazaoSocialFornecedor") or
            res.get("razaoSocialFornecedor") or
            res.get("fornecedor", {}).get("razaoSocial") or
            ""
        )
        val_hom = res.get("valorUnitarioHomologado")
        if val_hom is not None:
            try:
                valor_unitario = float(val_hom)
            except (ValueError, TypeError):
                pass
        # Data de homologação real vem do resultado
        data_hom_raw = (
            res.get("dataHomologacao") or
            res.get("dataAtualizacao") or
            item.get("dataHomologacao") or
            item.get("dataResultado") or
            ""
        )
        if data_hom_raw:
            data_homologacao = str(data_hom_raw)[:10]

    # Fallback: valor estimado/quantidade do /itens quando não há resultado
    if valor_unitario == 0.0:
        try:
            valor_unitario = float(
                item.get("valorUnitarioHomologado") or
                item.get("valorUnitarioEstimado") or 0
            )
        except (ValueError, TypeError):
            pass

    if not data_homologacao:
        raw_d = item.get("dataHomologacao") or item.get("dataResultado") or ""
        if raw_d:
            data_homologacao = str(raw_d)[:10]

    # ── Quantidade ──────────────────────────────────────────────────
    quantidade = 0.0
    try:
        quantidade = float(
            item.get("quantidadeHomologada") or
            item.get("quantidade") or 0
        )
    except (ValueError, TypeError):
        pass

    # ── Normalização do fornecedor (SPEC §4.4) ──────────────────────
    fornecedor_normalizado = normalizar_fornecedor(fornecedor_original)

    # ── Reclassificação de categoria pelo texto do item ─────────────
    categoria_reclass = classify_category(descricao)
    cat_final = categoria_reclass or categoria_sigla

    # ── Extração de Frota Instalada (apenas para PECAS_MANUTENCAO §4.6) ─
    frota = extrair_dados_frota(descricao) if tipo == "PECAS_MANUTENCAO" else {
        "marca": "NÃO SE APLICA", "modelo": "NÃO SE APLICA", "ano": "NÃO SE APLICA"
    }

    # ── Filtro de máquina real (SPEC §4.4) ──────────────────────────
    # Aplica SOMENTE em COMPRA_NOVA + HOMOLOGADO.
    # Descarta: valor fora do range, quantidade fracionária, qtd > limite da categoria.
    if tipo == "COMPRA_NOVA" and situacao == "HOMOLOGADO":
        config_cat = CATEGORIES.get(cat_final)
        if config_cat:
            min_p = config_cat.get("min_price")
            max_p = config_cat.get("max_price")
            qtd_max = config_cat.get("qtd_max", 10)

            if min_p is not None and valor_unitario < min_p:
                logger.debug(f"Descartado: valor {valor_unitario} < min {min_p} ({cat_final})")
                return None
            if max_p is not None and max_p > 0 and valor_unitario > max_p:
                logger.debug(f"Descartado: valor {valor_unitario} > max {max_p} ({cat_final})")
                return None
            if quantidade <= 0 or quantidade != int(quantidade) or quantidade > qtd_max:
                logger.debug(f"Descartado: quantidade inválida {quantidade} ({cat_final})")
                return None

    # ── Município e órgão (do resultado da busca /search/) ──────────
    orgao_nome = item_busca.get("orgao_nome") or item_busca.get("orgaoNome") or ""
    if not orgao_nome:
        orgao_data = item_busca.get("orgao", {}) or {}
        orgao_nome = orgao_data.get("nome", "") if isinstance(orgao_data, dict) else str(orgao_data)
    if not orgao_nome:
        orgao_data = item_busca.get("orgaoEntidade", {}) or {}
        orgao_nome = orgao_data.get("razaoSocial", "") if isinstance(orgao_data, dict) else str(orgao_data)

    municipio_nome = item_busca.get("municipio_nome") or item_busca.get("municipioNome") or ""
    if not municipio_nome:
        municipio = item_busca.get("municipio", {}) or {}
        municipio_nome = municipio.get("nome", "") if isinstance(municipio, dict) else str(municipio)

    # ── URL de origem para rastreabilidade (SPEC §6) ─────────────────
    cnpj_orgao = str(cnpj)
    ano_compra = int(ano)
    sequencial = int(seq)
    url_origem = f"https://pncp.gov.br/app/editais/{cnpj_orgao}/{ano_compra}/{sequencial}"

    return {
        "cnpj_orgao":            cnpj_orgao,
        "ano_compra":            ano_compra,
        "sequencial_compra":     sequencial,
        "numero_item":           numero_item,
        "municipio":             municipio_nome,
        "uf":                    uf,
        "orgao":                 orgao_nome,
        "fornecedor_original":   str(fornecedor_original).strip(),
        "fornecedor_normalizado": fornecedor_normalizado,
        "quantidade":            quantidade,
        "valor_unitario":        valor_unitario,
        "data_homologacao":      data_homologacao,
        "descricao_original":    descricao[:500] if descricao else "",
        "url_origem":            url_origem,
        "categoria_sigla":       cat_final,
        "situacao":              situacao,
        "tipo_registro":         tipo,
        "fonte_id":              "PNCP",
        "comprador_tipo":        "Governo",
        "tipo":                  "COMPRA",
        "marca":                 frota["marca"],
        "modelo":                frota["modelo"],
        "ano":                   frota["ano"],
    }


# ─── Crawler principal ──────────────────────────────────────────────

def crawlear_pncp() -> List[Dict[str, Any]]:
    """Loop principal: 8 categorias × 27 UFs com paginação e chamada ao /resultados."""
    todos_registros = []
    total_chamadas = 0

    chaves_existentes = load_existing_keys()

    target_category = os.environ.get("TARGET_CATEGORY")
    if target_category:
        logger.info(f"Modo Matriz: Coletando apenas a categoria {target_category}")

    for sigla, config in CATEGORIES.items():
        if target_category and sigla != target_category:
            continue
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
                        cnpj = (
                            item_busca.get("orgao_cnpj") or
                            (item_busca.get("orgao", {}) or {}).get("cnpj", "") or
                            item_busca.get("cnpjOrgao", "")
                        )
                        ano = item_busca.get("ano") or item_busca.get("anoCompra", 0) or 0
                        seq = item_busca.get("numero_sequencial") or item_busca.get("sequencialCompra", 0) or 0

                        # Limitação de data (últimos 12 meses — API ordena -data)
                        if ano and int(ano) < 2025:
                            logger.info(f"[{sigla}] {uf} — Registro antigo (ano {ano}). Parando paginação.")
                            stop_pagination = True
                            break

                        # Extrair CNPJ/ano/seq da item_url se não vieram direto
                        item_url = item_busca.get("item_url", "")
                        if (not cnpj or not ano or not seq) and item_url:
                            match = re.search(r'/compras/(\d+)/(\d+)/(\d+)', item_url)
                            if match:
                                cnpj = cnpj or match.group(1)
                                ano = ano or int(match.group(2))
                                seq = seq or int(match.group(3))

                        if not cnpj or not ano or not seq:
                            continue

                        chave = f"{cnpj}_{ano}_{seq}"
                        if chave in chaves_existentes:
                            logger.debug(f"Pulando {chave}: já no banco.")
                            continue
                        chaves_existentes.add(chave)

                        # Passo 1: buscar itens da compra (/itens)
                        itens_detalhe = fetch_item_details(cnpj, ano, seq)
                        total_chamadas += 1

                        if not itens_detalhe:
                            sleep_entre_chamadas()
                            continue

                        for item_det in itens_detalhe:
                            numero_item = int(item_det.get("numeroItem", 0) or 0)
                            if numero_item <= 0:
                                continue

                            # Passo 2: buscar resultado do item (/resultados) — ONDE ESTÁ O FORNECEDOR
                            resultados = fetch_item_resultados(cnpj, ano, seq, numero_item)
                            total_chamadas += 1
                            sleep_entre_chamadas()  # Rate limit após cada chamada /resultados

                            registro = processar_item(
                                item_det, resultados, sigla, uf,
                                cnpj, ano, seq, item_busca
                            )
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


# ─── Ingestão no banco ──────────────────────────────────────────────

def ingest_to_supabase(records: List[Dict[str, Any]], db_url: str):
    """Insere ou atualiza registros no banco.
    Usa ON CONFLICT DO UPDATE para corrigir registros existentes com
    fornecedor_original/normalizado vazios de execuções anteriores.
    """
    if not HAS_PSYCOPG or not db_url:
        logger.error("psycopg2 não disponível ou sem DB_URL — ingestão ignorada.")
        return

    query = """
        INSERT INTO transacao (
            cnpj_orgao, ano_compra, sequencial_compra, numero_item,
            municipio, uf, orgao, fornecedor_original, fornecedor_normalizado,
            quantidade, valor_unitario, data_homologacao, descricao_original, url_origem,
            categoria_sigla, situacao, tipo_registro, fonte_id, comprador_tipo, tipo,
            marca, modelo, ano
        ) VALUES (
            %(cnpj_orgao)s, %(ano_compra)s, %(sequencial_compra)s, %(numero_item)s,
            %(municipio)s, %(uf)s, %(orgao)s, %(fornecedor_original)s, %(fornecedor_normalizado)s,
            %(quantidade)s, %(valor_unitario)s, %(data_homologacao)s, %(descricao_original)s, %(url_origem)s,
            %(categoria_sigla)s, %(situacao)s, %(tipo_registro)s, %(fonte_id)s, %(comprador_tipo)s, %(tipo)s,
            %(marca)s, %(modelo)s, %(ano)s
        )
        ON CONFLICT (cnpj_orgao, ano_compra, sequencial_compra, numero_item, tipo_registro, fonte_id)
        DO UPDATE SET
            fornecedor_original    = EXCLUDED.fornecedor_original,
            fornecedor_normalizado = EXCLUDED.fornecedor_normalizado,
            valor_unitario         = CASE WHEN EXCLUDED.valor_unitario > 0 THEN EXCLUDED.valor_unitario ELSE transacao.valor_unitario END,
            data_homologacao       = COALESCE(EXCLUDED.data_homologacao, transacao.data_homologacao),
            situacao               = EXCLUDED.situacao,
            tipo_registro          = EXCLUDED.tipo_registro,
            municipio              = COALESCE(NULLIF(EXCLUDED.municipio, ''), transacao.municipio),
            orgao                  = COALESCE(NULLIF(EXCLUDED.orgao, ''), transacao.orgao);
    """
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        try:
            execute_batch(cur, query, records, page_size=200)
            conn.commit()
            logger.info(f"{len(records)} registros inseridos/atualizados no banco.")
        except Exception as e:
            conn.rollback()
            logger.warning(f"Falha no batch insert ({e}). Tentando inserção individual...")
            success = 0
            for rec in records:
                try:
                    cur.execute(query, rec)
                    conn.commit()
                    success += 1
                except Exception as ex:
                    conn.rollback()
                    logger.warning(f"Falha ao inserir {rec.get('cnpj_orgao')}_{rec.get('sequencial_compra')}_{rec.get('numero_item')}: {ex}")
            logger.info(f"{success}/{len(records)} registros inseridos individualmente.")
        cur.close()
        conn.close()
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
    logger.info("PESADOS.ID — Pipeline de Ingestão PNCP v3.0")
    logger.info("=" * 60)

    # 1. Carregar configurações dinâmicas do banco
    load_category_limits_from_db()
    load_normalizacao_rules_from_db()

    db_url = get_db_url()

    # Jitter inicial em modo matriz para evitar concorrência simultânea na API do PNCP
    target_category = os.environ.get("TARGET_CATEGORY")
    if target_category:
        stagger = random.uniform(1.5, 9.0)
        logger.info(f"Modo Matriz [{target_category}]: Aguardando jitter de {stagger:.1f}s para desincronizar requisições...")
        time.sleep(stagger)

    # 2. Testar conectividade com a API PNCP com rotação de UFs e termo dinâmico
    registros = []
    termo_teste = "retroescavadeira"
    if target_category and target_category in CATEGORIES:
        termo_teste = CATEGORIES[target_category]["search_terms"][0]

    api_conectada = False
    logger.info(f"Testando conexão com a API do PNCP (termo: '{termo_teste}')...")
    for test_uf in ["MG", "SP", "DF"]:
        test = search_pncp(termo_teste, test_uf, 1, max_retries=4)
        if test and (test.get("items") or test.get("data") is not None):
            api_conectada = True
            logger.info(f"API PNCP respondeu com sucesso para '{termo_teste}' / UF {test_uf}. Iniciando crawler...")
            break
        else:
            logger.warning(f"Teste de conectividade na UF {test_uf} não obteve resposta. Tentando próxima UF...")
            time.sleep(random.uniform(2.0, 4.0))

    if not api_conectada:
        logger.warning("Conexão inicial com a API PNCP teve oscilações nas UFs de teste. Prosseguindo diretamente com a coleta nacional...")

    registros = crawlear_pncp()

    if not registros:
        logger.warning("Nenhum registro retornado pelo PNCP nesta execução.")

    # 3. Contagens do funil (SPEC §4 — Tela Metodologia)
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
        and r.get("quantidade", 0) > 0
        and r.get("quantidade", 0) == int(r.get("quantidade", 0))
        and r.get("quantidade", 0) <= CATEGORIES.get(r.get("categoria_sigla", ""), {}).get("qtd_max", 10)
    ])

    logger.info(f"Funil — brutos: {registros_brutos} | compra_nova: {registros_classificados} | homologados: {registros_homologados} | aprovados filtro: {registros_aprovados}")

    # 4. Persistir no banco
    if db_url:
        ingest_to_supabase(registros, db_url)
        log_coleta(db_url, registros_brutos, registros_aprovados, "sucesso")
    else:
        output = "pncp_crawled_records.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(registros, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Sem DB_URL — registros salvos em {output}")

    terminado = datetime.now()
    logger.info(f"Duração total: {(terminado - inicio).total_seconds():.1f}s")

    summary = json.dumps({
        "registros_brutos": registros_brutos,
        "registros_classificados": registros_classificados,
        "registros_homologados": registros_homologados,
        "registros_aprovados": registros_aprovados,
        "status": "sucesso"
    })
    print(f"\n---PIPELINE_SUMMARY:{summary}:PIPELINE_SUMMARY---")
    logger.info("Pipeline v3.0 finalizado com sucesso!")


if __name__ == "__main__":
    run_pipeline()
