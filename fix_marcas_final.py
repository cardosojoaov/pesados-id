"""
Correções finais:
1. Unifica 'New Holland' -> 'NEW HOLLAND' na dealer_marca (case consistency)
2. Corrige variações com acento em fornecedor_normalizado (PARANÁ -> PARANA)
3. Adiciona dealers restantes dos 36 sem marca
4. Zera e re-dispara trigger para pegar correções
"""
import os, re, psycopg2, unicodedata
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.environ.get("SUPABASE_DB_URL"))
cur = conn.cursor()

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')

# PASSO 1: Unificar dealer_marca - tudo UPPERCASE
print("Normalizando dealer_marca para UPPERCASE...")
cur.execute("SELECT id, marca FROM dealer_marca WHERE marca != UPPER(marca)")
rows = cur.fetchall()
for r in rows:
    cur.execute("UPDATE dealer_marca SET marca = %s WHERE id = %s", (r[1].upper(), r[0]))
print(f"  {len(rows)} marcas padronizadas para UPPER.")
conn.commit()

# PASSO 2: Corrigir variações com acento no fornecedor_normalizado
print("\nCorrigindo variações com acento...")
cur.execute("""
    SELECT DISTINCT fornecedor_normalizado FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
""")
normals = [r[0] for r in cur.fetchall() if r[0]]

count_corr = 0
for norm in normals:
    stripped = strip_accents(norm).upper()
    if stripped != norm:  # tem diferença — corrigir
        cur.execute("""
            UPDATE transacao SET fornecedor_normalizado = %s
            WHERE fornecedor_normalizado = %s AND tipo_registro='COMPRA_NOVA'
        """, (stripped, norm))
        if cur.rowcount:
            print(f"  '{norm}' -> '{stripped}' ({cur.rowcount} registros)")
            count_corr += cur.rowcount
conn.commit()
print(f"  Total: {count_corr} registros corrigidos.")

# PASSO 3: Adicionar dealers restantes com marcas conhecidas
print("\nAdicionando dealers restantes...")
novos_dealers = [
    # SOTREQ = distribuidora oficial da Caterpillar no Brasil
    ("SOTREQ S/A",          "CATERPILLAR", "confirmado"),
    ("SOTREQ SA",           "CATERPILLAR", "confirmado"),
    ("SOTREQ",              "CATERPILLAR", "confirmado"),
    # NORDICA = concessionária Volvo CE
    ("NORDICA VEICULOS SA", "VOLVO",       "presumido"),
    ("NORDICA VEICULOS S/A","VOLVO",       "presumido"),
    # BMC HYUNDAI = distribuidora Hyundai CE
    ("BMC HYUNDAI",         "HYUNDAI",     "confirmado"),
    # PARA EQUIPAMENTOS com acento
    ("PARANA EQUIPAMENTOS SA",  "CASE",    "presumido"),
    # COMAZI = John Deere no RS
    ("COMAZI TRATORES",     "JOHN DEERE",  "presumido"),
    # SEMAX = JCB
    ("SEMAX MAQUINAS",      "JCB",         "presumido"),
    # FORZA (versão com acento normalizado)
    ("FORZA MAQUINAS",      "CASE",        "presumido"),
    # SHARK (versão com acento normalizado)
    ("SHARK MAQUINAS",      "JCB",         "presumido"),
    # D&D = revendedor multi
    ("D&D IMPORTACAO",      "XCMG",        "presumido"),
    # VIANMAQ = New Holland no RS
    ("VIANMAQ EQUIPAMENTOS","NEW HOLLAND", "presumido"),
    # PESO CAMINHOES = distribuidora
    ("PESO CAMINHOES",      "VOLVO",       "presumido"),
    ("PESO CAMINHOES E IMPLEMENTOS", "VOLVO", "presumido"),
    # MANUPA = revendedor
    ("MANUPA COMERCIO",     "LIUGONG",     "presumido"),
    # PRIMUM = dealer multimarcas
    ("PRIMUM COMERCIO",     "KOMATSU",     "presumido"),
    # TOSI = dealer
    ("TOSI COMERCIO",       "XCMG",        "presumido"),
    # ULTRA MAQUINAS
    ("ULTRA MAQUINAS",      "XCMG",        "presumido"),
    # ALFA COMERCIO
    ("ALFA COMERCIO DE EQUIPAMENTOS", "KOMATSU", "presumido"),
    # GUIMARAES
    ("GUIMARAES AGRICOLA",  "JOHN DEERE",  "presumido"),
    # LIPPEL
    ("LIPPEL ENGENHARIA",   "XCMG",        "presumido"),
    # SILMAQUINAS
    ("SILMAQUINAS E EQUIPAMENTOS", "NEW HOLLAND", "presumido"),
]

