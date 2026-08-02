"""
Re-enriquecimento PARALELO dos registros existentes na tabela transacao.

Usa ThreadPoolExecutor (4 workers) para buscar /resultados em paralelo,
reduzindo o tempo de ~10min para ~2-3min para 500 registros.

Variáveis de ambiente:
  DRY_RUN=1   → mostra o que faria, sem escrever no banco
  LIMITE=N    → max registros por execução (default: 500)
  WORKERS=N   → threads paralelas (default: 4, max recomendado: 6)
"""

import os
import re
import sys
import time
import random
import psycopg2
from psycopg2.extras import execute_batch
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import requests

load_dotenv()

DB_URL   = os.environ.get("SUPABASE_DB_URL")
DRY_RUN  = os.environ.get("DRY_RUN", "0") == "1"
LIMITE   = int(os.environ.get("LIMITE", "500"))
WORKERS  = int(os.environ.get("WORKERS", "4"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer":    "https://pncp.gov.br/app/editais",
    "Accept":     "application/json, text/plain, */*",
}

# Regras de normalização hardcoded (fallback)
NORMALIZACAO_FALLBACK = [
    (r"BANDEIRANTES|BAMAQ|BMAQ",  "BAMAQ"),
    (r"BRASIF",                    "BRASIF"),
    (r"VALENCE",                   "VALENCE"),
    (r"TRIAMA\s*NORTE|TRIAMA",     "TRIAMA NORTE"),
    (r"CENTRO\s*OESTE",            "CENTRO OESTE"),
    (r"XCMG",                      "XCMG BRASIL"),
    (r"CUMMINS",                   "CUMMINS"),
    (r"FAROL",                     "FAROL COMERCIAL"),
    (r"ECOSOL",                    "ECOSOL"),
    (r"\bJCB\b",                   "JCB DO BRASIL"),
    (r"CATERPILLAR|\bCAT\b",       "CATERPILLAR"),
    (r"NEW\s*HOLLAND",             "NEW HOLLAND"),
    (r"\bCASE\b",                  "CASE"),
    (r"KOMATSU",                   "KOMATSU"),
    (r"VOLVO",                     "VOLVO CE"),
    (r"JOHN\s*DEERE",              "JOHN DEERE"),
]


def carregar_regras(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT termo_busca, nome_normalizado FROM normalizacao_fornecedores ORDER BY id;")
        rows = cur.fetchall()
        cur.close()
        if rows:
            regras = [(r"\b" + re.escape(r[0]) + r"\b", r[1]) for r in rows]
            print(f"{len(regras)} regras de normalização carregadas do banco.")
            return regras
    except Exception as e:
        print(f"Falha ao carregar regras do banco: {e}. Usando hardcoded.")
    return list(NORMALIZACAO_FALLBACK)


def normalizar(razao: str, regras: list) -> str:
    upper = str(razao or "").upper().strip()
    if not upper:
        return ""
    for pattern, normalized in regras:
        if re.search(pattern, upper, re.IGNORECASE):
            return normalized
    return upper


def fetch_resultados(cnpj, ano, seq, numero_item):
    """Busca /resultados com retries e rate limit por worker."""
    url = (
        f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}"
        f"/compras/{ano}/{seq}/itens/{numero_item}/resultados"
    )
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 404:
                return []
            elif r.status_code in [429, 500, 502, 503, 504]:
                time.sleep(1.5 * (attempt + 1))
            else:
                return []
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
    return []


def processar_registro(row, regras):
    """Chamada à API + normalização para um único registro. Executado em thread."""
    rec_id, cnpj, ano, seq, num_item, tipo, situacao = row

    # Rate limit distribuído por worker (evita sobrecarga mesmo em paralelo)
    time.sleep(random.uniform(0.3, 0.5))

    resultados = fetch_resultados(cnpj, ano, seq, num_item)

    if not resultados or not isinstance(resultados, list):
        return {"id": rec_id, "status": "sem_resultado"}

    res = resultados[0]
    fornecedor_original = (
        res.get("nomeRazaoSocialFornecedor") or
        res.get("razaoSocialFornecedor") or
        (res.get("fornecedor") or {}).get("razaoSocial") or
        ""
    ).strip()

    val_hom = res.get("valorUnitarioHomologado")
    valor_unitario = None
    if val_hom is not None:
        try:
            valor_unitario = float(val_hom)
        except (ValueError, TypeError):
            pass

    data_hom = res.get("dataHomologacao") or res.get("dataAtualizacao") or ""
    data_homologacao = str(data_hom)[:10] if data_hom else None

    fornecedor_normalizado = normalizar(fornecedor_original, regras) if fornecedor_original else ""

    return {
        "id":                   rec_id,
        "status":               "ok",
        "tipo":                 tipo,
        "situacao":             situacao,
        "fornecedor_original":  fornecedor_original,
        "fornecedor_normalizado": fornecedor_normalizado,
        "valor_unitario":       valor_unitario or 0.0,
        "data_homologacao":     data_homologacao,
    }


def salvar_batch(conn, resultados_ok):
    """Salva um lote de resultados no banco em batch."""
    if not resultados_ok:
        return 0
    cur = conn.cursor()
    dados = [
        (
            r["fornecedor_original"],
            r["fornecedor_normalizado"],
            r["valor_unitario"],
            r["valor_unitario"],
            r["data_homologacao"],
            r["id"],
        )
        for r in resultados_ok
    ]
    cur.executemany("""
        UPDATE transacao SET
            fornecedor_original    = %s,
            fornecedor_normalizado = %s,
            valor_unitario         = CASE WHEN %s > 0 THEN %s ELSE valor_unitario END,
            data_homologacao       = COALESCE(%s, data_homologacao)
        WHERE id = %s
    """, dados)
    conn.commit()
    cur.close()
    return len(dados)


def run():
    modo = "[DRY RUN] " if DRY_RUN else ""
    print(f"{modo}Re-enriquecimento paralelo — LIMITE={LIMITE}, WORKERS={WORKERS}")

    conn = psycopg2.connect(DB_URL)
    regras = carregar_regras(conn)

    cur = conn.cursor()
    # Prioriza COMPRA_NOVA + HOMOLOGADO, depois COMPRA_NOVA, depois o resto
    cur.execute("""
        SELECT id, cnpj_orgao, ano_compra, sequencial_compra, numero_item, tipo_registro, situacao
        FROM transacao
        WHERE (fornecedor_original IS NULL OR fornecedor_original = '')
          AND fonte_id = 'PNCP'
        ORDER BY
            CASE
                WHEN tipo_registro = 'COMPRA_NOVA' AND situacao = 'HOMOLOGADO' THEN 0
                WHEN tipo_registro = 'COMPRA_NOVA' THEN 1
                ELSE 2
            END,
            id
        LIMIT %s
    """, (LIMITE,))
    rows = cur.fetchall()
    cur.close()

    total = len(rows)
    print(f"{total} registros a processar.")
    if not total:
        print("Nada a fazer — todos os registros já têm fornecedor preenchido!")
        conn.close()
        return

    atualizados  = 0
    sem_resultado = 0
    erros        = 0
    batch_ok     = []
    BATCH_SIZE   = 50  # Salva a cada 50 registros ok

    inicio = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(processar_registro, row, regras): row for row in rows}

        concluidos = 0
        for future in as_completed(futures):
            concluidos += 1
            try:
                resultado = future.result()
                if resultado["status"] == "ok":
                    if DRY_RUN:
                        r = resultado
                        print(f"  [DRY] id={r['id']} {r['tipo']}/{r['situacao']} | "
                              f"fornorig={repr(r['fornecedor_original'])} | "
                              f"norm={repr(r['fornecedor_normalizado'])} | "
                              f"val={r['valor_unitario']} | data={r['data_homologacao']}")
                        atualizados += 1
                    else:
                        batch_ok.append(resultado)
                        # Salva em batch a cada BATCH_SIZE registros
                        if len(batch_ok) >= BATCH_SIZE:
                            try:
                                salvos = salvar_batch(conn, batch_ok)
                                atualizados += salvos
                                batch_ok = []
                            except Exception as e:
                                print(f"  ERRO ao salvar batch: {e}")
                                conn.rollback()
                                erros += len(batch_ok)
                                batch_ok = []
                else:
                    sem_resultado += 1

            except Exception as e:
                erros += 1
                row = futures[future]
                print(f"  ERRO id={row[0]}: {e}")

            # Progresso a cada 50 itens
            if concluidos % 50 == 0 or concluidos == total:
                elapsed = time.time() - inicio
                rate = concluidos / elapsed if elapsed > 0 else 0
                eta = (total - concluidos) / rate if rate > 0 else 0
                print(f"  [{concluidos}/{total}] ok={atualizados} sem_resultado={sem_resultado} erros={erros} "
                      f"({rate:.1f}/s, ETA ~{eta:.0f}s)")

    # Salva o lote final (se não for DRY_RUN)
    if not DRY_RUN and batch_ok:
        try:
            salvos = salvar_batch(conn, batch_ok)
            atualizados += salvos
        except Exception as e:
            print(f"  ERRO ao salvar lote final: {e}")
            conn.rollback()
            erros += len(batch_ok)

    conn.close()

    elapsed_total = time.time() - inicio
    print()
    print(f"{modo}Concluído em {elapsed_total:.1f}s:")
    print(f"  Atualizados no banco: {atualizados}")
    print(f"  Sem resultado na API: {sem_resultado}")
    print(f"  Erros:                {erros}")
    print()

    if not DRY_RUN and (total - sem_resultado - erros) > 0:
        print("Registros restantes com fornecedor vazio: rode novamente para continuar.")


if __name__ == "__main__":
    run()