for forn, marca, conf in novos_dealers:
    cur.execute("""
        INSERT INTO dealer_marca (fornecedor_normalizado, marca, confianca, data_inicio_vigencia)
        VALUES (%s, %s, %s, '2020-01-01')
        ON CONFLICT DO NOTHING
    """, (forn, marca, conf))
conn.commit()
print(f"  {len(novos_dealers)} novos dealers inseridos.")

# PASSO 4: Também normalizar variações sem pontuação no fornecedor_normalizado
print("\nPadronizando pontuação residual...")
substituicoes = [
    ("FORZA MAQUINAS AGRICOLAS E CONSTRUCAO LTDA,", "FORZA MAQUINAS"),
    ("SHARK MAQUINAS PARA CONSTRUCAO LTDA",         "SHARK MAQUINAS"),
    ("CAMPO E CIDADE COMERCIO DE PECAS E SERVICOS LTDA", "CAMPO E CIDADE COMERCIO"),
    ("CCM CMERCIO E SERVICOS LTDA",                 "CCM COMERCIO"),
    ("D&D IMPORTACAO, COMERCIO, SERVICOS E LOCACOES EIRELI", "D&D IMPORTACAO"),
    ("NORDICA VEICULOS S.A.",                        "NORDICA VEICULOS SA"),
    ("NORDICA VEICULOS S/A",                         "NORDICA VEICULOS SA"),
    ("BMC HYUNDAI S/A",                              "BMC HYUNDAI"),
    ("VIANMAQ EQUIPAMENTOS LTDA.",                   "VIANMAQ EQUIPAMENTOS"),
    ("VIANMAQ EQUIPAMENTOS LTDA",                    "VIANMAQ EQUIPAMENTOS"),
    ("PESO CAMINHOES E IMPLEMENTOS LTDA",            "PESO CAMINHOES E IMPLEMENTOS"),
    ("MANUPA COMERCIO EXPORTACAO IMPORTACAO DE EQUIPAMENTOS E VEICULOS ADAPTADOS LTDA",       "MANUPA COMERCIO"),
    ("MANUPA COMERCIO, EXPORTACAO, IMPORTACAO DE EQUIPAMENTOS E VEICULOS ADAPTADOS EIRELI",  "MANUPA COMERCIO"),
    ("PRIMUM COMERCIO DE IMPLEMENTOS LTDA",          "PRIMUM COMERCIO"),
    ("TOSI COMERCIO DE MAQUINAS E EQUIPAMENTOS LTDA","TOSI COMERCIO"),
    ("ULTRA MAQUINAS E SERVICOS LTDA-EPP",           "ULTRA MAQUINAS"),
    ("ALFA COMERCIO DE EQUIPAMENTOS LTDA",           "ALFA COMERCIO DE EQUIPAMENTOS"),
    ("GUIMARAES AGRICOLA LTDA",                      "GUIMARAES AGRICOLA"),
    ("LIPPEL ENGENHARIA E EQUIPAMENTOS LTDA",        "LIPPEL ENGENHARIA"),
    ("SILMAQUINAS E EQUIPAMENTOS LTDA",              "SILMAQUINAS E EQUIPAMENTOS"),
    ("SEMAX MAQUINAS LTDA",                          "SEMAX MAQUINAS"),
    ("COMAZI TRATORES E MAQUINAS LTDA",              "COMAZI TRATORES"),
]

count_sub = 0
for old, new in substituicoes:
    cur.execute("""
        UPDATE transacao SET fornecedor_normalizado=%s
        WHERE fornecedor_normalizado=%s AND tipo_registro='COMPRA_NOVA'
    """, (new, old))
    count_sub += cur.rowcount
conn.commit()
print(f"  {count_sub} registros padronizados.")

# PASSO 5: Re-processar trigger com marca zerada
print("\nZerando e re-disparando trigger...")
cur.execute("""
    UPDATE transacao SET marca_deduzida = NULL
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
""")
cur.execute("""
    UPDATE transacao SET fornecedor_normalizado = fornecedor_normalizado
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
""")
conn.commit()
print(f"  Trigger re-disparado.")

# RESULTADO FINAL
print("\n=== RESULTADO FINAL ===")
cur.execute("""
    SELECT marca_deduzida, COUNT(*)
    FROM transacao
    WHERE tipo_registro='COMPRA_NOVA' AND situacao='HOMOLOGADO'
      AND fornecedor_original IS NOT NULL AND fornecedor_original != ''
    GROUP BY marca_deduzida ORDER BY 2 DESC
""")
total_ok = 0
total_nao = 0
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]}")
    if r[0] and 'IDENTIFICAD' not in str(r[0]).upper():
        total_ok += r[1]
    else:
        total_nao += r[1]
print(f"\n  COM marca: {total_ok}/151 | SEM marca: {total_nao}/151")

cur.close()
conn.close()
